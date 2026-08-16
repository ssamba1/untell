"""Fence and display-math state are isolated from each other.

The docstring promised exactly this: "$$ inside a fenced code block is code, not math, and a ```
inside a math block is math, not a fence". The implementation tracked the two with separate state
variables, but neither checked the other: a ``$$`` line inside a fence toggled ``in_math`` anyway,
so an odd number of ``$$`` lines left the math state stuck open after the fence closed and every
following prose line was silently locked; and a fence marker inside a math block opened (or closed)
the fence, so an odd count leaked fence state past the closing ``$$``.

Both leaks are invisible to the meaning gate, the detectors and the tells catalogue — none of them
looks at layout — and both turn ordinary prose into untransformable layout, or worse, hand math or
code to a rewriter.
"""

from __future__ import annotations

from untell.layout import apply_per_block, blocks

TRANSFORM = lambda s: s.replace("prose here", "PROSE HERE")  # noqa: E731


def test_odd_dollar_dollar_inside_a_fence_does_not_leak_math_state():
    """A fence containing ``$$`` without its closer must not lock the prose after the fence."""
    src = "```\n$$\nx = 1\n```\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out


def test_a_pair_of_dollar_dollars_inside_a_fence_stays_code():
    src = "```\n$$\nx = 1\n$$\n```\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out


def test_odd_backtick_inside_a_math_block_does_not_leak_fence_state():
    """A lone ``` inside math is math, not a fence opener — the prose after ``$$`` stays prose."""
    src = "$$\n\\int_0^1 x dx\n```\nx\n$$\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out


def test_odd_tilde_inside_a_math_block_does_not_leak_fence_state():
    src = "$$\n\\int_0^1 x dx\n~~~\nx\n$$\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out


def test_a_fence_pair_inside_a_math_block_is_math():
    src = "$$\na\n```\nb\n```\nc\n$$\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out
    assert "a" in out and "b" in out and "c" in out


def test_math_then_fence_then_prose():
    src = "$$\na\n$$\n\n```\nb\n```\n\nprose here."
    out = apply_per_block(src, TRANSFORM)
    assert "PROSE HERE" in out, out


def test_identity_transform_round_trips_every_shape():
    """None of these shapes may lose or gain a line under the identity transform."""
    for src in [
        "```\n$$\nx = 1\n```\nprose here.",
        "$$\n\\int_0^1 x dx\n```\nx\n$$\nprose here.",
        "$$\n\\int_0^1 x dx\n~~~\nx\n$$\nprose here.",
    ]:
        assert apply_per_block(src, lambda b: b) == src


def test_blocks_agrees_with_apply_per_block_on_the_leaky_shapes():
    """Both entry points are built on one partitioner; the prose unit must be visible to both."""
    src = "$$\n\\int_0^1 x dx\n```\nx\n$$\nprose here."
    assert blocks(src) == ["prose here."]
    seen: list[str] = []
    apply_per_block(src, lambda b: seen.append(b) or b)
    assert seen == ["prose here."]
