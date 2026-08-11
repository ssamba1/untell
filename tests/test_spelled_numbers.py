"""A numeral must count "as a numeral or as its English word" — including compound ones.

`numerals.py` promises exactly that. `_spelled_value` summed the parts additively, so
"two hundred and forty" read as 2 + 40 = 42 and a source saying 240 looked like it had lost the
quantity. MEASURED: 5, 12, 20 and 100 all round-tripped and 240 did not — the small values are
covered by exact word forms and 100 by the loose-synonym map, so everything compound fell through
both and nothing pointed at the gap.

No in-repo rewriter spells numbers out, so this was unreachable from the free path. The LLM
rewriter writes prose and can spell whatever it likes.
"""

from __future__ import annotations

import pytest

from untell.scripts.numerals import _numbers, numbers_kept


@pytest.mark.parametrize(
    "text,expected",
    [
        ("three", ["3"]),
        ("fifteen", ["15"]),
        ("twenty-four", ["24"]),
        ("one hundred", ["100"]),
        ("two hundred and forty", ["240"]),
        ("nine hundred ninety nine", ["999"]),
    ],
)
def test_a_spelled_number_reads_as_its_value(text: str, expected: list[str]) -> None:
    assert _numbers(text) == expected


@pytest.mark.parametrize(
    "source,candidate",
    [
        ("The trial enrolled 240 patients.", "The trial enrolled two hundred and forty patients."),
        ("Only 5 tests passed.", "Only five tests passed."),
        ("It took 100 days.", "It took one hundred days."),
        ("We saw 24 events.", "We saw twenty-four events."),
    ],
)
def test_spelling_a_number_out_is_not_a_dropped_quantity(source: str, candidate: str) -> None:
    assert numbers_kept(source, candidate)


@pytest.mark.parametrize(
    "source,candidate",
    [
        ("The trial enrolled 240 patients.", "The trial enrolled 420 patients."),
        ("Only 7 of the 19 tests passed.", "Only a few of the 19 tests passed."),
        ("The trial enrolled 240 patients.", "The trial enrolled two hundred and fifty patients."),
    ],
)
def test_a_changed_or_vanished_quantity_is_still_caught(source: str, candidate: str) -> None:
    """The half that matters. Widening what counts as a number must not widen what counts as
    equal — the second case is the one the module was written for."""
    assert not numbers_kept(source, candidate)


def test_thousands_combined_with_hundreds_are_a_known_limit() -> None:
    """Pinned so it is a documented boundary rather than a surprise.

    "one thousand two hundred and forty" reads as two numbers, 1002 and 40, because the pattern
    takes one multiplier per match. Prose almost never spells a number that large, and the
    alternative is a materially more complex regex for a case with no observed instance — the same
    call made about the spaCy parse asymmetry in Result 72. If this starts mattering, the test
    names the behaviour to change.
    """
    assert _numbers("one thousand two hundred and forty") == ["1002", "40"]
