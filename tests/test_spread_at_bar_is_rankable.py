"""A spread exactly at the bar is rankable, not unrankable.

sentences.py:165: `return (max(scores) - min(scores)) < _TARGETING_SPREAD_BAR` —
scores are unrankable only when the spread is strictly BELOW the 0.05 bar. The
mutation < -> <= makes a spread of exactly 0.05 unrankable, declaring a
document's sentence scores too close to order when they sit exactly at the
usable threshold. Exact float: 0.05 - 0.0 == 0.05.
"""
from untell.scripts.sentences import _targeting_is_unrankable

ROWS = [{"ai": 0.0}, {"ai": 0.025}, {"ai": 0.05}]


def test_spread_at_bar_is_rankable():
    assert _targeting_is_unrankable(ROWS) is False


def test_exactly_min_sentences_proceed_to_spread():
    # 3 rows (== _MIN_SENTENCES_FOR_SPREAD) with spread 0.049 (< bar): the
    # count guard must NOT short-circuit; the spread decides (unrankable).
    rows = [{"ai": 0.5}, {"ai": 0.5245}, {"ai": 0.549}]
    assert _targeting_is_unrankable(rows) is True

