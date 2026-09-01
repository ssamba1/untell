"""A conformal bound calibrated across all lengths is not a bound at any of them.

`calibrate()` returns one threshold for a corpus, and `calibrate_by_length()` has existed since it
shipped with a docstring saying that one threshold "is one average". Nobody had measured the cost.
Round seventy-two did, on all 6,810 pre-LLM abstracts: the global alpha=0.05 threshold delivers
**10.78%** on 60-100-word documents and **2.55%** on 200+, against the 5% it promises. The short
band's 95% CI is [8.55%, 13.51%] — nowhere near 5%, so this is a real breach and not sampling noise.

It breaches in the worse direction. Short documents are where a wrong verdict is least recoverable
and where this repo has separately measured the highest false-positive rates, and the corpus floor of
60 words means the 60-100 row is the *mildest* short-document case, not the worst.

The tests here use synthetic scores with a deliberate length effect rather than the real corpus,
because the corpus needs a 25-minute scoring run and a network download. The real figures are in
`untell/calibrate.py`'s docstring and in round seventy-two of the ledger; what this file pins is the
property that makes them possible — that per-band calibration tracks a length effect a single
threshold averages away.
"""

from __future__ import annotations

import random

import pytest

from untell.calibrate import calibrate, calibrate_by_length

ALPHA = 0.05
BANDS = (60, 100, 150, 200)


def _corpus(seed: int = 0, n: int = 4000) -> list[tuple[int, float]]:
    """(word_count, score) pairs where short documents score higher, as they measurably do.

    The effect is the shape this repo measured — 30.0% flagged at 50 words or fewer against 21.7% at
    50-100 — not the magnitude, which the real corpus supplies.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        words = rng.choice([70, 90, 120, 140, 170, 190, 240, 300])
        centre = 0.62 - 0.0009 * words  # shorter -> higher score
        out.append((words, min(1.0, max(0.0, rng.gauss(centre, 0.08)))))
    return out


def _realised(scores: list[float], threshold: float) -> float:
    return sum(s >= threshold for s in scores) / len(scores) if scores else 0.0


def _band(pairs, low, high):
    return [s for words, s in pairs if low <= words < high]


def test_the_global_threshold_misses_its_own_bound_at_the_short_end():
    """The finding. A threshold that holds on the mixture does not hold on its parts."""
    pairs = _corpus()
    threshold = calibrate([s for _, s in pairs], alpha=ALPHA)["threshold"]

    overall = _realised([s for _, s in pairs], threshold)
    assert overall == pytest.approx(ALPHA, abs=0.01), "premise: it must hold on the mixture"

    short = _realised(_band(pairs, 60, 100), threshold)
    long_ = _realised(_band(pairs, 200, 10**9), threshold)
    assert short > 2 * ALPHA, f"short documents should breach the bound, got {short:.2%}"
    assert long_ < ALPHA, f"long documents should be under it, got {long_:.2%}"
    assert short > 3 * long_, (
        f"the spread is the point: {short:.2%} at the short end against {long_:.2%} at the long one")


def test_per_band_thresholds_hold_where_the_global_one_does_not():
    """The fix, on the same corpus."""
    pairs = _corpus()
    per_band = calibrate_by_length(pairs, alpha=ALPHA, bands=BANDS)
    for label, result in per_band.items():
        if result is None:
            continue
        low = int(label.split("-")[0].rstrip("+"))
        high = int(label.split("-")[1]) if "-" in label else 10**9
        realised = _realised(_band(pairs, low, high), result["threshold"])
        assert realised <= ALPHA + 0.02, f"band {label} realised {realised:.2%}"


def test_the_band_thresholds_actually_differ():
    """Guards the guard. If every band returned the same threshold, the test above would pass while
    measuring nothing — and the whole argument for per-band calibration would be empty."""
    per_band = calibrate_by_length(_corpus(), alpha=ALPHA, bands=BANDS)
    thresholds = [r["threshold"] for r in per_band.values() if r]
    assert len(thresholds) >= 3
    assert max(thresholds) - min(thresholds) > 0.05, (
        f"bands should disagree by more than rounding: {sorted(thresholds)}")


def test_a_band_threshold_is_wrong_for_the_other_bands():
    """Applied outside its band, a threshold is too strict or too loose — which is the same finding
    read from the other end, and the reason one number cannot serve both."""
    pairs = _corpus()
    per_band = calibrate_by_length(pairs, alpha=ALPHA, bands=BANDS)
    short = per_band["60-100"]["threshold"]
    long_ = per_band["200+"]["threshold"]
    assert short > long_, "shorter documents need a HIGHER bar, not a lower one"
    everything = [s for _, s in pairs]
    assert _realised(everything, short) < ALPHA
    assert _realised(everything, long_) > ALPHA


def test_a_band_too_small_for_alpha_reports_nothing_rather_than_a_number():
    """The refusal that makes per-band calibration safe to recommend: narrow bands run out of data
    fast, and an unsupported threshold that looks authoritative is worse than a gap."""
    pairs = [(70, 0.5)] * 5 + [(250, 0.5)] * 400
    out = calibrate_by_length(pairs, alpha=ALPHA, bands=BANDS)
    assert out["60-100"] is None
    assert out["200+"] is not None
