"""Killing test: score_text / untell_text must reject non-str with a clean TypeError.

Fuzz-found: bytes input (e.g. a file read in binary mode) raised an internal
'string pattern on bytes-like object' / 'ord() expected string of length 1'
TypeError from deep inside the normalisers. The public entry points must
name the contract: text must be str.
"""
import pytest

from untell.scripts.score import score_text
from untell.scripts.run import untell_text

BAD_INPUTS = [
    b"hello world",        # utf-8 bytes
    b"\x00\x01\x02",       # binary bytes
    b"\xff" * 10,          # invalid-utf8 bytes
    bytearray(b"test"),    # bytearray
    memoryview(b"test"),   # memoryview
    12345,                 # int
    None,                  # None
    ["list", "of", "words"],  # list
    {"text": "dict"},      # dict
]


def test_score_text_rejects_non_str():
    for bad in BAD_INPUTS:
        with pytest.raises(TypeError, match="text must be str"):
            score_text(bad, tier="lite")


def test_untell_text_rejects_non_str():
    for bad in BAD_INPUTS:
        with pytest.raises(TypeError, match="text must be str"):
            untell_text(bad, tier="lite", max_iters=1, progress=False)
