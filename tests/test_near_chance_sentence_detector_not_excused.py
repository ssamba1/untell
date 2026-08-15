"""A near-chance sentence detector is not excused from broken.

eval/detector_audit.py:495: `and r["auroc"] > SENTENCE_BROKEN_AUROC` — a
sentence-granularity detector with a bad verdict is excused ONLY when its
AUROC is above the small-sample bar (0.2); near-chance AUROC must count as
broken. The mutation and -> or at that position bypasses the AUROC guard
whenever auroc is present, excusing a 0.1-AUROC detector. The rendered report
gains a 'Not counted' line that must not exist.
"""
from eval.detector_audit import render

ROW = {
    "detector": "s_det",
    "verdict": "INVERTED",
    "granularity": "sentence",
    "auroc": 0.1,
}
REPORT = {"source": "x", "results": [ROW], "broken": ["s_det"], "layout_shortcut": None}


def test_near_chance_sentence_detector_is_not_excused():
    out = render(REPORT)
    assert "Not counted" not in out, "near-chance detector must stay in broken"
