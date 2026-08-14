"""Display-math blocks must round-trip byte-identical through the layout layer.

A `$$...$$` block was classified as prose — the delimiters are not fences, so the
equation was handed to the transform and rewritten. Same damage class as fenced
code before it was protected. Inline `$...$` stays prose (locked by preserve.py).
"""

from untell.layout import apply_per_block, restore_layout_lines

MATH = """Prose before.

$$
\\int_0^1 x dx = \\frac{1}{2}
$$

Prose after."""


def _upper_prose(t: str) -> str:
    return t.upper()


def test_display_math_content_is_never_handed_to_the_transform():
    out = apply_per_block(MATH, _upper_prose)
    # The equation must survive verbatim — no uppercase, no reflow.
    assert "\\int_0^1 x dx = \\frac{1}{2}" in out
    assert "\\INT" not in out
    # The delimiters survive.
    assert out.count("$$") == 2
    # Prose around it was rewritten.
    assert "PROSE BEFORE" in out
    assert "PROSE AFTER" in out


def test_display_math_survives_restore_layout_lines():
    out = apply_per_block(MATH, _upper_prose)
    restored = restore_layout_lines(MATH, out)
    assert "\\int_0^1 x dx = \\frac{1}{2}" in restored


def test_math_inside_fenced_code_is_not_a_math_block():
    """A ``` fence containing $$ is code, and must not toggle the math state."""
    doc = "Prose.\n\n```\n$$\nnot math\n$$\n```\n\nMore prose."
    out = apply_per_block(doc, _upper_prose)
    # The fence content stays verbatim.
    assert "$$\nnot math\n$$" in out


def test_math_block_can_contain_a_fence_marker():
    """A ``` inside $$...$$ is math content, and must not close anything."""
    doc = "Prose.\n\n$$\n```\n\\alpha\n$$\n\nMore prose."
    out = apply_per_block(doc, _upper_prose)
    assert "```" in out
    assert "\\alpha" in out
