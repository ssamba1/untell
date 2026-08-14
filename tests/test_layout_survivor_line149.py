"""Test for layout.py line 149 mutation survivor: front_matter_end boundary.

The _segments function uses <= to classify front matter lines. Mutating <= to < at
line 149 would make the second line of an empty front matter document (---\n---)
be classified as prose instead of layout. This test pins that boundary.

The distinction matters for any document starting with ---:
  index <= front_matter_end: line is front matter (layout)
  index <  front_matter_end: with front_matter_end=0, line 0 would NOT be front matter
"""
from untell.layout import _prose_line_mask, _segments


class TestFrontMatterBoundary:
    def test_closing_fence_is_layout_not_prose(self):
        """Mutating <= to < at line 149 would make the closing --- as prose.

        For an empty front matter document (---\n---), both markers must be layout.
        With < (wrong), the second --- falls through to the prose path.
        """
        text = "---\n---"
        segs = list(_segments(text))
        kinds = [kind for kind, _, _ in segs]
        assert kinds == ["layout", "layout"], (
            f"empty front matter markers must both be 'layout', got {kinds}. "
            "Mutating <= to < would make the second --- be classified as prose."
        )

    def test_prose_line_mask_agrees_with_segments_for_front_matter(self):
        """The mask and source must agree on front matter documents."""
        text = "---\n---\n\nprose here"
        src_lines = text.split("\n")
        mask = _prose_line_mask(text)
        assert len(mask) == len(src_lines), (
            f"mask length {len(mask)} != src length {len(src_lines)}. "
            "This means front matter lines were misclassified as prose."
        )
        # The blank line after --- should be layout
        assert not mask[0], "first line (---) must be layout"
        assert not mask[1], "second line (---) must be layout"
