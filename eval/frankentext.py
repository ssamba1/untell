"""Score text assembled from many human sources, where every word is human and the arrangement is not.

*Frankentext* ([2026.acl-long.1457](https://aclanthology.org/2026.acl-long.1457/)) has an LLM build a
long narrative from thousands of randomly sampled human snippets, roughly 90% of tokens copied
verbatim, and finds **72% of them misclassified as human-written by Pangram**. That result is not
evasion in the usual sense and no threshold fixes it: the words are human and the composition is not.

Every arm this repository audits — human, AI-assisted, machine-humanized, fully generated — assumes
authorship of the *words*. This module measures what our own stack does with text where that
assumption fails.

**The construction here is deliberately cruder than the paper's**, and the difference is the point.
Frankentexts are assembled *by an LLM* for coherence; these are assembled by `random.sample` for none
at all. So this is not a replication and cannot be read as one — it is the same input property
(human tokens, machine arrangement) with the coherence removed, which isolates whether a detector is
responding to the words or to their order.

Every snippet comes from pre-2022 publications, so **every token is human by construction** and any
verdict of "AI" is a false positive in the strictest sense this repository has available.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from eval.arms import length_match, render_length_match
from eval.pre_llm_fpr import pre_llm_abstracts, wilson_interval

_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(texts: list[str], min_words: int = 6) -> list[str]:
    out = []
    for text in texts:
        for s in _SENT.split(text):
            s = s.strip()
            if len(s.split()) >= min_words:
                out.append(s)
    return out


def stitch(pool: list[str], n_sentences: int, rng: random.Random) -> str:
    """One text, each sentence drawn from a different human document."""
    return " ".join(rng.sample(pool, min(n_sentences, len(pool))))


def probe(texts: list[str], tier: str = "lite", n: int = 60, n_sentences: int = 12,
          seed: int = 0) -> dict:
    """Flag rate for stitched text against whole documents from the same corpus.

    The comparison arm is scored at a matched word count. Without that this would measure the length
    effect — rounds thirty-six and thirty-seven — rather than anything about composition.
    """
    from untell.scripts.score import score_text

    rng = random.Random(seed)
    pool = sentences(texts)
    if len(pool) < n_sentences * 2:
        return {"error": f"only {len(pool)} sentences in the corpus; need {n_sentences * 2}"}

    stitched = [stitch(pool, n_sentences, rng) for _ in range(n)]
    target_words = sum(len(s.split()) for s in stitched) // max(len(stitched), 1)
    # Whole human documents, truncated to the stitched arm's mean length.
    whole = []
    for text in texts:
        words = text.split()
        if len(words) >= target_words:
            whole.append(" ".join(words[:target_words]))
        if len(whole) == n:
            break

    def _rate(items: list[str]) -> dict:
        hits, detectors = [], set()
        for item in items:
            result = score_text(item, tier=tier)
            if not result.get("agreement"):
                continue
            detectors.update(k for k, v in result["detectors"].items()
                             if isinstance(v, (int, float)))
            hits.append(int(bool(result["flagged"])))
        low, high = wilson_interval(sum(hits), len(hits))
        return {"n": len(hits), "flagged": sum(hits),
                "rate": round(sum(hits) / len(hits), 4) if hits else None,
                "ci95": [round(low, 4), round(high, 4)], "detectors": sorted(detectors)}

    # The shared check, not a bespoke one. `eval/arms.py` exists because this exact confound
    # produced a wrong headline in rounds thirty-six, thirty-seven and fifty, and remembering to
    # look failed all three times.
    match = length_match({"stitched": stitched, "whole": whole})
    if not match["length_matched"]:
        return {"error": f"arms are not comparable: {match['reason']}. Use fewer sentences so more "
                         f"documents reach the target length.",
                "mean_words": target_words, "length_match": match}

    a, b = _rate(stitched), _rate(whole)
    gap = (round(a["rate"] - b["rate"], 4)
           if a["rate"] is not None and b["rate"] is not None else None)
    return {
        "tier": tier, "seed": seed, "sentences_per_text": n_sentences,
        "mean_words": target_words, "length_match": match,
        "stitched": a, "whole": b, "gap": gap,
        "intervals_overlap": (
            None if gap is None
            else not (a["ci95"][0] > b["ci95"][1] or b["ci95"][0] > a["ci95"][1])),
        "note": (
            "Every token in both arms is human, from pre-2022 publications, so every flag is a "
            "false positive. The stitched arm is assembled by random sampling, NOT by an LLM for "
            "coherence as in 2026.acl-long.1457 — this isolates the effect of arrangement, and is "
            "not a replication of that paper."
        ),
    }


def _render(r: dict) -> str:
    if "error" in r:
        return f"cannot run: {r['error']}"
    lines = [
        f"Stitched human text against whole human text (tier={r['tier']}, "
        f"{r['sentences_per_text']} sentences each, ~{r['mean_words']} words).",
        "",
        render_length_match(r["length_match"]) if "length_match" in r else "",
        "",
        f"{'arm':<12} {'n':>4} {'flagged':>9}   95% CI",
    ]
    for name in ("stitched", "whole"):
        row = r[name]
        ci = f"[{row['ci95'][0]:.1%}, {row['ci95'][1]:.1%}]"
        rate = f"{row['rate']:.1%}" if row["rate"] is not None else "—"
        lines.append(f"{name:<12} {row['n']:>4} {rate:>9}   {ci}")
    if r["gap"] is not None:
        lines += ["", f"gap: {r['gap']:+.1%}",
                  ("The intervals OVERLAP, so this is not evidence that arrangement matters."
                   if r["intervals_overlap"] else
                   "The intervals do NOT overlap.")]
    if len(r["stitched"]["detectors"]) < 2:
        lines += ["", "NOTE: one detector scored; this is that detector's behaviour, not an "
                      "ensemble's."]
    lines += ["", r["note"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--sentences", type=int, default=12)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    texts = pre_llm_abstracts(args.cache)
    if not texts:
        print(f"no pre-LLM abstracts in {args.cache} — run "
              f"`python -m eval.litreview --download` first", file=sys.stderr)
        return 1
    report = probe(texts, tier=args.tier, n=args.n, n_sentences=args.sentences, seed=args.seed)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
