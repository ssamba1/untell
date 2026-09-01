"""A real perplexity signal, with no model download and no HuggingFace.

untell's lite tier calls its first channel "perplexity" and computes the fraction of tokens that
appear in a 120-word stoplist. MEASURED 2026-09-01, those two things point in OPPOSITE directions
on learner writing: the stoplist ratio flags less-proficient writers, and actual perplexity flags
more-proficient ones. The proxy is not a stand-in for the thing it is named after, and nothing in
the repository could previously tell you that, because measuring it needed a language model and
every route to one was assumed to be a model download.

It is not. NLTK's corpora are served from raw.githubusercontent.com, which is reachable where
huggingface.co is not, and two million tokens is enough to build an interpolated bigram model that
answers the question. This module is that model:

    python -m eval.ngram_lm train --out ~/.cache/untell-corpora/ngram_lm.pkl
    python -m eval.ngram_lm score --csv essays.csv --by ell_status

MEASURED with it, mean log-perplexity, lower = more predictable = the machine-like end:

    ELLIPSE   low proficiency 6.5816   high proficiency 6.4406   d -0.320
    ASAP      ELL             7.0837   non-ELL          6.8778   d -0.491

**What this is not.** It is a bigram model over 1961 American English and newswire, so it is a
weak language model and a domain mismatch with school essays. It is not a detector and must not be
used as one. Its entire job is to be a perplexity signal honest enough to check a proxy against,
and it is reported with that limitation attached wherever it is quoted.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import pickle
import re
import sys
import urllib.request
from pathlib import Path

# Reachable where HuggingFace is not. These are the corpora, not models: an LM built from public
# text is the one route to a perplexity number that survives an egress policy.
NLTK_BASE = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora"
DEFAULT_CORPORA = ("brown", "reuters")
CITATION = (
    "Language model trained on the NLTK Brown Corpus (Francis & Kucera 1979) and Reuters-21578. "
    "Fetched from https://github.com/nltk/nltk_data"
)

_WORD = re.compile(r"[a-z']+")
# Brown ships word/TAG pairs; the tag is not part of the language.
_TAG = re.compile(r"/[^\s]+")
# Weight on the bigram in the interpolation. 0.7 is conventional and was not tuned on the essay
# corpora -- tuning it there would let the LM learn the thing it is supposed to measure.
LAMBDA = 0.7
MIN_TOKENS = 10


def _cache_dir() -> Path:
    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return Path(base)


def fetch_corpora(names: tuple[str, ...] = DEFAULT_CORPORA, dest: Path | None = None) -> Path:
    import zipfile

    dest = dest or (_cache_dir() / "nltk")
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        if (dest / name).exists():
            continue
        url = f"{NLTK_BASE}/{name}.zip"
        print(f"fetching {url}", file=sys.stderr)
        blob = urllib.request.urlopen(url, timeout=180).read()  # noqa: S310 - fixed https base
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as zf:
            zf.extractall(dest)
    return dest


def train(corpora_dir: Path, patterns: tuple[str, ...] = ("brown/c*", "reuters/training/*")) -> dict:
    """Counts, not probabilities. Smoothing happens at scoring time so the model stays inspectable."""
    uni: collections.Counter = collections.Counter()
    bi: collections.Counter = collections.Counter()
    ntok = 0
    files: list[str] = []
    for pat in patterns:
        files += glob.glob(str(corpora_dir / pat))
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        words = ["<s>", *_WORD.findall(_TAG.sub(" ", text).lower())]
        if len(words) < 3:
            continue
        uni.update(words)
        ntok += len(words)
        bi.update(zip(words, words[1:]))
    return {"uni": dict(uni), "bi": dict(bi), "ntok": ntok, "V": len(uni), "files": len(files)}


class NgramLM:
    """Interpolated bigram/unigram with add-1 unigram backoff."""

    def __init__(self, model: dict) -> None:
        self.uni = model["uni"]
        self.bi = model["bi"]
        self.ntok = model["ntok"]
        self.V = model["V"]

    @classmethod
    def load(cls, path: Path) -> NgramLM:
        with open(path, "rb") as fh:
            return cls(pickle.load(fh))

    def log_perplexity(self, text: str) -> float | None:
        """Mean negative log-likelihood per token. LOWER = more predictable = more machine-like."""
        words = ["<s>", *_WORD.findall(text.lower())]
        if len(words) < MIN_TOKENS:
            return None
        total = 0.0
        n = 0
        for a, b in zip(words, words[1:]):
            p_uni = (self.uni.get(b, 0) + 1) / (self.ntok + self.V)
            count_a = self.uni.get(a, 0)
            p_bi = (self.bi.get((a, b), 0) / count_a) if count_a else 0.0
            total -= math.log(LAMBDA * p_bi + (1 - LAMBDA) * p_uni)
            n += 1
        return total / n if n else None


def cohen_d(a: list[float], b: list[float]) -> float | None:
    """Standardised mean difference, b minus a. None when either arm cannot support a variance."""
    import statistics

    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = statistics.variance(a), statistics.variance(b)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    if pooled == 0:
        return None
    return (statistics.mean(b) - statistics.mean(a)) / pooled


def contrast(rows: list[dict], lm: NgramLM, axis: str, min_group: int = 30) -> dict:
    """Mean log-perplexity per group, and which group looks more machine-like."""
    import statistics

    from eval.subgroup_audit import _MISSING

    buckets: dict[str, list[float]] = {}
    for row in rows:
        value = row.get(axis)
        if value is None or str(value).strip().lower() in _MISSING:
            continue
        lp = lm.log_perplexity(row["text"])
        if lp is not None:
            buckets.setdefault(str(value), []).append(lp)
    groups = {k: {"n": len(v), "mean_log_perplexity": round(statistics.mean(v), 4)}
              for k, v in buckets.items() if len(v) >= min_group}
    out: dict = {"axis": axis, "groups": groups, "citation": CITATION}
    if len(groups) == 2:
        (ka, ga), (kb, gb) = sorted(groups.items())
        out["cohen_d"] = cohen_d(buckets[ka], buckets[kb])
        out["lower_perplexity"] = (ka if ga["mean_log_perplexity"] < gb["mean_log_perplexity"]
                                   else kb)
        out["reading"] = (f"{out['lower_perplexity']} is more predictable to this LM, i.e. the "
                          f"more machine-like end of the signal")
    out["limitation"] = ("bigram LM over 1961 American English and newswire; a weak model and a "
                         "domain mismatch with student essays. A perplexity SIGNAL, not a detector.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    t = sub.add_parser("train")
    t.add_argument("--out", type=Path, default=_cache_dir() / "ngram_lm.pkl")
    sc = sub.add_parser("score")
    sc.add_argument("--csv", type=Path, required=True)
    sc.add_argument("--model", type=Path, default=_cache_dir() / "ngram_lm.pkl")
    sc.add_argument("--by", required=True)
    sc.add_argument("--min-words", type=int, default=60)
    a = ap.parse_args(argv)

    if a.cmd == "train":
        corpora = fetch_corpora()
        model = train(corpora)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "wb") as fh:
            pickle.dump(model, fh)
        print(f"{model['ntok']:,} tokens, {model['V']:,} types, {len(model['bi']):,} bigrams "
              f"from {model['files']} files -> {a.out}")
        print(CITATION)
        return 0
    if a.cmd == "score":
        import csv as _csv

        lm = NgramLM.load(a.model)
        rows = []
        with open(a.csv, encoding="utf-8", errors="replace") as fh:
            for raw in _csv.DictReader(fh):
                text = (raw.get("full_text") or raw.get("text") or "").strip()
                if len(text.split()) >= a.min_words:
                    rows.append({"text": text, **raw})
        print(json.dumps(contrast(rows, lm, a.by), indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
