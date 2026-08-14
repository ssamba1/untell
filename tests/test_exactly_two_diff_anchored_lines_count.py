"""Exactly two diff-anchored lines must count as a formatting tell.

tells.py:921: diff_anchored reports when `count >= 2`. The mutation 2 -> 3
makes a text with exactly two "+" lines report nothing, silently dropping a
layout tell at its own threshold. Fenced code is stripped first, so the probe
uses plain diff-anchored lines outside a fence.
"""
from untell.scripts.tells import _formatting_tells


def test_exactly_two_diff_anchored_lines_count():
    text = "some prose\n+ added line one\n+ added line two\nmore prose"
    out = _formatting_tells(text)
    assert out.get("diff_anchored") == 2, out


def test_one_diff_anchored_line_does_not_count():
    text = "some prose\n+ added line one\nmore prose"
    out = _formatting_tells(text)
    assert "diff_anchored" not in out, out
