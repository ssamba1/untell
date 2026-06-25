"""Per-sentence AI scoring — find the exact sentences a detector flags.

The closed loop is far more efficient when it rewrites only the sentences that read as AI, instead of
re-rolling the whole paragraph (demonstrated live: ZeroGPT flagged an aphoristic closer + opener; fixing
just those took a stuck 35% to 0%). This module scores each sentence and returns the flagged ones, which
the rewriter then targets.

    humanize-sentences "Your paragraph here." --tier lite
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from humanize.scripts.score import DEFAULT_THRESHOLD, score_text

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def score_sentences(text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Score each sentence; return per-sentence P(AI) and the flagged (>= threshold) sentence texts."""
    sents = split_sentences(text)
    rows = []
    flagged: list[str] = []
    for s in sents:
        ai = float(score_text(s, tier=tier, threshold=threshold)["max"])
        is_flagged = ai >= threshold
        rows.append({"text": s, "ai": round(ai, 4), "flagged": is_flagged})
        if is_flagged:
            flagged.append(s)
    return {"tier": tier, "threshold": threshold, "sentences": rows, "flagged": flagged}


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="humanize-sentences", description="Per-sentence AI scoring.")
    parser.add_argument("text", nargs="?")
    parser.add_argument("--file", "-f")
    parser.add_argument("--tier", default="lite", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = score_sentences(text, tier=args.tier, threshold=args.threshold)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        for row in result["sentences"]:
            mark = "AI " if row["flagged"] else "ok "
            print(f"[{mark}{row['ai']:.2f}] {row['text']}")
        print(f"\n{len(result['flagged'])}/{len(result['sentences'])} sentences flagged (>= {args.threshold}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
