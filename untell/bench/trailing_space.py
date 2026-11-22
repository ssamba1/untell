"""Does one trailing space change a detector's verdict? Measured over a whole corpus.

For every document: score the text with trailing horizontal whitespace removed, then the same text
plus one space. Same words, same characters a reader can see. Run against ``raw:<detector>``
scorers (the model as an un-hardened deployment runs it, without untell's input normalisation).

    python -m untell.bench.trailing_space liang-2023/corpus.jsonl --detector hc3_roberta \\
        --detector roberta_openai --out trailing-space.json

Written after a single human TOEFL essay went from 0.9098 to 0.0010 on hc3_roberta when one
space was appended (docs/observatory/trailing-space.md has the population result).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from untell.evidence.corpus import load_corpus
from untell.evidence.scorers import resolve_scorer
from untell.evidence.stats import auroc, wilson_interval


def measure(docs: list[dict], detector: str, threshold: float = 0.5, progress=None) -> list[dict]:
    sc = resolve_scorer(f"raw:{detector}", threshold)
    rows = []
    for i, d in enumerate(docs):
        text = d["text"].rstrip(" \t")
        rows.append({"id": d["id"], "group": d.get("group", ""), "label": d["label"],
                     "words": len(text.split()),
                     "orig": sc.verdict(text).score, "trailing_space": sc.verdict(text + " ").score})
        if progress:
            progress(detector, i + 1, len(docs))
    return rows


def summarise(rows: list[dict], threshold: float = 0.5) -> dict:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["orig"] is not None and r["trailing_space"] is not None:
            by[r["group"]].append(r)
    groups = {}
    for g, rs in sorted(by.items()):
        n = len(rs)
        flagged = [r for r in rs if r["orig"] >= threshold]
        flips = [r for r in rs if (r["orig"] >= threshold) != (r["trailing_space"] >= threshold)]
        groups[g] = {
            "n": n, "label": rs[0]["label"],
            "flagged_original": len(flagged),
            "flagged_with_trailing_space": sum(1 for r in rs if r["trailing_space"] >= threshold),
            "verdict_flips": len(flips),
            "flip_rate_among_flagged": (sum(1 for r in flips if r["orig"] >= threshold) / len(flagged)
                                        if flagged else None),
            "flip_rate_ci95": list(wilson_interval(len(flips), n)) if n else None,
        }
    hum = [r for r in rows if r["label"] == "human" and r["orig"] is not None]
    ai = [r for r in rows if r["label"] == "ai" and r["orig"] is not None]
    return {
        "threshold": threshold, "groups": groups,
        "auroc_original": auroc([r["orig"] for r in ai], [r["orig"] for r in hum]),
        "auroc_both_with_trailing_space": auroc([r["trailing_space"] for r in ai],
                                                [r["trailing_space"] for r in hum]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.trailing_space",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("corpus", help="a .jsonl corpus (untell report-card format)")
    ap.add_argument("--detector", action="append", required=True,
                    help="a local detector name, scored raw (repeatable)")
    ap.add_argument("--group", action="append", help="only these groups (repeatable)")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", required=True, help="JSON file for per-document scores and summaries")
    args = ap.parse_args(argv)
    docs = load_corpus(args.corpus)
    if args.group:
        docs = [d for d in docs if d.get("group") in set(args.group)]

    def prog(det: str, i: int, n: int) -> None:
        if i % 50 == 0 or i == n:
            print(f"  {det}: {i}/{n}", file=sys.stderr, flush=True)

    result = {}
    for det in args.detector:
        rows = measure(docs, det, args.threshold, prog)
        result[det] = {"summary": summarise(rows, args.threshold),
                       "documents": [{k: v for k, v in r.items()} for r in rows]}
        Path(args.out).write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    for det, res in result.items():
        print(f"== {det}")
        for g, s in res["summary"]["groups"].items():
            print(f"  {g:32} flagged {s['flagged_original']:3} -> {s['flagged_with_trailing_space']:3}"
                  f"   flips {s['verdict_flips']}/{s['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
