"""Ensemble detector scoring — the skill's eyes on the text.

Loads every detector available at the requested tier, scores the text with each, and emits
JSON the skill (Claude) reads as feedback:

    {
      "tier": "lite",
      "detectors": {"perplexity_burstiness": 0.71, ...},
      "max": 0.71,          # the proxy the loop drives below threshold (multi-detector evasion)
      "mean": 0.71,
      "threshold": 0.30,
      "flagged": true       # max >= threshold => still looks AI, keep rewriting
    }

The ``max`` aggregation targets the hardest detector in the ensemble (report gap #3): a rewrite
only "passes" when *every* detector is under threshold.

CLI / console entry (`humanize-score`):
    humanize-score "<text>"
    humanize-score --file path.txt --tier full --threshold 0.3
    echo "text" | humanize-score
"""

from __future__ import annotations

import argparse
import json
import sys

from humanize.detectors.base import load_detectors, resolved_tier

DEFAULT_THRESHOLD = 0.30


def score_text(text: str, tier: str = "full", threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Score ``text`` with the available detector ensemble; return the result dict."""
    detectors = load_detectors(tier)
    scores: dict[str, float] = {}
    for d in detectors:
        try:
            scores[d.name] = round(float(d.score(text)), 4)
        except Exception as exc:  # a flaky detector must not crash the loop
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = str(exc)[:120]  # type: ignore[assignment]

    numeric = [v for v in scores.values() if isinstance(v, (int, float))]
    mx = max(numeric) if numeric else 0.5
    mean = sum(numeric) / len(numeric) if numeric else 0.5
    return {
        "tier": resolved_tier(detectors),
        "detectors": scores,
        "max": round(mx, 4),
        "mean": round(mean, 4),
        "threshold": threshold,
        "flagged": mx >= threshold,
    }


def _read_input(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            return fh.read()
    if args.text:
        return args.text
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="humanize-score",
        description="Score text with the local AI-detector ensemble and print JSON.",
    )
    parser.add_argument("text", nargs="?", help="Text to score (or use --file / stdin).")
    parser.add_argument("--file", "-f", help="Read text from this file.")
    parser.add_argument(
        "--tier",
        default="full",
        choices=["lite", "full", "heavy"],
        help="Max detector tier to attempt; auto-degrades to what is installed (default: full).",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Max-proxy P(AI) below which text is considered human-passing (default: {DEFAULT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    text = _read_input(args)
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = score_text(text, tier=args.tier, threshold=args.threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
