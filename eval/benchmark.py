"""Run the untell benchmark: compare noop / single_pass / full_loop on a dataset.

    python -m eval.benchmark --dataset builtin --n 5
    python -m eval.benchmark --dataset hc3 --n 100 --threshold 0.3

Success criterion (the report's thesis): ``full_loop`` reaches a higher bypass rate than
``single_pass`` at equal-or-better semantic similarity. With only the lite tier installed the
absolute numbers are weak (heuristic detector), but the *relative* comparison is what the harness
is built to show; install ``.[full]`` for meaningful absolute bypass rates.
"""

from __future__ import annotations

import argparse

from eval.baselines import STRATEGIES
from eval.datasets import load_samples
from eval.report import render


def run(dataset: str, n: int, tier: str, threshold: float, strategies: list[str]) -> dict[str, list]:
    samples = load_samples(dataset, n)
    by_strategy: dict[str, list] = {}
    for name in strategies:
        fn = STRATEGIES[name]
        results = []
        for text in samples:
            results.append(fn(text, tier=tier, threshold=threshold))
        by_strategy[name] = results
    return by_strategy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.benchmark", description=__doc__)
    parser.add_argument("--dataset", default="builtin", help="builtin | hc3 | raid")
    parser.add_argument("--n", type=int, default=5, help="number of samples")
    parser.add_argument("--tier", default="lite", choices=["lite", "full", "heavy"])
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument(
        "--strategies",
        default="noop,single_pass,full_loop",
        help="comma-separated subset of: noop, single_pass, full_loop",
    )
    parser.add_argument("--out", help="write the markdown report to this path")
    parser.add_argument(
        "--enable-radar",
        action="store_true",
        help="include RADAR (paraphrase-robust, the hardest open detector) — requires --tier full and "
        "the model download; RADAR is non-commercial licensed (research/eval only).",
    )
    args = parser.parse_args(argv)

    if args.enable_radar:
        import os

        os.environ["UNTELL_ENABLE_RADAR"] = "1"

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    unknown = [s for s in strategies if s not in STRATEGIES]
    if unknown:
        parser.error(f"unknown strategy/strategies: {', '.join(unknown)} (choose from {', '.join(STRATEGIES)})")
    by_strategy = run(args.dataset, args.n, args.tier, args.threshold, strategies)
    report = render(by_strategy, args.threshold)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
