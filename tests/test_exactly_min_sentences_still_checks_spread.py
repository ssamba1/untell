"""Exactly MIN_SENTENCES_FOR_SPREAD sentences must still be rankable-checked.

sentences.py:163 guards the spread test with `len(scores) < _MIN_SENTENCES_FOR_SPREAD`.
The mutation < -> <= makes the guard fire AT the minimum (3 sentences), so a
document with exactly 3 narrowly-scored sentences reads as "rankable" instead of
"unrankable" — sending the rewriter to target near-equal sentences. The boundary
case is the point of the guard.
"""
from untell.scripts.sentences import _targeting_is_unrankable


def test_exactly_min_sentences_with_narrow_spread_is_unrankable():
    rows = [{"ai": 0.51}, {"ai": 0.52}, {"ai": 0.53}]  # spread 0.02 < 0.05 bar
    assert _targeting_is_unrankable(rows) is True


def test_below_min_sentences_is_rankable():
    rows = [{"ai": 0.51}, {"ai": 0.52}]  # 2 < 3: guard fires, no spread test
    assert _targeting_is_unrankable(rows) is False
