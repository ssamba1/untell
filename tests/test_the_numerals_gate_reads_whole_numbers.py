"""The fact-preservation gate admitted changed quantities and vetoed unchanged ones.

`numbers_kept` promises that every numeral the source states survives the rewrite. Four ways it
did not hold, all MEASURED against the real gate functions:

FALSE NEGATIVES — meaning changed, gate passed. The dangerous direction.

    -5 degrees      -> 5 degrees          kept=True   (the sign was never extracted)
    100 patients    -> two hundred        kept=True   (200 != 100)
    1,000 units     -> two thousand       kept=True
    1,000,000       -> two million        kept=True
    5 cases         -> twenty-five cases  kept=True
    9 cases         -> ninety cases       kept=True
    1 case          -> twenty-one cases   kept=True

The first is `_NUMBER_RE` opening with `\\d`, so the minus was outside every match. The rest are one
cause: the permissive-word fallback was a bare substring test, and "five" is inside "twenty-five",
"nine" inside "ninety", "hundred" inside "three hundred". The audit that found this reported the
scale words; sweeping the small numbers as well showed every compound leaked the same way.

FALSE VETO — meaning unchanged, gate refused. Costs the loop a legitimate candidate.

    5.0 per 100 -> 5 per 100      kept=False, missing ['5.0']
    5 per 100   -> 5.0 per 100    kept=False, missing ['5']
    5.50        -> 5.5            kept=False, missing ['5.50']

Comparison is by string, and trailing zeros after a decimal point make two spellings of one
quantity. Tidying them is exactly what a rewriter does.

THE FIXES, and why "a hundred" had to be taught first. Dropping the scale words from the permissive
map closes the multiple leak, but on its own it breaks "100 -> a hundred", which is a faithful
rewrite: `_SPELLED_RE` required a unit word before the scale, so "a hundred" produced no value at
all. Admitting `a` as a multiplier of one lets the value path handle it, and `_spelled_value`
already read a missing multiplier as 1. The order matters — the second change without the first
would have traded a false negative for a false veto.

MEASURED after: 0 of 66 real rewrites vetoed, across four number-bearing documents, three rewriters
and six seeds. A gate that blocks the loop is worse than one that misses a case.
"""

from __future__ import annotations

import pytest

from untell.scripts.numerals import missing_numbers, numbers_kept

CHANGED = [
    ("negative sign", "The temperature was -5 degrees.", "The temperature was 5 degrees."),
    ("negative percent", "Margin fell to -12 percent.", "Margin fell to 12 percent."),
    ("hundred doubled", "The trial enrolled 100 patients.", "The trial enrolled two hundred patients."),
    ("thousand doubled", "Losses reached 1,000 units.", "Losses reached two thousand units."),
    ("million doubled", "Revenue hit 1,000,000 dollars.", "Revenue hit two million dollars."),
    ("five inside twenty-five", "We found 5 cases.", "We found twenty-five cases."),
    ("five inside forty-five", "We found 5 cases.", "We found forty-five cases."),
    ("nine inside ninety", "We found 9 cases.", "We found ninety cases."),
    ("one inside twenty-one", "We found 1 case.", "We found twenty-one cases."),
    ("two inside twenty-two", "We found 2 cases.", "We found twenty-two cases."),
    ("hundred inside three hundred", "We saw 100 items.", "We saw three hundred items."),
    ("digits doubled", "Revenue hit 1,000,000 dollars.", "Revenue hit 2,000,000 dollars."),
]

UNCHANGED = [
    ("spelled faithfully", "The trial enrolled 100 patients.", "The trial enrolled one hundred patients."),
    ("a hundred", "The trial enrolled 100 patients.", "The trial enrolled a hundred patients."),
    ("a thousand", "Losses reached 1,000 units.", "Losses reached a thousand units."),
    ("small spelled", "We found 5 cases.", "We found five cases."),
    ("ten spelled", "We found 10 cases.", "We found ten cases."),
    ("trailing zero dropped", "Rate was 5.0 per 100.", "Rate was 5 per 100."),
    ("trailing zero added", "Rate was 5 per 100.", "Rate was 5.0 per 100."),
    ("trailing zero in decimal", "Rate was 5.50 per 100.", "Rate was 5.5 per 100."),
    ("comma expanded", "Revenue hit 1,000,000 dollars.", "Revenue hit 1000000 dollars."),
    ("magnitude notation", "Losses hit 5 million.", "Losses hit 5,000,000.")
]


@pytest.mark.parametrize("name,source,candidate", CHANGED, ids=[c[0] for c in CHANGED])
def test_a_changed_quantity_is_refused(name: str, source: str, candidate: str) -> None:
    assert not numbers_kept(source, candidate), (
        f"{name}: the gate accepted a changed quantity — {source!r} -> {candidate!r}"
    )
    assert missing_numbers(source, candidate), "refused with nothing named as missing"


@pytest.mark.parametrize("name,source,candidate", UNCHANGED, ids=[c[0] for c in UNCHANGED])
def test_an_unchanged_quantity_is_admitted(name: str, source: str, candidate: str) -> None:
    """The error that costs more. A veto here removes a legitimate candidate from the loop."""
    assert numbers_kept(source, candidate), (
        f"{name}: the gate refused an unchanged quantity — {source!r} -> {candidate!r}, "
        f"missing {missing_numbers(source, candidate)}"
    )


def test_a_negative_number_is_extracted_with_its_sign() -> None:
    """The mechanism, so a future regex change cannot silently drop the sign again."""
    from untell.scripts.numerals import _numbers

    assert "-5" in _numbers("The temperature was -5 degrees.")
    assert "5" in _numbers("The temperature was 5 degrees.")


def test_a_range_is_still_two_positive_numbers() -> None:
    """The risk of admitting a leading minus: a hyphenated range must not read as a negative."""
    from untell.scripts.numerals import _numbers

    values = _numbers("Temperatures ranged from 5-10 degrees.")
    assert "5" in values and "10" in values, values
    assert "-10" not in values, "the range hyphen was read as a minus sign"


def test_the_permissive_word_must_stand_alone() -> None:
    """The fallback's contract, asserted directly."""
    from untell.scripts.numerals import _says_word

    assert _says_word("we found five cases", "five")
    assert not _says_word("we found twenty-five cases", "five")
    assert not _says_word("we found ninety cases", "nine")
