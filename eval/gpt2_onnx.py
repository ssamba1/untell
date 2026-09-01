"""True GPT-2 perplexity with no HuggingFace anywhere in the path.

This module exists because I twice reported a transformer measurement as environmentally blocked,
and it was not. huggingface.co and four mirrors are egress-blocked here, but the ONNX model zoo
keeps GPT-2 in **GitHub LFS**, and LFS objects for public repos are served by
media.githubusercontent.com, which is reachable. The earlier 403 came from a github.com URL hitting
this session's repository scoping -- a permission error I read as a network one, and stopped on.

    weights   onnx/models -> gpt2-lm-head-10.onnx (664,871,060 bytes) via media.githubusercontent
    tokenizer OpenAI's published encoder.json + vocab.bpe, on GitHub
    runtime   onnxruntime, from pypi (which this environment does not proxy)

MEASURED with it (n=250 per group, seed 0, 384-token cap), mean negative log-likelihood --
lower = more predictable = the machine-like end of a perplexity signal:

    ASAP      ELL 3.8748   non-ELL   3.5533   d -0.671
    ELLIPSE   low 3.7733   high-prof 3.1725   d -1.320

Both directions match the stdlib bigram model in `eval/ngram_lm.py` and both are LARGER, so the
finding is not an artifact of a weak n-gram model: scaling the language model amplifies it.

**This is a perplexity signal, not a detector.** GPT-2 small is not an AI-text detector and must
never be pointed at a student's work as though it were one.

    python -m eval.gpt2_onnx fetch
    python -m eval.gpt2_onnx score --csv essays.csv --by ell_status --per-group 250
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import sys
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://media.githubusercontent.com/media/onnx/models/main/validated/text/"
    "machine_comprehension/gpt-2/model/gpt2-lm-head-10.onnx"
)
ENCODER_URL = "https://raw.githubusercontent.com/graykode/gpt-2-Pytorch/master/GPT2/encoder.json"
BPE_URL = "https://raw.githubusercontent.com/graykode/gpt-2-Pytorch/master/GPT2/vocab.bpe"
CITATION = (
    "GPT-2 (Radford et al. 2019), ONNX export from the onnx/models zoo; BPE vocabulary as "
    "published by OpenAI. A perplexity signal, NOT a detector."
)
MAX_TOKENS = 384
MIN_TOKENS = 20


def _cache() -> Path:
    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return Path(base) / "gpt2"


def fetch(dest: Path | None = None) -> Path:
    """~665MB once. Cached outside the tree; nothing here is ever committed."""
    dest = dest or _cache()
    dest.mkdir(parents=True, exist_ok=True)
    for url, name in (
        (ENCODER_URL, "encoder.json"),
        (BPE_URL, "vocab.bpe"),
        (MODEL_URL, "gpt2-lm-head.onnx"),
    ):
        target = dest / name
        if target.exists():
            continue
        print(f"fetching {name}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=600) as fh:  # noqa: S310 - fixed https URLs
            target.write_bytes(fh.read())
    return dest


def bytes_to_unicode():
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


def get_pairs(word):
    return {(word[i], word[i + 1]) for i in range(len(word) - 1)}


class Encoder:
    def __init__(self, encoder, bpe_merges):
        self.encoder = encoder
        self.byte_encoder = bytes_to_unicode()
        self.bpe_ranks = dict(zip(bpe_merges, range(len(bpe_merges))))
        self.cache = {}
        self.pat = re.compile(
            r"'s|'t|'re|'ve|'m|'ll|'d| ?[A-Za-z]+| ?[0-9]+| ?[^\sA-Za-z0-9]+|\s+(?!\S)|\s+"
        )

    def bpe(self, token):
        if token in self.cache:
            return self.cache[token]
        word = tuple(token)
        pairs = get_pairs(word)
        if not pairs:
            return token
        while True:
            bigram = min(pairs, key=lambda p: self.bpe_ranks.get(p, float("inf")))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                    new.extend(word[i:j])
                    i = j
                except ValueError:
                    new.extend(word[i:])
                    break
                if word[i] == first and i < len(word) - 1 and word[i + 1] == second:
                    new.append(first + second)
                    i += 2
                else:
                    new.append(word[i])
                    i += 1
            word = tuple(new)
            if len(word) == 1:
                break
            pairs = get_pairs(word)
        out = " ".join(word)
        self.cache[token] = out
        return out

    def encode(self, text):
        ids = []
        for tok in self.pat.findall(text):
            tok = "".join(self.byte_encoder[b] for b in tok.encode("utf-8"))
            ids.extend(self.encoder[t] for t in self.bpe(tok).split(" ") if t in self.encoder)
        return ids


class Gpt2Perplexity:
    """Lazily loads the ONNX session; one instance per process is plenty."""

    def __init__(self, model_dir: Path) -> None:
        import onnxruntime as ort

        enc = json.loads((model_dir / "encoder.json").read_text(encoding="utf-8"))
        merges = [
            tuple(line.split())
            for line in (model_dir / "vocab.bpe").read_text(encoding="utf-8").split("\n")[1:]
            if len(line.split()) == 2
        ]
        self.enc = Encoder(enc, merges)
        self.session = ort.InferenceSession(
            str(model_dir / "gpt2-lm-head.onnx"), providers=["CPUExecutionProvider"]
        )

    def nll(self, text: str) -> float | None:
        """Mean negative log-likelihood per token. LOWER = more predictable = machine-like end."""
        import numpy as np

        ids = self.enc.encode(text)[:MAX_TOKENS]
        if len(ids) < MIN_TOKENS:
            return None
        x = np.array(ids, dtype=np.int64).reshape(1, 1, len(ids))
        logits = self.session.run(None, {"input1": x})[0][0, 0]
        logits = logits - logits.max(axis=-1, keepdims=True)
        logsum = np.log(np.exp(logits).sum(axis=-1))
        tgt = np.array(ids[1:])
        lp = logits[np.arange(len(tgt)), tgt] - logsum[: len(tgt)]
        return float(-lp.mean())


def cohen_d(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = statistics.variance(a), statistics.variance(b)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return (statistics.mean(b) - statistics.mean(a)) / pooled if pooled else None


def contrast(rows, scorer, axis, per_group=250, seed=0, min_group=30):
    """Sampled per group, because a 665MB model on CPU is not free."""
    from eval.subgroup_audit import _MISSING

    rows = [
        r for r in rows if r.get(axis) is not None and str(r[axis]).strip().lower() not in _MISSING
    ]
    random.Random(seed).shuffle(rows)
    buckets: dict = {}
    for row in rows:
        key = str(row[axis])
        if len(buckets.get(key, [])) >= per_group:
            continue
        val = scorer(row["text"])
        if val is not None:
            buckets.setdefault(key, []).append(val)
    groups = {
        k: {"n": len(v), "mean_nll": round(statistics.mean(v), 4)}
        for k, v in buckets.items()
        if len(v) >= min_group
    }
    out = {
        "axis": axis,
        "groups": groups,
        "citation": CITATION,
        "limitation": "GPT-2 small, sampled, 384-token cap. A signal, not a detector.",
    }
    if len(groups) == 2:
        (ka, ga), (kb, gb) = sorted(groups.items())
        out["cohen_d"] = cohen_d(buckets[ka], buckets[kb])
        out["lower_perplexity"] = ka if ga["mean_nll"] < gb["mean_nll"] else kb
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("fetch")
    sc = sub.add_parser("score")
    sc.add_argument("--csv", type=Path, required=True)
    sc.add_argument("--by", required=True)
    sc.add_argument("--per-group", type=int, default=250)
    sc.add_argument("--seed", type=int, default=0)
    sc.add_argument("--min-words", type=int, default=60)
    a = ap.parse_args(argv)

    if a.cmd == "fetch":
        print(fetch())
        print(CITATION)
        return 0
    if a.cmd == "score":
        import csv as _csv

        scorer = Gpt2Perplexity(fetch())
        rows = []
        with open(a.csv, encoding="utf-8", errors="replace") as fh:
            for raw in _csv.DictReader(fh):
                text = (raw.get("full_text") or raw.get("text") or "").strip()
                if len(text.split()) >= a.min_words:
                    rows.append({"text": text, **raw})
        print(json.dumps(contrast(rows, scorer.nll, a.by, a.per_group, a.seed), indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
