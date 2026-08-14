"""Spelled-number dict values must be exact.

numerals.py:88/93: the spelled-unit dicts map "ten"->10, "eighty"->80 etc. The
mutations 10->11 / 80->81 change the parsed value. _spelled_value is the
parser the whole preserve path runs on, so an off-by-one dict value rewrites
the wrong number.
"""
from untell.scripts.numerals import _spelled_value


def test_ten_is_ten():
    assert _spelled_value("ten") == "10"


def test_eighty_is_eighty():
    assert _spelled_value("eighty") == "80"


def test_compound_uses_units():
    assert _spelled_value("twenty three") == "23"
