"""Regression tests for three bugs found and fixed in text_split.py and layout.py.

Bug 1 (text_split) — emoji or symbol between a sentence terminator and the following space
hides the boundary from every _SENT_SPLIT alternative, collapsing two sentences into one.
MEASURED: split_sentences("Done.\U0001F389 Next.") -> ONE sentence.

Bug 2 (text_split) — "vs." followed by a capitalised word splits incorrectly because "vs" is
not in _TITLE_PREFIXES and the capital triggers the abbreviation rule's "can open a sentence"
path. Comparisons ("A vs. B") are never sentence boundaries.
MEASURED: split_sentences("Team A vs. Team B won.") -> ["Team A vs.", "Team B won."]

Bug 3 (layout) — a list-item line with trailing hard-break spaces ("- item  ") reaches the
hard-break check before the marker check, so the marker is included in the body that the
transform receives. Every other list item keeps the bullet outside the transform's scope.
MEASURED: apply_per_block("- item  \\n- other", str.upper) -> "[- ITEM]  \\n- [OTHER]"
(bullet capitalised for the hard-break item; normal item was fine).
"""

from __future__ import annotations

import pytest

from untell.layout import apply_per_block, _segments
from untell.text_split import split_sentences


# ---------------------------------------------------------------------------
# Bug 1: emoji / symbol after sentence-terminal period
# ---------------------------------------------------------------------------

class TestEmojiAfterPeriod:
    """An emoji or symbol directly after a period, before a space, must not hide the boundary."""

    @pytest.mark.parametrize(
        "text",
        [
            "Done.\U0001F389 The next sentence starts here.",
            "Task complete.✓ Now proceed.",
            "Step one done.✔ Step two follows.",
            "Error!❌ Please try again.",
            "Ready?❗ Start now.",
        ],
    )
    def test_emoji_after_terminator_splits_into_two_sentences(self, text):
        result = split_sentences(text)
        assert len(result) == 2, (
            f"Expected 2 sentences but got {len(result)}: {result!r}"
        )

    def test_emoji_does_not_consume_content(self):
        """The emoji must stay with the sentence that ends, not disappear from the output."""
        text = "Done.\U0001F389 The next sentence."
        parts = split_sentences(text)
        joined = "".join("".join(p.split()) for p in parts)
        assert joined == "".join(text.split())

    def test_emoji_stays_on_the_ending_sentence(self):
        """The emoji belongs to the sentence that ends, same as a closing quote or bracket."""
        parts = split_sentences("Done.\U0001F389 The next sentence.")
        assert parts[0] == "Done.\U0001F389"
        assert parts[1] == "The next sentence."

    def test_plain_sentence_boundary_is_unchanged(self):
        """Guard: ordinary sentence splitting must not be affected."""
        assert split_sentences("Done. Next.") == ["Done.", "Next."]

    def test_emoji_mid_sentence_without_period_is_not_a_boundary(self):
        """An emoji in the middle of a sentence with no preceding period is NOT a split point."""
        assert split_sentences("Great \U0001F389 result. And done.") == [
            "Great \U0001F389 result.",
            "And done.",
        ]


# ---------------------------------------------------------------------------
# Bug 2: "vs." followed by a capitalised continuation
# ---------------------------------------------------------------------------

class TestVsAbbreviation:
    """'vs.' is a comparison preposition, never a sentence terminator."""

    @pytest.mark.parametrize(
        "text",
        [
            "Team A vs. Team B won the championship.",
            "Good vs. Evil is the theme of the story.",
            "The U.S. vs. China trade dispute intensified.",
            "Apple vs. Microsoft is the classic rivalry.",
        ],
    )
    def test_vs_before_capital_does_not_split(self, text):
        result = split_sentences(text)
        assert len(result) == 1, (
            f"Expected 1 sentence but got {len(result)}: {result!r}"
        )

    def test_vs_before_lowercase_merges_as_before(self):
        """The abbreviation rule already merged lowercase continuations; that must still work."""
        assert len(split_sentences("3.5 vs. 2.1 shows the gap.")) == 1

    def test_genuine_sentence_boundary_after_a_full_stop_still_splits(self):
        """Guard: the fix must not suppress real splits."""
        assert len(split_sentences("He finished first. Then he rested.")) == 2


# ---------------------------------------------------------------------------
# Bug 3: hard-break list item loses its list-marker prefix
# ---------------------------------------------------------------------------

class TestHardBreakListItem:
    """A list item whose body ends in a hard break must have its marker extracted."""

    HARD_BREAK_LIST = "- First item  \n- Second item"

    def test_marker_is_not_inside_the_transform_body(self):
        """The transform must NOT see the bullet '- ' as part of the body it receives."""
        seen: list[str] = []
        apply_per_block(self.HARD_BREAK_LIST, lambda s: seen.append(s) or s)
        # Normal (no hard break) item: seen body is "Second item" (no bullet).
        # Hard-break item (BEFORE fix): seen body was "- First item" (bullet included).
        # AFTER fix: both items yield the text after the marker only.
        for body in seen:
            assert not body.lstrip().startswith("-"), (
                f"Transform received bullet character inside its input: {body!r}"
            )

    def test_hard_break_is_preserved_in_output(self):
        """The trailing '  ' (hard break) must survive the transform."""
        out = apply_per_block(self.HARD_BREAK_LIST, str.upper)
        assert "  \n" in out, f"Hard break was dropped: {out!r}"

    def test_bullet_is_preserved_in_output(self):
        """The bullet must be present in the final output, just outside the transform's scope."""
        out = apply_per_block(self.HARD_BREAK_LIST, str.upper)
        # Both items are list items, so both should have "- " in the output
        lines = out.split("\n")
        for line in lines:
            assert line.startswith("- "), f"Bullet missing from output line: {line!r}"

    def test_segments_extracts_marker_from_hard_break_item(self):
        """_segments must yield ("prose", "- ", body) not ("prose", "", "- body  ")."""
        segs = list(_segments("- item  \n- other"))
        # Both segments should be prose with marker prefix "- "
        for kind, prefix, body in segs:
            if kind == "prose":
                assert prefix == "- ", (
                    f"Expected prefix='- ', got prefix={prefix!r}, body={body!r}"
                )
                assert not body.startswith("-"), (
                    f"Body should not start with bullet: {body!r}"
                )

    def test_numbered_list_item_with_hard_break_also_fixed(self):
        """The same fix applies to ordered-list items like '1. item  '."""
        segs = list(_segments("1. First item  \n2. Second item"))
        for kind, prefix, body in segs:
            if kind == "prose":
                assert not body.lstrip().startswith(("1.", "2.")), (
                    f"Numbered list marker inside transform body: {body!r}"
                )

    def test_plain_hard_break_line_is_unchanged(self):
        """A non-list line with trailing spaces still yields prefix='' as before."""
        segs = list(_segments("Plain line with hard break.  \nNext."))
        # The first line is NOT a list item, so prefix should stay ''
        # (its body already contains the sentence-final period, no marker)
        for kind, prefix, body in segs:
            if kind == "prose" and "hard break" in body:
                assert prefix == "", f"Expected no prefix for plain line: prefix={prefix!r}"
