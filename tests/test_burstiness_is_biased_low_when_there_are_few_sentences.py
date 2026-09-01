"""The detector's length effect is a small-sample bias in a coefficient of variation.

`_burstiness` is the CV of sentence word-counts, and `burst_signal = (0.55 - cv) / 0.55` at weight
0.6 is the largest term in the lite score. A CV estimated from four sentences underestimates the true
one badly, and `_burstiness` makes it worse by dividing by `n` rather than `n - 1`.

So a short document gets a low CV *because it is short*, a high `burst_signal`, and a high score —
with nothing about the writing involved. That is the mechanism behind the 28.69%-versus-12.77%
false-positive gap rounds seventy-two to seventy-four measured and could not explain.

These tests draw sentence lengths from ONE fixed distribution. Any gradient with sentence count is
estimator bias by construction, because the thing being estimated never changes.
"""

from __future__ import annotations

import random

import pytest

from untell.detectors.perplexity_burstiness import (
    _burstiness,
    burstiness_bias_corrected,
    clamp01,
)

TRUE_MEAN, TRUE_SD = 22.0, 11.0
TRUE_CV = TRUE_SD / TRUE_MEAN  # 0.5
TRIALS = 4000


def _sentences(lengths: list[int]) -> list[str]:
    return [" ".join(["w"] * n) for n in lengths]


def _mean_cv(estimator, n: int, seed: int = 7) -> float:
    rng = random.Random(seed)
    total = 0.0
    for _ in range(TRIALS):
        lengths = [max(3, int(rng.gauss(TRUE_MEAN, TRUE_SD))) for _ in range(n)]
        total += estimator(_sentences(lengths))
    return total / TRIALS


def test_the_shipped_estimator_underestimates_badly_at_few_sentences():
    """The defect. Three sentences from a distribution whose CV is 0.50 read as about 0.38."""
    assert _mean_cv(_burstiness, 3) < 0.42
    assert _mean_cv(_burstiness, 100) > 0.47


def test_the_shipped_estimator_has_a_large_gradient_in_sentence_count_alone():
    """Nothing about the writing changes across these draws. Only `n` does."""
    few, many = _mean_cv(_burstiness, 3), _mean_cv(_burstiness, 100)
    assert many - few > 0.08, f"gradient {many - few:.4f}"


def test_the_corrected_estimator_is_nearly_flat_and_lands_near_the_truth():
    values = [_mean_cv(burstiness_bias_corrected, n) for n in (3, 4, 10, 100)]
    assert max(values) - min(values) < 0.03, f"gradient {max(values) - min(values):.4f}: {values}"
    for value in values:
        assert abs(value - TRUE_CV) < 0.04, f"{value:.4f} against a true {TRUE_CV}"


def test_the_correction_is_at_least_three_times_flatter():
    """The comparison, as a ratio, so it survives the fixture's exact distribution changing."""
    shipped = _mean_cv(_burstiness, 100) - _mean_cv(_burstiness, 3)
    corrected = abs(_mean_cv(burstiness_bias_corrected, 100)
                    - _mean_cv(burstiness_bias_corrected, 3))
    assert shipped > 3 * corrected, f"shipped {shipped:.4f} against corrected {corrected:.4f}"


def test_the_bias_is_worth_a_tenth_of_a_score():
    """Why it matters. `burst_signal` is `(0.55 - cv) / 0.55` at weight 0.6, so the CV gradient is
    handed straight to documents that happen to have fewer sentences."""
    signal = lambda cv: clamp01((0.55 - cv) / 0.55)  # noqa: E731
    few = signal(_mean_cv(_burstiness, 3))
    many = signal(_mean_cv(_burstiness, 100))
    assert 0.6 * (few - many) > 0.08, f"{0.6 * (few - many):.4f} of score from sample size alone"


@pytest.mark.parametrize("estimator", [_burstiness, burstiness_bias_corrected])
def test_both_estimators_refuse_a_single_sentence(estimator):
    """A CV of one length is undefined; the detector has a separate branch for that case and both
    estimators must keep returning the value it expects."""
    assert estimator(_sentences([20])) == 0.0
    assert estimator([]) == 0.0
    assert estimator(_sentences([0, 0])) == 0.0


def test_the_correction_never_lowers_the_estimate():
    """Bessel and the 1/4n term both increase it, so the corrected value is always at least the
    shipped one — which is what makes the direction of the score change predictable."""
    rng = random.Random(3)
    for _ in range(300):
        lengths = [max(1, int(rng.gauss(20, 9))) for _ in range(rng.randrange(2, 12))]
        sentences = _sentences(lengths)
        assert burstiness_bias_corrected(sentences) >= _burstiness(sentences) - 1e-12


def test_the_shipped_default_is_unchanged():
    """The correction is deliberately not wired in: swapping it would move the false-positive rate
    from 19.44% to 12.41% and no AI-labelled corpus is reachable here to price the other half.

    If someone wires it in, this fails and points at the measurement that has to come first.
    """
    import inspect

    from untell.detectors import perplexity_burstiness as module

    source = inspect.getsource(module.lite_score)
    assert "burstiness_bias_corrected" not in source, (
        "the corrected estimator is now in the scoring path. Before that lands, measure detection "
        "power on an AI-labelled corpus — a detector that fires less always has fewer false "
        "positives, and only half the trade-off has been measured."
    )
