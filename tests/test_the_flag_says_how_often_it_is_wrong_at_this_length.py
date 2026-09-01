"""The short-text warning stops at 40 words. The elevated false-positive rate does not.

MEASURED at the shipped verdict threshold of 0.45 on all 6,810 pre-LLM ACL abstracts — human by
construction, so every flag is a false positive:

    60-100 words     603 docs   28.69%   [25.22%, 32.43%]
    100-150 words  3,032 docs   20.65%   [19.24%, 22.12%]
    150-200 words  2,705 docs   17.26%   [15.89%, 18.73%]
    200+ words       470 docs   12.77%   [10.05%, 16.09%]

**More than one human document in four between 60 and 100 words is flagged**, and until round
seventy-three none of them carried any caveat, because 60 sits above the 40-word cliff where
`_short_text_warning` stops. Length is worth 2.2x on the shipped default and the report said nothing
about it.

The evidence is also stronger than what the existing bands rest on: 6,810 documents that are human
because of when they were published, against 40 HC3 texts truncated.
"""

from __future__ import annotations

import re

import pytest

from untell.scripts.score import (
    _ELEVATED_FPR_BANDS,
    _MIN_WORDS_FOR_A_VERDICT,
    _STDLIB_PERPLEXITY_VERDICT_THRESHOLD,
    _length_false_positive_warning,
)

WORDS = "The system processes data efficiently and stores every result carefully ".split()
SHIPPED = _STDLIB_PERPLEXITY_VERDICT_THRESHOLD


def _text(n: int) -> str:
    return " ".join((WORDS * 200)[:n])


def _rate(note: str | None) -> str | None:
    if not note:
        return None
    found = re.search(r"\*\*([\d.]+%)\*\* of documents this length", note)
    return found.group(1) if found else None


@pytest.mark.parametrize("words,expected", [(40, "28.69%"), (66, "28.69%"), (99, "28.69%")])
def test_the_elevated_band_quotes_its_measured_rate(words, expected):
    assert _rate(_length_false_positive_warning(_text(words), SHIPPED)) == expected


@pytest.mark.parametrize("words", [100, 149, 150, 199, 400])
def test_lengths_at_or_near_the_corpus_average_get_nothing(words):
    """20.65% at 100-150 and 17.26% at 150-200 sit either side of the corpus-wide 19.47%. A note
    there says "this document is average" on the majority of all input, and stacking caveats buries
    the actionable one — which `test_the_specific_caveat_comes_first` caught when this fired on
    every length: a 66-word sample of ordinary prose went from one note to two."""
    assert _length_false_positive_warning(_text(words), SHIPPED) is None


def test_the_gap_above_the_short_text_cliff_is_covered():
    """The finding. 40 to 100 words used to get no caveat at all while being flagged 28.69% of the
    time."""
    assert _MIN_WORDS_FOR_A_VERDICT == 40
    assert _length_false_positive_warning(_text(40), SHIPPED) is not None
    assert _length_false_positive_warning(_text(80), SHIPPED) is not None


def test_below_the_cliff_this_note_stays_quiet():
    """`_short_text_warning` owns that range and says something stronger: no verdict at all. Two
    notes about length on one short document would bury the one that matters."""
    for words in (5, 20, 39):
        assert _length_false_positive_warning(_text(words), SHIPPED) is None


def test_a_caller_who_sets_their_own_verdict_bar_gets_none_of_these_numbers():
    """The rates are measured AT 0.45. Printing them beside someone else's bar attributes one
    threshold's number to another — the defect `_threshold_range_warning` exists for.

    ✗ The first version of this function gated on `DEFAULT_THRESHOLD`, which is 0.30 and is the
    LOOP's stop target, not the bar `flagged` is decided on. It would have printed a 0.45 rate for
    every caller who left the loop target alone.
    """
    for other in (0.30, 0.5215, 0.6, 0.9):
        assert _length_false_positive_warning(_text(80), other) is None


def test_the_note_says_what_the_rate_is_a_rate_of():
    """A percentage whose subject is unstated reads as an accuracy figure. The same reasoning put
    HUMAN in capitals in `_short_text_warning`."""
    note = _length_false_positive_warning(_text(80), SHIPPED)
    assert "false positive" in note
    assert "pre-LLM" in note and "6,810" in note
    assert "95% CI" in note


def test_the_unmeasured_range_is_named_rather_than_interpolated():
    """The pre-LLM corpus floors at 60 words, so 40-60 is not measured. The rate there is higher,
    not lower, and the note says so instead of quoting a number nobody derived."""
    near = _length_false_positive_warning(_text(45), SHIPPED)
    assert "not directly measured" in near
    assert _length_false_positive_warning(_text(80), SHIPPED).count("not directly measured") == 0


def test_the_bands_are_ordered_and_the_rates_fall_with_length():
    """Guards the table itself. A band list out of order would quote the wrong rate silently, and a
    rate that rose with length would mean the measurement had been transcribed backwards."""
    bounds = [b for b, _, _ in _ELEVATED_FPR_BANDS]
    assert bounds == sorted(bounds)
    rates = [float(r.rstrip("%")) for _, r, _ in _ELEVATED_FPR_BANDS]
    assert rates == sorted(rates, reverse=True), rates
    # Every band must be materially above the corpus-wide 19.47%, or it is not worth a caveat.
    assert all(r > 24.0 for r in rates), rates
