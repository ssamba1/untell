"""Issue #40 companion: simulate the ENSEMBLE at the shipped threshold under per-detector cuts.

The loop targets a sentence when `max(detector scores) >= min_score` (min_score = 0.30,
`untell/rewriter/targeted.py`, `DEFAULT_THRESHOLD` in `untell/scripts/score.py`). The
issue-40 design replaces the single global cut with a PER-DETECTOR sentence-granularity
cut: a sentence is flagged when ANY detector's score clears ITS calibrated cut
(`OR_d score_d >= cut_d`, with every cut_d >= 0.30 so the shipped floor is never
loosened). This script simulates that on the raw per-sentence scores captured by
`calibration_sweep.py` and contrasts it with:

  * the shipped ensemble (max >= 0.30) — what the loop experiences today;
  * global threshold moves (0.35/0.40/0.45/0.50) — the RED option, shown to be wrong:
    mage's human mode sits at 0.7-1.0 so a global raise pays FPR for nothing, and the
    TPR loss lands on the detectors that actually rank (hc3_roberta, pb).

Cut rule: `cut_d(target)` = smallest t >= SHIPPED with FPR(t) <= target at 0.001
resolution (the least TPR-damaging cut meeting the FPR budget — every human sentence
above the cut is a false positive, so moving the cut above the first budget-meeting
point only costs AI recall). The sweep's conservative `t_for_fpr_*` (largest such t)
is reported alongside.

Usage: python .claude/probes/ensemble_calib_sim.py <evidence.json> [--target 0.20]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SHIPPED = 0.30
GRID = [round(i / 1000, 3) for i in range(300, 1001)]  # 0.300..1.000 at 0.001


def fpr(scores: list[float], t: float) -> float:
    return sum(1 for x in scores if x >= t) / len(scores)


def tpr(scores: list[float], t: float) -> float:
    return sum(1 for x in scores if x >= t) / len(scores)


def cut_for_fpr(human: list[float], target: float) -> tuple[float, float, float]:
    """Smallest t >= SHIPPED with FPR(t) <= target; return (cut, fpr_at_cut, tpr_at_cut)."""
    ai = None  # caller passes ai separately for tpr
    for t in GRID:
        if fpr(human, t) <= target:
            return t, fpr(human, t), 0.0
    return 1.0, fpr(human, 1.0), 0.0


def largest_t_for_fpr(human: list[float], target: float) -> float:
    uniq = sorted(set(human))
    cands = [0.0] + uniq
    for a, b in zip(uniq, uniq[1:]):
        cands.append((a + b) / 2)
    best = 0.0
    for t in cands:
        if sum(1 for x in human if x >= t) / len(human) <= target:
            best = max(best, t)
    return round(best, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence", type=Path)
    ap.add_argument("--target", type=float, default=0.20)
    args = ap.parse_args()

    ev = json.loads(args.evidence.read_text(encoding="utf-8"))
    raw = ev["raw_scores"]
    dets = [k for k in raw if raw[k].get("human") and raw[k].get("ai")]

    print(f"evidence: {args.evidence.name}  pairs={ev.get('pairs')} "
          f"max_sentences={ev.get('max_sentences')}  head={ev.get('git_head')}")
    print(f"target FPR: {args.target}   shipped ensemble floor: {SHIPPED}")
    print()

    # --- per-detector table ---------------------------------------------------
    print("PER-DETECTOR (sentence granularity)")
    print(f"{'detector':<22}{'n':>4}{'FPR@0.30':>9}{'TPR@0.30':>9}{'cut(tgt)':>9}"
          f"{'FPR@cut':>8}{'TPR@cut':>8}{'t_largest':>10}")
    cuts: dict[str, float] = {}
    for d in dets:
        h, a = raw[d]["human"], raw[d]["ai"]
        f_s, t_s = fpr(h, SHIPPED), tpr(a, SHIPPED)
        cut = None
        for t in GRID:
            if t >= SHIPPED and fpr(h, t) <= args.target:
                cut = t
                break
        cuts[d] = SHIPPED if cut is None else cut
        f_c, t_c = fpr(h, cuts[d]), tpr(a, cuts[d])
        tl = largest_t_for_fpr(h, args.target)
        print(f"{d:<22}{len(h):>4}{f_s:>9.3f}{t_s:>9.3f}{cuts[d]:>9.3f}"
              f"{f_c:>8.3f}{t_c:>8.3f}{tl:>10.4f}")

    # --- ensemble simulations -------------------------------------------------
    n_h = len(raw[dets[0]]["human"])
    n_a = len(raw[dets[0]]["ai"])

    def ens_fpr_tpr(cut_map: dict[str, float] | None, floor: float = SHIPPED) -> tuple[float, float]:
        flagged_h = flagged_a = 0
        members = list(cut_map) if cut_map is not None else dets
        for i in range(n_h):
            if cut_map is None:
                hit = max(raw[d]["human"][i] for d in members) >= floor
            else:
                hit = any(raw[d]["human"][i] >= cut_map[d] for d in members)
            flagged_h += int(hit)
        for i in range(n_a):
            if cut_map is None:
                hit = max(raw[d]["ai"][i] for d in members) >= floor
            else:
                hit = any(raw[d]["ai"][i] >= cut_map[d] for d in members)
            flagged_a += int(hit)
        return flagged_h / n_h, flagged_a / n_a

    fpr_ship, tpr_ship = ens_fpr_tpr(None, SHIPPED)
    print()
    print(f"ENSEMBLE shipped (max >= {SHIPPED}):  FPR={fpr_ship:.4f}  TPR={tpr_ship:.4f}  (n={n_h}/{n_a})")

    # contribution: who flags the human sentences at shipped, and who is the sole flagger
    print()
    print("CONTRIBUTION to shipped ensemble FPR (human sentences flagged at 0.30):")
    for d in dets:
        flags = sum(1 for x in raw[d]["human"] if x >= SHIPPED)
        others = [e for e in dets if e != d]
        exclusive = sum(
            1 for i, x in enumerate(raw[d]["human"])
            if x >= SHIPPED and not any(raw[e]["human"][i] >= SHIPPED for e in others)
        )
        print(f"  {d:<22} flags {flags:>2}/{n_h} human sents ({flags/n_h:.3f})  "
              f"sole flagger on {exclusive:>2} ({exclusive/n_h:.3f})")

    fpr_cal, tpr_cal = ens_fpr_tpr(cuts)
    print(f"ENSEMBLE calibrated cuts (OR_d score>={cuts}):  FPR={fpr_cal:.4f}  TPR={tpr_cal:.4f}")

    # contrast: global threshold moves (RED — never applied)
    print()
    print("GLOBAL THRESHOLD MOVES (contrast — RED, never applied):")
    for t in (0.35, 0.40, 0.45, 0.50):
        f, tp = ens_fpr_tpr(None, t)
        print(f"  max >= {t:.2f}:  FPR={f:.4f}  TPR={tp:.4f}")

    # exclusion variant: drop detectors whose cut keeps TPR below a floor
    print()
    for floor_tpr in (0.30, 0.50):
        keep = {d for d in dets if tpr(raw[d]["ai"], cuts[d]) >= floor_tpr}
        if keep:
            sub = {d: cuts[d] for d in keep}
            f, tp = ens_fpr_tpr(sub)
            print(f"ENSEMBLE calibrated, exclude TPR<{floor_tpr:.2f} at cut "
                  f"({sorted(keep)}):  FPR={f:.4f}  TPR={tp:.4f}")
        else:
            print(f"ENSEMBLE calibrated, exclude TPR<{floor_tpr:.2f} at cut: no detectors kept")

    return 0


if __name__ == "__main__":
    sys.exit(main())
