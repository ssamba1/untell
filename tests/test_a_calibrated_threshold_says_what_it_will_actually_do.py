"""The conformal bound is marginal, and the number callers want is conditional.

`calibrate()` returns a threshold and, until round sixty-one, a `calibration_fpr` — the rate on the
very documents that produced the threshold. That number is optimistic by construction and it is not
what anyone deploying the threshold cares about. The question is what the threshold does on the
*next* document, and the honest answer is not "at most alpha".

Split conformal guarantees `P(false positive) <= alpha` averaged over calibration sets. Conditional
on the one calibration set you actually have, the realised rate is `Beta(n + 1 - rank, rank)`
distributed: mean alpha, and therefore **above alpha about half the time**. `coverage_spread()`
computes that distribution in closed form, and this file pins it against simulation.

The claim worth guarding is the counter-intuitive one. More calibration data does *not* reduce the
chance of exceeding alpha — that converges to ~50%. It reduces the amount by which you exceed it.
A reader who assumes otherwise will read a single calibration run as a guarantee it never was.
"""

from __future__ import annotations

import math
import random

import pytest

from untell.calibrate import _beta_cdf, _beta_quantile, calibrate, coverage_spread, required_samples

ALPHA = 0.05


def _simulate(n: int, alpha: float, trials: int, seed: int) -> list[float]:
    """Realised false-positive rates from `trials` independent calibrations.

    Scores are uniform draws, which makes them exchangeable by construction and continuous, so the
    Beta result applies exactly and no corpus or detector is needed. The realised rate for a
    threshold `t` under a uniform score distribution is exactly `1 - t`, so the test measures the
    closed form against the definition rather than against a second approximation.
    """
    rng = random.Random(seed)
    # Not `calibrate()`: it rounds the threshold to 4dp, which perturbs the rate the threshold
    # implies, and the rank is the only thing being simulated.
    rank = math.ceil((n + 1) * (1.0 - alpha))
    out = []
    for _ in range(trials):
        scores = [rng.random() for _ in range(n)]
        out.append(1.0 - sorted(scores)[rank - 1])
    return out


@pytest.mark.parametrize("n", [100, 599, 2000])
def test_the_closed_form_matches_simulation(n):
    """If the Beta shapes were wrong, every number this module reports would be wrong quietly."""
    spread = coverage_spread(n, ALPHA)
    rates = sorted(_simulate(n, ALPHA, trials=600, seed=n))
    median = rates[len(rates) // 2]
    exceeds = sum(r > ALPHA for r in rates) / len(rates)
    assert median == pytest.approx(spread["median"], abs=0.006), (
        f"n={n}: simulated median {median:.4f} against closed form {spread['median']:.4f}")
    assert exceeds == pytest.approx(spread["exceeds_alpha"], abs=0.06), (
        f"n={n}: simulated {exceeds:.1%} exceed alpha against closed form "
        f"{spread['exceeds_alpha']:.1%}")


def test_the_mean_realised_rate_is_alpha_which_is_the_whole_guarantee():
    """The marginal bound, stated as an equality rather than an inequality.

    `mean` is exactly `alpha` up to the discreteness of `ceil`. A conformal threshold does not aim
    *under* alpha — it aims *at* it — which is why exceeding alpha half the time is correct.
    """
    for n in (300, 599, 2000, 6810):
        assert coverage_spread(n, ALPHA)["mean"] == pytest.approx(ALPHA, abs=0.001)


def test_more_data_narrows_the_band_rather_than_lowering_the_exceedance():
    """The finding of round sixty-one, pinned in both directions.

    Reading only the first assertion would suggest more data buys safety; it buys precision. The
    second assertion is the one that would catch a rewrite quietly implying otherwise.
    """
    widths = [coverage_spread(n, ALPHA)["p95"] - coverage_spread(n, ALPHA)["p5"]
              for n in (150, 599, 2000, 6810)]
    assert widths == sorted(widths, reverse=True), f"band should narrow monotonically: {widths}"
    assert widths[0] > 4 * widths[-1], (
        f"n=150 to n=6810 should be a large narrowing, got {widths[0]:.4f} to {widths[-1]:.4f}")

    exceeds = [coverage_spread(n, ALPHA)["exceeds_alpha"] for n in (599, 2000, 6810)]
    assert all(e > 0.40 for e in exceeds), (
        f"exceedance converges to ~50%, it does not fall away with n: {exceeds}")


def test_the_band_at_n_150_contains_this_repos_own_superseded_result():
    """Round sixty called 0.5215 a threshold that "failed its bound". It did not.

    Derived at alpha=0.05 on 150 documents, it flags 6.93% of the full 6,810-document corpus. That
    is inside the p5-p95 band for a 150-document calibration, so it is an ordinary draw and not a
    defect — which is the correction round sixty-one makes to round sixty.
    """
    spread = coverage_spread(150, ALPHA)
    assert spread["p5"] < 0.0693 < spread["p95"], (
        f"6.93% should sit inside [{spread['p5']:.4f}, {spread['p95']:.4f}]")


def test_the_arithmetic_survives_a_calibration_set_this_repo_actually_has():
    """6,810 documents means binomial coefficients that overflow a float if summed directly.

    The first implementation of the closed form raised OverflowError above n = 1000. A probability
    that cannot be computed for the corpus the repo ships is not a shipped feature.
    """
    spread = coverage_spread(6810, ALPHA)
    for key in ("mean", "median", "p5", "p95", "exceeds_alpha"):
        assert 0.0 <= spread[key] <= 1.0, f"{key} out of range: {spread[key]}"
    assert spread["p5"] < spread["median"] < spread["p95"]


def test_a_sample_too_small_for_alpha_gets_nothing_here_too():
    """`calibrate()` refuses rather than flatters; the spread must refuse on the same boundary, or
    a caller can be told what a threshold will do when there is no threshold."""
    assert required_samples(0.01) == 99
    assert coverage_spread(98, 0.01) is None
    assert coverage_spread(99, 0.01) is not None
    assert coverage_spread(19, ALPHA) is None
    assert calibrate([0.5] * 19, alpha=ALPHA) is None


def test_calibrate_carries_the_spread_so_the_honest_number_travels_with_the_threshold():
    """A caller reading `calibration_fpr` alone is reading the in-sample rate. The point of shipping
    this is that they cannot get the threshold without also getting what it will really do."""
    rng = random.Random(7)
    result = calibrate([rng.random() for _ in range(599)], alpha=ALPHA)
    assert result["expected_fpr"] is not None
    assert result["expected_fpr"]["n_calibration"] == result["n_calibration"]
    assert result["expected_fpr"]["alpha"] == ALPHA
    # The in-sample rate sits at alpha by construction; the out-of-sample band straddles it.
    assert result["expected_fpr"]["p5"] < ALPHA < result["expected_fpr"]["p95"]


def test_an_invalid_alpha_is_refused_rather_than_producing_a_shape():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            coverage_spread(500, bad)


# --- the distribution itself, against closed forms with known answers ----------------------------
#
# Everything above trusts `_beta_cdf`. Simulation agreement is good evidence but it is agreement
# between two things this repository wrote. These four cases are not: Beta(1, 1) is exactly
# Uniform(0, 1) and Beta(2, 1) has CDF x-squared, so a wrong implementation cannot pass them by
# coincidence. They also cost nothing to run, which the 400-trial simulations do not.


@pytest.mark.parametrize("x", [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
def test_beta_one_one_is_the_uniform_distribution(x):
    assert _beta_cdf(x, 1, 1) == pytest.approx(x, abs=1e-12)


@pytest.mark.parametrize("x", [0.2, 0.6, 0.9])
def test_beta_two_one_has_cdf_x_squared(x):
    assert _beta_cdf(x, 2, 1) == pytest.approx(x * x, abs=1e-12)


def test_the_cdf_is_monotone_and_bounded_at_the_shapes_this_module_uses():
    """Bisection in `_beta_quantile` is only correct if the function it inverts is monotone."""
    previous = -1.0
    for step in range(101):
        value = _beta_cdf(step / 100, 7, 144)  # the n = 150, alpha = 0.05 shapes
        assert 0.0 <= value <= 1.0
        assert value >= previous - 1e-12, f"not monotone at x = {step / 100}"
        previous = value


@pytest.mark.parametrize("p", [0.05, 0.5, 0.95])
def test_the_quantile_inverts_the_cdf(p):
    for a, b in ((7, 144), (30, 570), (2, 49)):
        assert _beta_cdf(_beta_quantile(p, a, b), a, b) == pytest.approx(p, abs=1e-6)
