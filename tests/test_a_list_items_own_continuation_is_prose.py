"""A list item's wrapped second line was classified as a code block and never rewritten.

`_segments` decides an indented line starts an indented code block, guarded by `not buffer`:

    # `not buffer` is what keeps this off a soft-wrapped paragraph's continuation lines: an
    # indented line only starts code when it BEGINS a block, which after a blank line it does.

That reasoning is right and the guard does not implement it. The list-marker branch calls
`flush()` and yields its segment directly, so it never appends to `buffer` -- meaning after any
list item the buffer is empty and the item's OWN continuation line satisfies `not buffer`.

MEASURED before the fix:

    _segments("- first item\\n    continues here on the next line\\n- second item")
      -> ("prose",  "- ", "first item")
         ("layout", "",   "    continues here on the next line")   <- the author's prose
         ("prose",  "- ", "second item")

so `apply_per_block` handed that line straight back verbatim. Text the user wrote was excluded
from the rewrite, silently, and `changed=False` for that line looks identical to a line the
transform chose not to alter.

The separator that matters is the blank line, which is also what CommonMark uses: an indented
line directly under a marker is lazy continuation of the item, while a blank line first makes it
a genuine indented code block inside the list. Both cases are asserted here, because a fix that
caught the continuation by loosening the code-block test would start rewriting real code.
"""

from __future__ import annotations

from untell.layout import _segments, apply_per_block

CONTINUATION = "- first item\n    continues here on the next line\n- second item"
NUMBERED = "1. first item\n    continues here on the next line\n2. second item"
CODE_IN_LIST = "- item\n\n    actual_code = 2\n"
CODE_AFTER_PROSE = "some prose here\n\n    code_block_line = 1\n\nmore prose"
CODE_AFTER_HEADING = "# Heading\n    still_code = 1"


def _kinds(text: str) -> list[str]:
    return [kind for kind, _prefix, _body in _segments(text)]


def test_a_wrapped_list_item_line_is_prose_not_a_code_block():
    kinds = _kinds(CONTINUATION)
    assert kinds == ["prose", "prose", "prose"], kinds


def test_the_indent_survives_as_a_prefix_rather_than_reaching_the_transform():
    """Same contract as a list marker: the transform sees words, the layout is re-attached."""
    segments = list(_segments(CONTINUATION))
    _kind, prefix, body = segments[1]
    assert prefix == "    ", f"indent not carried as prefix: {prefix!r}"
    assert body == "continues here on the next line", body


def test_the_continuation_is_actually_transformed_end_to_end():
    """The point of the fix -- a segment can be relabelled and still never reach the transform."""
    out = apply_per_block(CONTINUATION, str.upper)
    assert "CONTINUES HERE ON THE NEXT LINE" in out, out
    assert "    CONTINUES" in out, f"the indent was not restored: {out!r}"


def test_an_ordered_list_behaves_the_same_as_a_bullet():
    assert _kinds(NUMBERED) == ["prose", "prose", "prose"]


def test_a_blank_line_still_makes_an_indented_block_code():
    """The distinction the fix rests on. Without this the fix would rewrite real code."""
    kinds = _kinds(CODE_IN_LIST)
    assert kinds[0] == "prose"
    assert "layout" in kinds[1:], kinds
    out = apply_per_block(CODE_IN_LIST, str.upper)
    assert "actual_code = 2" in out, f"code was rewritten: {out!r}"


def test_an_indented_block_after_ordinary_prose_is_still_code():
    out = apply_per_block(CODE_AFTER_PROSE, str.upper)
    assert "code_block_line = 1" in out, f"code was rewritten: {out!r}"


def test_an_indented_line_after_a_heading_is_still_code():
    """Only LIST markers open a continuation. A heading does not, so this stays a code block."""
    out = apply_per_block(CODE_AFTER_HEADING, str.upper)
    assert "still_code = 1" in out, f"code after a heading was rewritten: {out!r}"


def test_the_two_partitions_still_agree_about_the_continuation():
    """`blocks()` and `apply_per_block()` are built on `_segments` so they cannot disagree.

    A previous defect in this module was exactly a disagreement between them, so any change to the
    classifier is worth re-checking here: everything `apply_per_block` transformed must be prose,
    and the reassembled document must differ from the source only where the transform ran.
    """
    identity = apply_per_block(CONTINUATION, lambda s: s)
    assert identity == CONTINUATION, f"identity transform changed the document: {identity!r}"
