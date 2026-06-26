"""Per-sentence AI scoring — find the exact sentences a detector flags.

The closed loop is far more efficient when it rewrites only the sentences that read as AI, instead of
re-rolling the whole paragraph (demonstrated live: ZeroGPT flagged an aphoristic closer + opener; fixing
just those took a stuck 35% to 0%). This module scores each sentence and returns the flagged ones, which
the rewriter then targets.

    untell-sentences "Your paragraph here." --tier lite
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.score import DEFAULT_THRESHOLD, score_text

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def score_sentences(
    text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD, top: int | None = None
) -> dict:
    """Score each sentence; flag the WORST ones to rewrite first.

    Per-sentence scores are noisy — short sentences especially, where signals like burstiness are
    undefined — so this targets the worst sentences **relative to the rest** (capped) rather than
    every sentence over an absolute threshold, which floods short text with false positives. The
    ``flagged`` list is "rewrite these first", not an absolute per-sentence verdict.
    """
    sents = split_sentences(text)
    scored = [(s, float(score_text(s, tier=tier, threshold=threshold)["max"])) for s in sents]
    n = len(scored)
    if top is None:
        top = max(1, (n + 2) // 3)  # the worst ~third, at least one
    # Rank by score (desc); flag the worst `top` that are also at/above threshold.
    order = sorted(range(n), key=lambda i: scored[i][1], reverse=True)
    flag_idx = {i for i in order[:top] if scored[i][1] >= threshold}
    rows: list[dict] = []
    flagged: list[str] = []
    for i, (s, ai) in enumerate(scored):
        is_flagged = i in flag_idx
        rows.append({"text": s, "ai": round(ai, 4), "flagged": is_flagged})
        if is_flagged:
            flagged.append(s)
    return {
        "tier": tier,
        "threshold": threshold,
        "sentences": rows,
        "flagged": flagged,
        "note": "per-sentence scores are noisy (esp. short sentences); 'flagged' = the worst "
        "sentences to rewrite first, not an absolute verdict",
    }


def main(argv: list[str] | None = None) -> int:
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    parser = argparse.ArgumentParser(prog="untell-sentences", description="Per-sentence AI scoring.")
    parser.add_argument("text", nargs="?")
    parser.add_argument("--file", "-f")
    parser.add_argument("--tier", default="lite", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Flag at most this many of the worst sentences (default: ~the worst third).",
    )
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

    result = score_sentences(text, tier=args.tier, threshold=args.threshold, top=args.top)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        for row in result["sentences"]:
            mark = "AI " if row["flagged"] else "ok "
            print(f"[{mark}{row['ai']:.2f}] {row['text']}")
        print(f"\n{len(result['flagged'])}/{len(result['sentences'])} sentences flagged to rewrite first.")
        print(f"note: {result['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
