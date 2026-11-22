"""`score_tells` must stay linear on text made of blank lines.

Six patterns began with `^\\s*` under MULTILINE. At every line start `\\s*` swallowed all the
newlines that followed before failing, so a document of N blank lines cost O(N²): MEASURED, 2,000
newlines took 0.66 s and 100,000 roughly half an hour (tests/test_scale_ceilings.py timed out at
1,200 s). Leading HORIZONTAL whitespace (`[ \\t]*`) is what those patterns mean — `^` already
matches at each line start — and the tell counts over all 746 Liang et al. essays plus edge cases
were identical before and after. 100,000 newlines now take about 0.2 s.
"""

from __future__ import annotations

import time

from untell.scripts.tells import _CATEGORIES, _DIFF_ANCHOR_RE, score_tells


def test_blank_lines_do_not_go_quadratic():
    start = time.perf_counter()
    score_tells("\n" * 100_000)
    assert time.perf_counter() - start < 10, "score_tells is superlinear on blank lines again"


def test_no_line_anchored_pattern_lets_leading_space_cross_lines():
    for name, pat in [*_CATEGORIES, ("diff_anchor", _DIFF_ANCHOR_RE)]:
        assert r"^\s*" not in pat.pattern, f"{name}: ^\\s* under MULTILINE is O(n^2) on blank lines"
        assert r"[.!?]\s))\s*" not in pat.pattern, f"{name}: use [ \\t]* after the anchor"


def test_the_fix_still_finds_openers_after_blank_lines():
    t = score_tells("Intro sentence here.\n\n   Moreover, this still counts.\n\n# Key takeaways\n")
    assert t["by_category"].get("formulaic_transition") == 1
    assert t["by_category"].get("markdown_artifact") == 1
