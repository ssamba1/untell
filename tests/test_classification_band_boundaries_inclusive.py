"""Classification band boundaries are inclusive: exact scores stay in-band.

humanness.py:507-515: the verdict bands are `score >= 75/60/45/30`. The
mutation >= -> > at any edge pushes an exact-boundary score into the next band
down: 60 must be "mostly human", not "mixed". Pure function.
"""
from untell.humanness import classification


def test_score_exactly_sixty_is_mostly_human():
    assert classification(60) == "mostly human"


def test_score_exactly_seventy_five_is_human():
    assert classification(75) == "human"


def test_score_exactly_forty_five_is_mixed():
    assert classification(45) == "mixed"


def test_score_exactly_thirty_is_likely_ai():
    assert classification(30) == "likely AI"


def test_just_below_sixty_is_mixed():
    assert classification(59.99) == "mixed"
