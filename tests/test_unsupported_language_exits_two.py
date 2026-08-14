"""Unsupported-language text exits 2 (the documented convention).

sentences.py:356: when the tells catalogue reports language_supported=False, main
returns 2 — the comment says it is "the same code and reasoning untell-verify,
untell-score, untell-tells and untell-humanness use", MEASURED on a Chinese
paragraph that previously printed [ok 0.00] and exited 0. The mutation 2 -> 3
changes the documented usage-error code.
"""
from untell.scripts.sentences import main

CHINESE = "这是一个测试段落，用来检测语言支持。"


def test_unsupported_language_exits_two():
    assert main([CHINESE]) == 2
