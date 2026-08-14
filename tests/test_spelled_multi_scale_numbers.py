"""Killing/regression test: spelled multi-scale numbers parse as ONE quantity.

"three thousand two hundred" is 3200, not 3002. The old _SPELLED_RE matched only
"three thousand two" and left "hundred" dangling, so a faithful rewrite of 3,200
spelled out was vetoed and a real +200 change was missed. Same for the reverse
group order and nested scales.
"""
from untell.scripts.numerals import _numbers, missing_numbers, numbers_kept


def test_scale_then_hundred_is_one_number():
    assert _numbers("three thousand two hundred") == ["3200"]
    assert _numbers("two million three hundred thousand") == ["2300000"]
    assert _numbers("three thousand five hundred and twenty") == ["3520"]


def test_hundred_then_scale_is_one_number():
    assert _numbers("two hundred three thousand") == ["203000"]


def test_simple_scales_still_parse():
    assert _numbers("three thousand") == ["3000"]
    assert _numbers("two hundred") == ["200"]
    assert _numbers("one thousand two hundred and forty") == ["1240"]
    assert _numbers("fifteen hundred") == ["1500"]
    assert _numbers("a thousand and one") == ["1001"]


def test_gate_accepts_digit_to_spelled_rewrite():
    # A faithful rewrite spelling the quantity out must not be vetoed.
    src = "The budget is 3,200 dollars."
    cand = "The budget is three thousand two hundred dollars."
    assert missing_numbers(src, cand) == []
    assert numbers_kept(src, cand) is True


def test_gate_accepts_spelled_to_digit_rewrite():
    src = "The budget is three thousand two hundred dollars."
    cand = "The budget is 3,200 dollars."
    assert missing_numbers(src, cand) == []
