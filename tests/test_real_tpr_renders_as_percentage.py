"""A real TPR must render as a percentage, not the placeholder.

eval/detector_audit.py:477: `tpr = f"{r['tpr']:6.0%}" if r.get("tpr") is not
None else "     -"` — a detector with a measured TPR shows it in the table.
The mutation is not None -> is None inverts the guard: an EXISTING tpr now
takes the placeholder branch, hiding the value. The FPR/TPR columns are what
caught the two scale-miscalibrated detectors at AUROC 0.999+ (see comment).
"""
from eval.detector_audit import render

ROW = {
    "detector": "test",
    "verdict": "OK",
    "auroc": 0.9,
    "fpr": 0.1,
    "tpr": 0.75,
    "human_mean": 0.5,
    "ai_mean": 0.6,
    "gap": 0.1,
}
REPORT = {"source": "x", "results": [ROW], "broken": [], "layout_shortcut": None}


def test_real_tpr_renders_as_percentage():
    out = render(REPORT)
    line = next(x for x in out.splitlines() if "test" in x)
    assert "75%" in line, line
    assert line.rstrip().endswith("75%"), line
