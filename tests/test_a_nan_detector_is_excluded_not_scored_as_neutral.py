"""A detector that returns NaN is excluded as failed, never scored as a neutral 0.5.

The aggregation guards against a detector returning NaN *directly* — that guard exists and is
tested. But every real detector routes its model output through ``clamp01``, which used to
convert NaN into 0.5 ("neutral"), and the guard never saw the NaN: the detector returned a
valid-looking 0.5, which the ensemble averaged and flagged on. MEASURED through the real
pipeline, a detector emitting NaN read as ``max=0.5, mean=0.5, flagged=True`` — a broken
component manufacturing a confident verdict.

The fix: ``clamp01`` propagates NaN unchanged, so the aggregation's NaN guard records
``<name>__error: detector returned NaN`` and excludes the detector. ``windowed_max`` drops
NaN windows too, because ``max()`` with a NaN is order-dependent (``max([nan, 0.3])`` is nan,
``max([0.3, nan])`` is 0.3). These tests pin the two surfaces end to end.
"""
from __future__ import annotations

import math

import untell.detectors.base as base
import untell.scripts.score as score_module

TEXT = (
    "It is worth noting that this pivotal approach leverages a robust framework for delivery "
    "today, and the comprehensive solution underscores a seamless outcome for every stakeholder."
)


class _NaN:
    """A detector whose model output is NaN — broken model, unreachable API, malformed response."""

    name, tier = "nan_det", "lite"

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        return float("nan")


def test_clamp01_propagates_nan_instead_of_faking_neutral_05():
    """NaN is a failure signal; 0.5 is a valid-looking score. The aggregation's NaN guard must
    be allowed to see it, or a dead component reads as 'unsure' in every aggregate."""
    assert math.isnan(base.clamp01(float("nan")))


def test_a_nan_detector_is_excluded_with_an_error_not_scored_as_05(monkeypatch):
    """End to end: the real aggregation, the real NaN path. Before the fix this read
    max=0.5, mean=0.5, flagged=True; now the detector is excluded and named as failed."""
    monkeypatch.setattr(score_module, "load_detectors", lambda tier="lite": [_NaN()])
    r = score_module.score_text(TEXT, tier="lite")

    assert r["detectors"]["nan_det"] is None
    assert "nan_det__error" in r["detectors"], "the failure must be named, not silently dropped"
    assert "NaN" in r["detectors"]["nan_det__error"]
    assert "nan_det" in r["failed_detectors"]
    assert r["scored"] is False, "no verdict may be invented from a broken detector"
    assert r["max"] == r["max"] and r["mean"] == r["mean"], "max/mean must not be NaN"
    assert r["max"] != 0.5, "the old neutral-0.5 behaviour must not resurface"


def test_windowed_max_drops_nan_windows_instead_of_poisoning_the_max():
    """max() with a NaN is order-dependent: [nan, 0.3] -> nan but [0.3, nan] -> 0.3. One broken
    window must not be able to nuke or fake the windowed score either way."""
    assert base.windowed_max(
        "AAA " + "one two three four five six seven eight nine ten " * 40,
        lambda w: float("nan") if "AAA" in w else 0.3,
        window_words=40,
    ) == 0.3

    assert base.windowed_max(
        "one two three four five six seven eight nine ten " * 40,
        lambda w: float("nan"),
        window_words=40,
    ) is None, "all-NaN windows are no signal, not a score"
