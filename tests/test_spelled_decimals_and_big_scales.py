"""A numeral must count "as a numeral or as its English word" — including decimals and
billion/trillion, the two spelled forms the extraction once misread.

`_SPELLED_RE`'s multiplier branch knew hundred/thousand/million while `_SCALES` (the digit
path's table) also knew billion/trillion — so "Losses hit five billion." read as ['5'] and a
rewrite that changed billion to trillion passed `numbers_kept` with nothing missing. MEASURED
before the fix, both directions were broken:

    "Losses hit five billion." -> "Losses hit five trillion."   PASSED (the leak)
    "Losses hit five billion." -> "Losses hit 5,000,000,000."   VETOED  (faithful expansion)

Spelled decimals had the opposite shape: "twelve point four" read as two integers, 12 and 4,
so a faithful "12.4%" -> "twelve point four percent" was vetoed in both directions — the
value 12.4 could never match because it was never produced.

No in-repo rewriter spells numbers out, so both were unreachable from the free path. The LLM
rewriter writes prose and can spell whatever it likes.
"""

from __future__ import annotations

import pytest

from untell.scripts.numerals import _numbers, numbers_kept


@pytest.mark.parametrize(
    "text,expected",
    [
        ("twelve point four", ["12.4"]),
        ("three point one four", ["3.14"]),
        ("zero point five", ["0.5"]),
        ("one point five million", ["1500000"]),
        ("five billion", ["5000000000"]),
        ("five trillion", ["5000000000000"]),
    ],
)
def test_a_spelled_decimal_or_big_scale_reads_as_its_value(text: str, expected: list[str]) -> None:
    assert _numbers(text) == expected


@pytest.mark.parametrize(
    "source,candidate",
    [
        ("The fund returned 12.4% last year.", "The fund returned twelve point four percent last year."),
        ("Rate was 3.5 per 100.", "Rate was three point five per 100."),
        ("Losses hit five billion.", "Losses hit 5,000,000,000."),
        ("Debt reached two trillion.", "Debt reached 2,000,000,000,000."),
    ],
)
def test_spelling_a_decimal_or_big_scale_out_is_not_a_dropped_quantity(
    source: str, candidate: str
) -> None:
    assert numbers_kept(source, candidate)


@pytest.mark.parametrize(
    "source,candidate",
    [
        ("Losses hit five billion.", "Losses hit five trillion."),
        ("Losses hit five million.", "Losses hit five billion."),
        ("The fund returned 12.4% last year.", "The fund returned 15.4% last year."),
    ],
)
def test_a_changed_magnitude_or_decimal_is_still_caught(source: str, candidate: str) -> None:
    """The half that matters. Recognising more word forms must not widen what counts as equal —
    a rewrite that upgrades billion to trillion is exactly the leak the scale fold exists for."""
    assert not numbers_kept(source, candidate)
