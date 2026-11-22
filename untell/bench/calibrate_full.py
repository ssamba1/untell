"""Fit untell's full-tier verdict on one human corpus; report it on others.

The shipped full-tier verdict was ``max(detector scores) >= 0.30``. Audited by its own report card
it flagged 57% of 394 human essays (92% of TOEFL essays by non-native writers) and 65% of pre-2022
PEPs. The cause is visible in the per-detector scores: the five detectors live on different
scales, and one of them (MAGE) gives a median of 1.000 to pre-2022 human technical prose, so the
max is decided by whichever member is most miscalibrated on the register at hand.

This module puts every detector on the same scale — its own distribution on known-human text —
and aggregates there:

1. For each detector, the empirical CDF of its scores on the FIT corpus (human only). A score's
   calibrated value is its mid-rank percentile: the share of fit documents scoring below it, plus
   half the share tied with it. A detector that gives most humans 1.000 therefore maps 1.000 to a
   middling percentile, and stops deciding verdicts on its own.
2. The aggregate is the highest calibrated percentile across detectors.
3. The cut is the aggregate's (1 - target_fpr) quantile on the fit corpus.

It is then evaluated, untouched, on corpora the fit never saw. Whatever those numbers are is what
gets published; the cut is not adjusted after looking at them.

    python -m untell.bench.calibrate_full scores.json --fit fit_capsule.jsonl \\
        --eval peps_capsule.jsonl --eval corpus.jsonl --target-fpr 0.05 --out calibration.json
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from untell.evidence.stats import auroc, wilson_interval

QUANTILES = 201  # points stored per detector: enough resolution, small enough to ship


def _percentile(sorted_xs: list[float], x: float) -> float:
    n = len(sorted_xs)
    lo = bisect.bisect_left(sorted_xs, x)
    hi = bisect.bisect_right(sorted_xs, x)
    return (lo + 0.5 * (hi - lo)) / n


def fit(rows: list[dict], target_fpr: float) -> dict:
    """Calibration from human-only fit rows: ``{"detectors": {name: [q0..q200]}, "cut": float}``."""
    by_det: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for k, v in r["det"].items():
            if v is not None and v == v:
                by_det[k].append(float(v))
    tables = {}
    for k, xs in by_det.items():
        xs.sort()
        tables[k] = [xs[min(len(xs) - 1, round(i * (len(xs) - 1) / (QUANTILES - 1)))]
                     for i in range(QUANTILES)]
    cal = {"detectors": tables, "cut": None, "target_fpr": target_fpr, "fit_n": len(rows)}
    agg = sorted(aggregate(r["det"], cal) for r in rows)
    k = math.ceil((1 - target_fpr) * len(agg)) - 1
    cal["cut"] = math.nextafter(agg[max(0, min(len(agg) - 1, k))], math.inf)
    return cal


def calibrated(name: str, score: float, cal: dict) -> float | None:
    table = cal["detectors"].get(name)
    if table is None or score is None or score != score:
        return None
    return _percentile(table, float(score))


def aggregate(scores: dict, cal: dict) -> float:
    vals = [calibrated(k, v, cal) for k, v in scores.items()]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else 0.0


def evaluate(rows: list[dict], cal: dict, old_threshold: float = 0.30) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("group", "")].append(r)

    def rate(rs: list[dict], key) -> dict:
        k = sum(1 for r in rs if key(r))
        lo, hi = wilson_interval(k, len(rs)) if rs else (None, None)
        return {"k": k, "n": len(rs), "rate": k / len(rs) if rs else None, "ci95": [lo, hi]}

    def new(r):
        return aggregate(r["det"], cal) >= cal["cut"]

    def old(r):
        vals = [v for v in r["det"].values() if v is not None]
        return bool(vals) and max(vals) >= old_threshold

    out = {"groups": {}}
    for g, rs in sorted(groups.items()):
        out["groups"][g] = {"label": rs[0].get("label", "human"),
                            "old": rate(rs, old), "new": rate(rs, new)}
    hum = [r for r in rows if r.get("label", "human") == "human"]
    ai = [r for r in rows if r.get("label") == "ai"]
    if hum:
        out["human"] = {"old": rate(hum, old), "new": rate(hum, new)}
    if ai:
        out["ai_recall"] = {"old": rate(ai, old), "new": rate(ai, new)}
        out["auroc_new_aggregate"] = auroc([aggregate(r["det"], cal) for r in ai],
                                           [aggregate(r["det"], cal) for r in hum])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.calibrate_full",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("scores", help="per-detector scores JSON: {corpus file name: [rows]}")
    ap.add_argument("--fit", required=True, help="corpus file name (key in scores) to fit on")
    ap.add_argument("--eval", action="append", default=[], help="corpus to evaluate on (repeatable)")
    ap.add_argument("--target-fpr", type=float, default=0.05)
    ap.add_argument("--out", help="write the calibration (detectors + cut) here")
    args = ap.parse_args(argv)
    data = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    fit_rows = [r for r in data[Path(args.fit).name] if r.get("label", "human") == "human"]
    cal = fit(fit_rows, args.target_fpr)
    report = {"fit": Path(args.fit).name, "cut": cal["cut"], "target_fpr": args.target_fpr,
              "fit_check": evaluate(fit_rows, cal), "eval": {}}
    for e in args.eval:
        report["eval"][Path(e).name] = evaluate(data[Path(e).name], cal)
    if args.out:
        Path(args.out).write_text(json.dumps(cal, indent=1) + "\n", encoding="utf-8")
    json.dump(report, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
