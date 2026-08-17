"""Slice 10 (wave 6, issue #22): render + extend mage calibration evidence.

Reads the sweep JSON produced by mage_calib_sweep.py and renders the
per-corpus decision table for issue #22 (mage shipped cut sits inside the
human upper mode). Resolution matters: the shipped sweep samples cuts at 0.01
granularity, which is far too coarse to see the gap between the human upper
mode (~0.9995..0.99998 on HC3) and the AI operating point (~0.999987). This
renderer re-derives cuts at the resolution of the actual score columns so the
"cut for FPR<=20%" is the true smallest cut, and prints the full FPR/TPR
trade-off table across fine candidate cuts.

NO THRESHOLDS ARE CHANGED — analysis only; the recommendation is queued (RED).

Usage:
    python .claude/probes/mage_calib_analyze.py evidence/mage_calib_sweep_20260817.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def fpr_tpr(hs: list[float], as_: list[float], cut: float) -> tuple[float, float]:
    fpr = sum(1 for h in hs if h >= cut) / len(hs)
    tpr = sum(1 for a in as_ if a >= cut) / len(as_)
    return fpr, tpr


def smallest_cut_fpr_le(hs: list[float], as_: list[float], max_fpr: float):
    """True smallest cut (between distinct scores) with FPR <= max_fpr.

    Enumerate every distinct human score as the cut (score >= cut flags that
    doc), plus a hair above the highest human score (FPR 0). Pick the cut with
    FPR <= max_fpr that maximizes TPR; ties prefer the higher cut (lower FPR).
    """
    distinct = sorted(hs)
    cutset = distinct + [distinct[-1] + 1e-6]
    best = None
    for c in cutset:
        fpr, tpr = fpr_tpr(hs, as_, c)
        # prefer the highest cut (lowest FPR) among those that keep full TPR,
        # then the largest TPR.
        if fpr <= max_fpr and (best is None or tpr > best[2]
                               or (tpr == best[2] and fpr < best[1])):
            best = (c, fpr, tpr)
    return best


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/mage_calib_sweep_20260817.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    corpora = data["corpora"]
    shipped = data["shipped_threshold"]
    print(f"shipped threshold: {shipped}  (measured AI op point reported per corpus)\n")

    coarse = [0.30, 0.50, 0.80, 0.83, 0.90, 0.95, 0.99, 0.999, 0.9999]
    fine = [0.9990, 0.9995, 0.9999, 0.99995, 0.99998, 0.99999]
    cand = sorted(set(coarse + fine))

    table: dict[str, dict] = {}
    for cname, r in corpora.items():
        hs = r["human_scores"]  # already sorted ascending
        as_ = r["ai_scores"]
        nocc = {"fpr20": None, "fpr10": None, "packed": None}
        print(f"== {cname}  n_human={r['n_human']} n_ai={r['n_ai']}")
        print(f"  human_mean={r['human_mean']} ai_mean={r['ai_mean']} AUROC={r['auroc']}")
        print(
            f"  shipped op: FPR@0.30={r['fpr_at_shipped_0_30']} "
            f"TPR@0.30={r['tpr_at_shipped_0_30']} "
            f"humans>=0.83:{r['human_ge_0_83']}/{r['n_human']} "
            f"humans>=0.99:{r['human_ge_0_99']}/{r['n_human']}"
        )
        op_min = min(as_) if as_ else None
        op_med = sorted(as_)[len(as_) // 2] if as_ else None
        print(f"  AI operating point: min={op_min} median={op_med}")
        # field the shipped sweep reported is the coarse 0.01-grid answer
        print(
            f"  [coarse 0.01-grid] cut(FPR<=0.20)={r['cut_for_fpr_le_0_20']} "
            f"TPR@that={r['tpr_at_fpr20_cut']}"
        )
        for maxf, key in ((0.20, "fpr20"), (0.10, "fpr10"), (0.05, "fpr05")):
            b = smallest_cut_fpr_le(hs, as_, maxf)
            if b:
                print(f"  [fine, true smallest] cut(FPR<={maxf:.2f})={b[0]:.6f} FPR={b[1]:.4f} TPR={b[2]:.4f}")
                table.setdefault(cname, {})[key] = {"cut": b[0], "fpr": b[1], "tpr": b[2]}

        print(f"  {'cut':>9} {'FPR':>7} {'TPR':>7}")
        for c in cand:
            fpr, tpr = fpr_tpr(hs, as_, c)
            print(f"  {c:>9.5f} {fpr:>7.3f} {tpr:>7.3f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
