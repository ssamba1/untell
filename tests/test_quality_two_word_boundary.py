"""Killing test: quality.token_overlap's < 2 word-token guard (line 145 boundary).

The guard drops to character bigrams when either side has <2 word tokens. Mutating
< 2 -> <= 2 changes the exactly-2-word case from word-Dice to char-bigram scoring:
    'cat sleep' vs 'cats sleep' -> 0.5 (word Dice) but 0.9333 (char bigrams)
"""
from untell.scripts.quality import token_overlap


def test_exactly_two_words_uses_word_dice_not_char_bigrams():
    # 2 tokens each side, 1 shared word: word-Dice = 0.5.
    # Char bigrams would give 0.9333 (high shared character structure).
    assert token_overlap("cat sleep", "cats sleep") == 0.5


def test_under_two_words_uses_char_bigrams():
    # 1 token each: char-bigram path. "cat" vs "cats" shares most bigrams.
    assert token_overlap("cat", "cats") > 0.5
