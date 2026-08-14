"""Killing tests for the browser_check.py mutation survivors (2026-08-14 sweep).

  line 131  constant: 24 -> 25   label-to-number association gap boundary.

Killed here. 324 (Playwright timeout constant) needs a live browser to observe —
recorded as unkillable in survivors.md.
"""

from __future__ import annotations

from untell.browser_check import parse_ai_percent


class TestLabelGapBoundary:
    """Survivor browser_check.py:131 — `_gap(...) <= 24` mutated to `<= 25`.

    A human label EXACTLY 24 characters from its number is associated (the reading
    is refused as inverted); a label 25 away is not. The mutation would associate
    the 25-gap label too, refusing a reading the parser should return."""

    def test_gap_24_associates_the_label(self) -> None:
        # "45%" ends at 3; 23 x's; space; "human" starts at 27 -> gap 24
        text = "45%" + "x" * 23 + " human"
        assert parse_ai_percent(text) is None  # refused: human-labelled reading

    def test_gap_25_does_not_associate(self) -> None:
        # 24 x's; space; "human" starts at 28 -> gap 25
        text = "45%" + "x" * 24 + " human"
        assert parse_ai_percent(text) == 0.45  # returned: label out of range
