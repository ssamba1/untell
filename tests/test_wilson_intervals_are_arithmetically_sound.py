"""Every published proportion in this repository carries a Wilson interval. Check the arithmetic.

`docs/research-verification.md` reports 169 proportions with intervals, and a test fails if one
appears without. That guards *presence*. Nothing guarded *correctness* — and the intervals are what
every "the gap is not evidence of a disparity" verdict in rounds thirty-four to thirty-seven turns
on. A systematically narrow interval would have turned those honest negatives into findings.

Wilson was chosen over the normal approximation for a reason worth pinning: at the sample sizes and
rates this project works at, the normal interval runs off the end of [0, 1] and covers badly. These
tests check the properties that make the choice correct, and two textbook values.
"""

from __future__ import annotations

import pytest

from eval.pre_llm_fpr import wilson_interval


@pytest.mark.parametrize("successes,total", [
    (0, 10), (1, 10), (5, 10), (9, 10), (10, 10),
    (0, 1), (1, 1), (3, 599), (123, 599), (1362, 6810),
])
def test_the_interval_stays_inside_zero_and_one(successes, total):
    """The defect Wilson exists to avoid. The normal approximation at 0/10 gives [0, 0] and at 1/10
    gives a lower bound below zero; a false-positive rate cannot be negative, and an interval that
    claims [0, 0] at 0 of 10 asserts certainty from ten documents."""
    low, high = wilson_interval(successes, total)
    assert 0.0 <= low <= high <= 1.0


@pytest.mark.parametrize("successes,total", [(1, 10), (5, 10), (9, 10), (123, 599)])
def test_the_interval_contains_the_point_estimate(successes, total):
    low, high = wilson_interval(successes, total)
    assert low <= successes / total <= high


def test_zero_successes_still_admits_a_positive_rate():
    """The 200+ word band read 0.0% on n=15 and the roadmap quotes its interval to 37.9%. If a zero
    count produced a zero-width interval, that row would read as proof of a rate of zero."""
    low, high = wilson_interval(0, 15)
    assert low == 0.0
    assert high > 0.15, "0 of 15 must not imply the rate is near zero"


def test_all_successes_still_admits_a_rate_below_one():
    low, high = wilson_interval(15, 15)
    assert high == 1.0
    assert low < 0.85


@pytest.mark.parametrize("rate", [0.1, 0.2, 0.5])
def test_more_data_narrows_the_interval(rate):
    """The property the whole n=120 -> n=599 -> n=2400 -> n=6810 progression relies on. If intervals
    did not narrow with n, growing the corpus would have bought nothing."""
    widths = []
    for total in (50, 200, 800, 3200):
        low, high = wilson_interval(round(rate * total), total)
        widths.append(high - low)
    assert widths == sorted(widths, reverse=True), f"widths did not shrink: {widths}"


def test_the_interval_is_asymmetric_near_the_boundary():
    """Wilson's defining behaviour, and why it was chosen. Near 0 the interval leans upward, which a
    symmetric normal interval cannot do."""
    low, high = wilson_interval(1, 100)
    point = 0.01
    assert (high - point) > (point - low) * 2


@pytest.mark.parametrize("successes,total,expected_low,expected_high", [
    # Textbook 95% Wilson values, to three decimals.
    (0, 10, 0.000, 0.278),
    (5, 10, 0.237, 0.763),
])
def test_known_values(successes, total, expected_low, expected_high):
    """Two cases with published answers. Every property above would hold for a formula that was
    wrong by a constant factor; these are what pin it to Wilson specifically."""
    low, high = wilson_interval(successes, total)
    assert low == pytest.approx(expected_low, abs=0.002)
    assert high == pytest.approx(expected_high, abs=0.002)


def test_an_empty_sample_does_not_crash_or_claim_certainty():
    """`probe` divides by a count that can be zero when no detector scored anything."""
    low, high = wilson_interval(0, 0)
    assert 0.0 <= low <= high <= 1.0
