"""Measure untell's inference-only evasion ceiling against the LOCAL detector ensemble.

The literature has no data point for what the training-free closed loop actually achieves: only the
~1% one-shot-style floor and the ~97% RL-trained ceiling (see docs/free-ceiling-report.md). This
script produces that missing number. It scores a corpus of AI text, runs the untell loop on each,
and reports the before/after flagged rate plus per-detector mean P(AI).

Without a rewriter configured it reports the BASELINE (pre-rewrite detection) only, which is always
runnable and still useful. With a rewriter (an API key, or one passed to ``measure_ceiling``) it
reports the full before/after delta — the actual inference-only ceiling on the local tier.

    untell-ceiling                       # built-in sample, baseline (or full delta if a key is set)
    untell-ceiling --file corpus.txt     # paragraphs separated by blank lines
    untell-ceiling --tier full --best-of 3 --json
"""

from __future__ import annotations

import argparse
import json

# Run-as-file support: put the package parent on sys.path when executed directly.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.run import untell_text
from untell.scripts.score import DEFAULT_THRESHOLD, score_text

# A few formulaic AI paragraphs (no locked facts needed; this measures detector movement).
_SAMPLE = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries in recent "
    "years. Moreover, organizations increasingly leverage these technologies to optimize operational "
    "efficiency and drive innovation. Overall, the transformative impact continues to expand across "
    "various sectors.",
    "In today's rapidly evolving digital landscape, cybersecurity has become paramount. It is important "
    "to note that organizations must navigate the complexities of an ever-changing threat environment. "
    "Ultimately, a robust and comprehensive security posture is essential for success.",
    "Climate change represents one of the most pressing challenges of our time. Notably, rising global "
    "temperatures underscore the urgent need for action. By fostering collaboration and harnessing "
    "innovative solutions, society can pave the way toward a more sustainable future.",
]


def _numeric(score: dict) -> dict:
    return {
        k: v
        for k, v in score.get("detectors", {}).items()
        if isinstance(v, (int, float)) and not k.endswith("__error")
    }


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def measure_ceiling(
    texts: list[str],
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    max_iters: int = 5,
    rewriter=None,
    best_of: int = 1,
) -> dict:
    """Score each text, run the loop, and aggregate the before/after detector movement."""
    pre_max: list[float] = []
    post_max: list[float] = []
    per_pre: dict[str, list[float]] = {}
    per_post: dict[str, list[float]] = {}
    rewrote = 0

    for t in texts:
        pre = score_text(t, tier=tier, threshold=threshold)
        pre_max.append(pre["max"])
        for k, v in _numeric(pre).items():
            per_pre.setdefault(k, []).append(v)

        res = untell_text(
            t, tier=tier, threshold=threshold, max_iters=max_iters, rewriter=rewriter, best_of=best_of
        )
        if "error" not in res and "post" in res:
            post = res["post"]
            post_max.append(post["max"])
            for k, v in _numeric(post).items():
                per_post.setdefault(k, []).append(v)
            rewrote += 1

    def flagged_rate(scores: list[float]) -> float | None:
        return round(sum(1 for s in scores if s >= threshold) / len(scores), 4) if scores else None

    return {
        "n": len(texts),
        "tier": tier,
        "threshold": threshold,
        "max_iters": max_iters,
        "best_of": best_of,
        "rewrote": rewrote,
        "rewriter_available": rewrote > 0,
        "pre_flagged_rate": flagged_rate(pre_max),
        "post_flagged_rate": flagged_rate(post_max),
        "pre_mean_max": _mean(pre_max),
        "post_mean_max": _mean(post_max),
        "per_detector_pre": {k: _mean(v) for k, v in per_pre.items()},
        "per_detector_post": {k: _mean(v) for k, v in per_post.items()} or None,
    }


def _render(r: dict) -> str:
    lines = [
        f"untell inference-only ceiling — tier={r['tier']} threshold={r['threshold']} "
        f"best_of={r['best_of']} n={r['n']}",
        "",
        f"  pre  flagged rate: {r['pre_flagged_rate']}   mean max P(AI): {r['pre_mean_max']}",
    ]
    if r["rewriter_available"]:
        lines.append(
            f"  post flagged rate: {r['post_flagged_rate']}   mean max P(AI): {r['post_mean_max']}   "
            f"(rewrote {r['rewrote']}/{r['n']})"
        )
        lines.append("")
        lines.append("  per-detector mean P(AI)  before -> after:")
        for k, before in sorted(r["per_detector_pre"].items()):
            after = (r["per_detector_post"] or {}).get(k)
            lines.append(f"    {k:24} {before} -> {after}")
    else:
        lines.append("")
        lines.append(
            "  No rewriter configured (no ANTHROPIC_API_KEY / OPENAI_API_KEY, and not in the skill) "
            "— showing BASELINE detection only. Set a key, or run inside the /untell skill where "
            "Claude is the rewriter, to measure the after-rewrite ceiling."
        )
    return "\n".join(lines)


def _read_corpus(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    blocks = [b.strip() for b in raw.split("\n\n")]
    return [b for b in blocks if b]


def main(argv: list[str] | None = None) -> int:
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(prog="untell-ceiling", description=__doc__)
    parser.add_argument("--file", "-f", help="corpus file (paragraphs separated by blank lines)")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument("--best-of", type=int, default=1)
    parser.add_argument(
        "--rewriter",
        choices=["auto", "surgical"],
        default="auto",
        help="'auto' uses a hosted-LLM rewriter if a key is set (else baseline only); 'surgical' uses "
        "the deterministic no-key word-substitution rewriter so the loop runs at $0 (free measurement).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()
    texts = _read_corpus(args.file) if args.file else _SAMPLE
    if not texts:
        print(json.dumps({"error": "empty corpus"}))
        return 2
    rewriter = None
    if args.rewriter == "surgical":
        from untell.rewriter import get_rewriter

        rewriter = get_rewriter(prefer="surgical")
    result = measure_ceiling(
        texts,
        tier=args.tier,
        threshold=args.threshold,
        max_iters=args.max_iters,
        best_of=args.best_of,
        rewriter=rewriter,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
