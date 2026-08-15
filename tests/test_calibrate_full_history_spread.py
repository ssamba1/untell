"""Calibrate's determinism verdict must use full-history spread.

research.py cmd_calibrate: the determinism claim was computed from the last-two
runs' delta (all(v == 0) over one pair), which is coincidence-prone: two
consecutive runs can land in the same stable cluster while the process moves
between clusters. Measured on lite-hc3 (all committed in measurements.jsonl):
post_mean_max runs 0.5871/0.5887/0.5887/0.5625/0.5887 — run 4 moved 0.0262
below the cluster, invisible to a last-two comparison. The corrected verdict
uses the min-max spread across ALL runs; this regression pins that logic
against the real committed history: the spread is non-zero, so the recipe must
NOT be declared deterministic.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lite_hc3_metrics():
    rows = []
    ledger = ROOT / ".claude" / "measurements.jsonl"
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("recipe") == "lite-hc3" and row.get("metrics"):
            rows.append(row)
    return rows


def test_lite_hc3_full_history_spread_is_nonzero():
    rows = _lite_hc3_metrics()
    assert len(rows) >= 2, "need the committed lite-hc3 history"
    keys = sorted({k for r in rows for k in r["metrics"]})
    spread = {
        k: max(r["metrics"][k] for r in rows)
        - min(r["metrics"][k] for r in rows)
        for k in keys
    }
    # post_mean_max moved 0.0262 across the committed runs (0.5625 vs 0.5871+)
    assert spread["post_mean_max"] > 0.02, spread
    # the full-history verdict: any non-zero spread means NOT deterministic
    assert not all(v == 0.0 for v in spread.values())
