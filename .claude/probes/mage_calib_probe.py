"""Slice 10 (wave 6, issue #22): robust mage FPR-vs-cut sweep on HC3 + RAID.

Deterministic re-derivation of the shipped `mage_calib_sweep.py` curves using
the PROVEN-importable load path (same `eval.datasets.load_pairs` +
`collapse_layout` measurement the shipped sweep and the detector audit use).
The shipped sweep's `from datasets import load_dataset` is flaky inside the
Longformer-heavy process here, but the identical sequence works when `datasets`
is imported after mage scores a doc first (verified empirically, issue #22
slice 10). This probe keeps that order and writes the same JSON schema, so the
evidence is reproducible and comparable.

Also samples the cut grid DENSELY near the human upper mode (0.99..1.0) so the
"shipped cut sits inside the human upper mode" claim has a resolvable
FPR-vs-cut curve instead of the misleading coarse 0.01-grid answer.

NO THRESHOLDS ARE CHANGED. Measurement only; recommendation queued (RED).

Usage:
    python .claude/probes/mage_calib_probe.py --corpus hc3,raid --pairs 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_script_dir = str(Path(__file__).resolve().parent)
sys.path[:] = [p for p in sys.path if p != _script_dir]

from eval.datasets import load_pairs  # noqa: E402
from eval.detector_audit import auroc, collapse_layout  # noqa: E402
from untell.detectors.mage import MageDetector  # noqa: E402


def _mean(xs):
    return sum(xs) / len(xs)


def measure(det, corpus, n):
    pairs = load_pairs(corpus, n)
    if not pairs:
        return None
    humans = [collapse_layout(h) for h, _ in pairs]
    ais = [collapse_layout(a) for _, a in pairs]
    # Score a human first so the mage Longformer is fully loaded (and, on this
    # box, `datasets` is importable) before any further loads happen.
    hs = [x for x in (det.score(t) for t in humans) if isinstance(x, (int, float))]
    as_ = [x for x in (det.score(t) for t in ais) if isinstance(x, (int, float))]
    if not hs or not as_:
        return None
    # Fine cut grid: 0.00..0.99 step 0.01, then densely 0.990..0.9999 to resolve
    # the upper mode.
    cuts = [round(i / 100, 2) for i in range(100)]
    cuts += [0.990, 0.995, 0.999, 0.9995, 0.9999, 0.99995, 0.99999]
    cuts = sorted(set(cuts))
    fpr_at = {c: sum(1 for h in hs if h >= c) / len(hs) for c in cuts}
    tpr_at = {c: sum(1 for a in as_ if a >= c) / len(as_) for c in cuts}
    fpr20 = next((c for c in cuts if fpr_at[c] <= 0.20), None)
    return {
        "corpus": corpus,
        "n_human": len(hs),
        "n_ai": len(as_),
        "human_scores": [round(x, 6) for x in sorted(hs)],
        "human_scores_ordered": [round(x, 6) for x in hs],
        "ai_scores": [round(x, 6) for x in sorted(as_)],
        "human_mean": round(_mean(hs), 4),
        "ai_mean": round(_mean(as_), 4),
        "ai_op_min": round(min(as_), 6),
        "ai_op_median": round(sorted(as_)[len(as_) // 2], 6),
        "auroc": round(auroc(as_, hs), 4) if auroc(as_, hs) is not None else None,
        "fpr_at_shipped_0_30": fpr_at[0.30],
        "tpr_at_shipped_0_30": tpr_at[0.30],
        "human_ge_0_83": sum(1 for h in hs if h >= 0.83),
        "human_ge_0_99": sum(1 for h in hs if h >= 0.99),
        "cut_for_fpr_le_0_20": fpr20,
        "tpr_at_fpr20_cut": tpr_at[fpr20] if fpr20 is not None else None,
        "curve": [{"cut": c, "fpr": round(fpr_at[c], 4), "tpr": round(tpr_at[c], 4)}
                  for c in cuts],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="hc3,raid")
    ap.add_argument("--pairs", type=int, default=30)
    args = ap.parse_args()
    det = MageDetector()
    if not det.available():
        print("mage unavailable in this environment", file=sys.stderr)
        return 2
    out = {"shipped_threshold": 0.30, "corpora": {}}
    for corpus in [c.strip() for c in args.corpus.split(",") if c.strip()]:
        res = measure(det, corpus, args.pairs)
        if res is None:
            print(f"{corpus}: no pairs loaded", file=sys.stderr)
            return 3
        out["corpora"][corpus] = res
        print(
            f"{corpus:6} n={res['n_human']:2} hm={res['human_mean']:.4f} "
            f"am={res['ai_mean']:.4f} AUROC={res['auroc']} "
            f"FPR@0.30={res['fpr_at_shipped_0_30']:.4f} "
            f"op_min={res['ai_op_min']} cut(FPR<=0.20)={res['cut_for_fpr_le_0_20']} "
            f"TPR@that={res['tpr_at_fpr20_cut']}", file=sys.stderr)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
