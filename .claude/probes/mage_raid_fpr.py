"""Issue #21 (wave 6, slice 9): regression probe pinning mage-on-RAID human FPR.

README's heavy-tier note (2026-08-11) claims `mage`'s human false-positive rate at
threshold 0.30 on RAID is 0%. Wave-3 slice 11 measured 0.1667 (5/30) on the same load
path. This probe re-pins the measurement so a regression back to the 0% claim is
caught, and records which human docs get flagged.

Uses the EXACT load path of `eval.detector_audit --pairs N --dataset raid` —
`eval.datasets.load_pairs` plus `collapse_layout` — so the figure sits on the same
corpus selection the shipped claim comes from. NO thresholds are changed (threshold
moves are RED per the envelope). The README row itself is a published number and is RED:
this probe only MEASURES and PINS; the README edit is queued for a human.

Deliverables:
  - pin: mage RAID human FPR@0.30 == 0.1667 (5/30) at n=30, layout collapsed.
  - domain attribution: the 5 flagged human docs (all deep-learning/image-segmentation).

Usage:
    python .claude/probes/mage_raid_fpr.py [--pairs 30] [--json] > pin.json
Exit 0 when the pin reproduces; non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Running this file as a script auto-adds its own directory (.claude/probes/) to
# sys.path[0]. eval/datasets._raid_pairs does `from datasets import load_dataset`,
# which would then resolve to the fleet self-test probe .claude/probes/datasets.py
# (no load_dataset attribute -> ImportError -> false "needs .[eval] extra" fallback).
# Strip the probes dir so the real `datasets` package from the venv resolves.
sys.path = [p for p in sys.path if "probes" not in p.lower()]

from eval.datasets import load_pairs  # noqa: E402
from eval.detector_audit import collapse_layout  # noqa: E402
from untell.scripts.score import DEFAULT_THRESHOLD  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="emit JSON payload")
    args = ap.parse_args()
    n = args.pairs

    from untell.detectors.mage import MageDetector

    det = MageDetector()
    if not det.available():
        print("mage unavailable in this environment", file=sys.stderr)
        return 2

    pairs = load_pairs("raid", n)
    if not pairs:
        print("raid pairs did not load", file=sys.stderr)
        return 3

    humans = [collapse_layout(h) for h, _ in pairs]
    ais = [collapse_layout(a) for _, a in pairs]
    hs = [x for x in (det.score(t) for t in humans) if isinstance(x, (int, float))]
    as_ = [x for x in (det.score(t) for t in ais) if isinstance(x, (int, float))]
    if len(hs) != n or len(as_) != n:
        print(f"score mismatch: {len(hs)} human / {len(as_)} ai (expected {n})", file=sys.stderr)
        return 4

    fpr = sum(1 for h in hs if h >= DEFAULT_THRESHOLD) / len(hs)
    tpr = sum(1 for a in as_ if a >= DEFAULT_THRESHOLD) / len(as_)
    # Pinned measurement (wave-3 slice 11 + this slice): 5 of 30 human RAID docs
    # flagged at the 0.30 threshold — deep-learning / image-segmentation abstracts,
    # mage's training genre. README's "RAID 0%" does NOT reproduce.
    pin_flagged = 5 if n == 30 else None
    flagged_idxs = [i for i, s in enumerate(hs) if s >= DEFAULT_THRESHOLD]

    out = {
        "probe": "mage_raid_fpr",
        "issue": 21,
        "threshold": DEFAULT_THRESHOLD,
        "n": n,
        "load_path": "eval.datasets.load_pairs('raid', n) + collapse_layout",
        "fpr": round(fpr, 4),
        "tpr": round(tpr, 4),
        "flagged_n": len(flagged_idxs),
        "pin": f"FPR@{DEFAULT_THRESHOLD} == 0.1667 (5/30) on RAID human text at n=30, layout collapsed",
        "flagged_human_idxs": flagged_idxs,
        "human_scores": [round(x, 6) for x in hs],
        "reads": "README heavy-tier note claims RAID FPR 0%; this probe reproduces 5/30 (0.1667).",
    }

    ok = True
    if pin_flagged is not None:
        if len(flagged_idxs) != pin_flagged:
            ok = False
            print(
                f"PIN FAILED: expected {pin_flagged} flagged, got {len(flagged_idxs)} "
                f"(FPR={fpr:.4f})",
                file=sys.stderr,
            )
        else:
            print(
                f"PIN OK: {len(flagged_idxs)}/{n} human RAID docs flagged "
                f"at {DEFAULT_THRESHOLD} (FPR={fpr:.4f}) — matches 0.1667, not 0%.",
                file=sys.stderr,
            )

    print(json.dumps(out, indent=2))
    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
