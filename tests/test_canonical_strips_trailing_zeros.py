"""Canonical numbers strip trailing zeros instead of collapsing to "0".

numerals.py:214: `return trimmed or "0"` — trailing zeros after a decimal are
stripped ("5.50" -> "5.5") so equal quantities compare equal by string. The
mutation or -> and makes `trimmed and "0"`, which returns "0" for EVERY
non-empty trimmed value: "5.50" canonicalizes to "0", so a rewrite that tidied
a trailing zero compares unequal to its source (the exact false-veto the
docstring documents).
"""
from untell.scripts.numerals import _canonical


def test_trailing_zeros_stripped():
    assert _canonical("5.50") == "5.5"


def test_integer_left_alone():
    assert _canonical("5") == "5"


def test_all_zeros_becomes_zero():
    assert _canonical("0.00") == "0"
