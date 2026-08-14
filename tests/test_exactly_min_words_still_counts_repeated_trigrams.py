"""Exactly MIN_WORDS_FOR_REPETITION words must still be repetition-checked.

tells.py:708 guards trigram counting with `len(words) < _MIN_WORDS_FOR_REPETITION`.
The mutation < -> <= makes the guard fire AT the minimum (60 words), so a text
with exactly 60 words and a hammered trigram reads as 0 repeats instead of its
real count — the detector goes silent exactly at its own boundary.
"""
from untell.scripts.tells import _repeated_trigrams


def test_exactly_min_words_still_counts_repeated_trigrams():
    text = " ".join(["alpha beta gamma"] * 20)  # exactly 60 words
    assert _repeated_trigrams(text) > 0


def test_below_min_words_returns_zero():
    text = " ".join(["alpha beta gamma"] * 19)  # 57 words < 60
    assert _repeated_trigrams(text) == 0
