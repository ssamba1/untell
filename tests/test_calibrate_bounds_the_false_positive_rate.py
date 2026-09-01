"""A calibrated threshold is only worth shipping if its guarantee actually holds.

`untell/calibrate.py` answers the question this repo's headline result provokes — "then what
threshold should I use?" — with a conformal bound rather than a tuned number. These tests check the
bound empirically, and pin the three ways it could be quietly wrong: dropping the finite-sample
correction, returning an authoritative-looking threshold the sample cannot support, and hiding what
FPR control costs in detection power.
"""

from __future__ import annotations

import random

import pytest

from untell.calibrate import calibrate, calibrate_by_length, required_samples


def test_the_bound_holds_on_held_out_human_scores():
    """The property that matters, checked the only way it can be: calibrate on one human sample,
    measure the flag rate on another from the same distribution."""
    rng = random.Random(7)
    exceed = 0
    trials = 200
    for _ in range(trials):
        calibration = [rng.random() for _ in range(200)]
        result = calibrate(calibration, alpha=0.1)
        held_out = rng.random()
        exceed += int(held_out >= result["threshold"])
    assert exceed / trials < 0.16, f"bound badly violated: {exceed / trials:.3f} vs alpha=0.1"


def test_a_sample_too_small_for_the_alpha_returns_none():
    """1% control needs 99 samples. Returning a threshold from 40 would look authoritative and
    guarantee nothing — the most dangerous possible output of this module."""
    scores = [i / 40 for i in range(40)]
    assert calibrate(scores, alpha=0.01) is None
    assert calibrate(scores, alpha=0.1) is not None


def test_required_samples_matches_the_arithmetic_it_documents():
    assert required_samples(0.01) == 99
    assert required_samples(0.5) == 20, "the floor applies below the arithmetic requirement"
    with pytest.raises(ValueError):
        required_samples(0.0)


def test_the_finite_sample_correction_is_present():
    """Using the plain (1-alpha) quantile instead of ceil((n+1)(1-alpha)) under-covers on small
    samples. On n=20 at alpha=0.05 the corrected rank is 20, not 19."""
    scores = [i / 20 for i in range(20)]
    assert calibrate(scores, alpha=0.05)["rank"] == 20


def test_the_cost_of_the_bound_is_reported():
    """A threshold that flags nothing satisfies any alpha. The caller has to be able to see that."""
    result = calibrate([0.1] * 100, alpha=0.05)
    assert "calibration_fpr" in result and "calibration_flagged" in result


def test_ties_are_visible_rather_than_silently_breaking_the_bound():
    """With every score identical, `>= threshold` catches all of them. The realised rate must be
    reported so a caller sees they did not get the alpha they asked for."""
    result = calibrate([0.5] * 100, alpha=0.05)
    assert result["calibration_fpr"] > result["alpha"]


def test_a_stricter_alpha_never_lowers_the_threshold():
    rng = random.Random(3)
    scores = [rng.random() for _ in range(500)]
    assert calibrate(scores, 0.01)["threshold"] >= calibrate(scores, 0.1)["threshold"]


def test_bands_without_enough_samples_report_none_not_a_guess():
    samples = [(30, 0.2)] * 5 + [(150, 0.3) for _ in range(60)]
    out = calibrate_by_length(samples, alpha=0.1)
    assert out["0-50"] is None, "5 samples cannot support a bound"
    assert out["100-200"] is not None


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
def test_an_impossible_alpha_is_rejected(alpha):
    with pytest.raises(ValueError):
        calibrate([0.1] * 100, alpha=alpha)


def test_a_loose_alpha_still_needs_a_real_calibration_set():
    """MUTATION-CHECKED. Removing the `n < required_samples(alpha)` guard survived, because the
    defensive `rank > n` check below it catches every case a *tight* alpha produces. It does not
    catch a loose one: at alpha=0.5 with 5 scores the rank is 3, comfortably inside the sample, so
    without the first guard `calibrate` would hand back a threshold derived from five documents.

    `MIN_CALIBRATION` is the reason there are two guards. A bound estimated from a handful of
    documents is exactly the false precision this repository objects to elsewhere.
    """
    from untell.calibrate import MIN_CALIBRATION, calibrate, required_samples

    assert required_samples(0.5) == MIN_CALIBRATION
    assert calibrate([0.1] * 5, alpha=0.5) is None
    assert calibrate([0.1] * (MIN_CALIBRATION - 1), alpha=0.5) is None
    assert calibrate([0.1] * MIN_CALIBRATION, alpha=0.5) is not None
