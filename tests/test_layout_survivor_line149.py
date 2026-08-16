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

    def test_a_dot_closer_still_closes_front_matter_as_layout(self):
        """YAML front matter may close with `...` as well as `---`.

        The line-203 `<=` survivor resurfaced after the thematic-break branch landed:
        a `---` closer now lands in the HR branch and is layout either way, so the
        empty-front-matter tests cannot distinguish `<=` from `<`. The `...` closer
        has no other branch — under the mutant it falls through to prose and becomes
        a transformable block. MEASURED with the mutant applied:
        blocks('---\\ntitle: X\\n...\\nprose') -> ['...', 'prose'] (mutant) vs
        ['prose'] (original).
        """
        from untell.layout import blocks

        text = "---\ntitle: X\n...\nprose here. More."
        assert blocks(text) == ["prose here. More."], blocks(text)
        segs = list(_segments(text))
        kinds = [kind for kind, _, _ in segs]
        assert kinds == ["layout", "layout", "layout", "prose"], kinds
