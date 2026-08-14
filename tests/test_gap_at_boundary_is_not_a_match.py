"""A gap EXACTLY at the 0.25 boundary is not a match.

voice.py:228: `if abs(gap) < 0.25: return "matches"` — only gaps BELOW 0.25 are
matches. The mutation < -> <= turns a gap of exactly 0.25 (the documented
boundary) into "matches", hiding a real between-author distance. Pure function.
"""
from untell.scripts.voice import _describe


def test_gap_at_boundary_is_not_a_match():
    assert _describe(0.25, "burst") != "matches"
    assert "more varied rhythm" in _describe(0.25, "burst")


def test_gap_below_boundary_is_a_match():
    assert _describe(0.24, "burst") == "matches"
