"""A markdown hard break is an instruction, not incidental whitespace.

`layout.apply_per_block` gathers consecutive plain lines into one block "so a soft-wrapped
paragraph is transformed as a unit". A hard break — two or more trailing spaces — is not a soft
wrap: the author is asking for a rendered line break. Gathering it in let a sentence-level
transform merge straight across it, and two lines came back as one sentence.

It survived when nothing else changed, which is what made it easy to miss: the loss only appears
once the merge transform fires.
"""

from __future__ import annotations

from untell.layout import apply_per_block, blocks

HARD = "First line ends with a hard break.  \nSecond line follows it."
SOFT = "First line is soft wrapped\nand continues on the next line."


def test_a_hard_break_is_a_block_boundary() -> None:
    assert len(blocks(HARD)) == 2, blocks(HARD)


def test_a_soft_wrap_is_not() -> None:
    """Guards the guard: splitting on every newline would pass the test above and would destroy
    the whole point of gathering a paragraph so sentence work has more than one sentence in view."""
    assert len(blocks(SOFT)) == 1, blocks(SOFT)


def test_the_marker_survives_a_transform_that_strips_it() -> None:
    """The second half of the fix. Ending the block kept the line count right, but every transform
    strips trailing whitespace, so the output rendered as a soft wrap — the same loss by a
    different route."""
    out = apply_per_block(HARD, lambda s: s.strip().upper())
    assert "  \n" in out, repr(out)
    assert out.count("\n") == HARD.count("\n")


def test_a_merging_transform_cannot_join_across_it() -> None:
    """The original defect, stated as the invariant it broke."""
    merged = apply_per_block(HARD, lambda s: s.replace("\n", " "))
    assert merged.count("\n") == 1, repr(merged)


def test_ordinary_prose_is_untouched() -> None:
    """No trailing spaces anywhere: the new branch must not fire at all."""
    text = "One sentence here. Another sentence there."
    assert apply_per_block(text, lambda s: s) == text
