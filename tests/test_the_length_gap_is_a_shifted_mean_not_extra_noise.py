"""Whether short text is scored *worse* or merely *noisier* decides what the right fix is.

Extra variance at short lengths would mean the detector cannot tell, and the honest response is
abstention. A shifted mean means it can tell and is systematically wrong, and the response is a
per-length threshold — the signal is there, the bar is in the wrong place.

MEASURED on all 6,810 pre-LLM abstracts at the shipped verdict threshold of 0.45, 60-100 words
against 200+, a gap of 15.92 points:

    matching the long band's mean     28.69% -> 15.75%   closes 81% of the gap
    matching the long band's spread   28.69% -> 25.04%   closes 23%
    matching both                     28.69% -> 13.60%   against a long-band 12.77%

**It is the mean.** Short human text is not scored more noisily; it is scored more machine-like. So
`calibrate_by_length` is the right answer for it and abstention is not.

These tests use synthetic samples with one mechanism at a time, because the point is that the
decomposition can tell them apart. A diagnosis that returned "mean shift" for every input would
reproduce the real corpus's answer by luck and be worth nothing.
"""

from __future__ import annotations

import random

import pytest

from eval.length_standardized import decompose_length_gap

THRESHOLD = 0.45
SHORT, LONG = (60, 100), (200, 10**9)


def _samples(short_mean: float, short_sd: float, long_mean: float, long_sd: float,
             n: int = 3000, seed: int = 0) -> list[tuple[int, float]]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        out.append((rng.randrange(60, 100), rng.gauss(short_mean, short_sd)))
        out.append((rng.randrange(200, 320), rng.gauss(long_mean, long_sd)))
    return out


def test_a_pure_mean_shift_is_diagnosed_as_a_mean_shift():
    """Identical spreads, different centres. Only the threshold can fix this."""
    report = decompose_length_gap(
        _samples(0.42, 0.12, 0.30, 0.12), THRESHOLD, SHORT, LONG)
    assert report["mechanism"].startswith("mean shift")
    assert report["matching_mean"]["closes"] > 0.85
    assert report["matching_spread"]["closes"] < 0.2


def test_a_pure_variance_difference_is_diagnosed_as_variance():
    """Identical centres, different spreads. A threshold cannot fix this and the report says so.

    This is the case that makes the real corpus's answer meaningful: the decomposition is capable of
    returning the other verdict.
    """
    report = decompose_length_gap(
        _samples(0.30, 0.22, 0.30, 0.08), THRESHOLD, SHORT, LONG)
    assert report["mechanism"].startswith("variance")
    assert report["matching_spread"]["closes"] > 0.85
    assert report["matching_mean"]["closes"] < 0.2


def test_matching_both_closes_essentially_all_of_the_gap():
    """The two counterfactuals are not additive — on the real corpus they close 81% and 23% — so the
    check that the decomposition is complete is that together they close nearly everything."""
    for args in ((0.42, 0.12, 0.30, 0.12), (0.30, 0.22, 0.30, 0.08), (0.40, 0.18, 0.30, 0.10)):
        report = decompose_length_gap(_samples(*args), THRESHOLD, SHORT, LONG)
        assert report["matching_both"]["closes"] > 0.85, (args, report["matching_both"])


def test_no_gap_at_all_is_reported_without_dividing_by_zero():
    """Identical distributions. `closes` is a share of a gap, and there is none."""
    report = decompose_length_gap(_samples(0.30, 0.12, 0.30, 0.12), THRESHOLD, SHORT, LONG)
    assert abs(report["gap"]) < 0.05
    for key in ("matching_mean", "matching_spread", "matching_both"):
        assert report[key]["closes"] is None or isinstance(report[key]["closes"], float)


def test_the_observed_rates_are_the_ones_the_threshold_gives():
    """Guards the arithmetic against the counterfactuals: the reported `flagged` figures must be
    plain rates at the threshold, not something the transformation produced."""
    samples = _samples(0.42, 0.12, 0.30, 0.12)
    report = decompose_length_gap(samples, THRESHOLD, SHORT, LONG)
    short = [s for w, s in samples if SHORT[0] <= w < SHORT[1]]
    assert report["short"]["flagged"] == pytest.approx(
        sum(s >= THRESHOLD for s in short) / len(short), abs=1e-4)
    assert report["short"]["n"] == len(short)


@pytest.mark.parametrize("samples", [[], [(70, 0.5)], [(70, 0.5), (250, 0.5)]])
def test_a_band_too_small_to_have_a_spread_reports_nothing(samples):
    """A standard deviation needs two points, and a zero spread cannot be rescaled. Returning a
    number there would be arithmetic on nothing."""
    assert decompose_length_gap(samples, THRESHOLD, SHORT, LONG) is None
