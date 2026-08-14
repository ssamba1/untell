"""Killing test: untell_text must not raise on lone-surrogate input.

score_text handles lone surrogates (returns 0.0), but untell_text raised
UnicodeEncodeError when hashing the text for the seed (blake2b of utf-8
encode). Lone surrogates arrive from broken file encodings; the rewrite
loop must process or sanitize them, never leak a traceback.
"""
import pytest

from untell.scripts.run import untell_text

SURROGATE_INPUTS = [
    "abc\ud800def",          # lone high surrogate mid-string
    "\udc00 start",          # lone low surrogate at start
    "ends with \udfff",      # lone surrogate at end
    "mix \ud800 mid \udc00", # two surrogates
]


def test_untell_text_handles_lone_surrogates():
    for text in SURROGATE_INPUTS:
        # Must not raise; must return a result with a final string
        result = untell_text(text, tier="lite", max_iters=1, progress=False)
        assert isinstance(result["final"], str), f"no final for {text!r}"


def test_surrogate_seed_is_stable():
    # The same surrogate text must hash to the same seed (deterministic)
    text = "abc\ud800def"
    r1 = untell_text(text, tier="lite", max_iters=1, progress=False)
    r2 = untell_text(text, tier="lite", max_iters=1, progress=False)
    assert r1["final"] == r2["final"], "surrogate input not deterministic"
