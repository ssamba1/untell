"""Fast pure-math tests for detector calibration logits (no model loads).

Every supervised adapter ends with a logistic squash:
    clamp01(1.0 / (1.0 + exp(±(x - MID) / SCALE)))
Pinning the constants and the squash shape catches calibration regressions — the
class of bug that made fast_detectgpt emit a near-constant 0.30 and binoculars
misplace the human midpoint. (History: fdg constants were re-centred twice after
measured miscalibration; the constants are the product's decision, not trivia.)
"""

from __future__ import annotations

import math

from untell.detectors import binoculars as BIN
from untell.detectors import fast_detectgpt as FDG


def _squash(x: float, mid: float, scale: float) -> float:
    return 1.0 / (1.0 + math.exp(-(x - mid) / scale))


class TestFastDetectGPTConstants:
    """The calibration midpoint is the class boundary (~+0.16 separates HC3 halves).

    At x == _CAL_MID the logistic is 0.5: the detector must say "exactly unsure"
    when the discrepancy is at the measured class boundary, not 0.30 (the old
    broken constant) or 0.9."""

    def test_midpoint_is_exactly_unsure(self) -> None:
        assert _squash(FDG._CAL_MID, FDG._CAL_MID, FDG._CAL_SCALE) == 0.5

    def test_ai_side_saturates(self) -> None:
        # 0.16 above mid (AI range) -> high probability
        assert _squash(FDG._CAL_MID + 0.16, FDG._CAL_MID, FDG._CAL_SCALE) > 0.85

    def test_human_side_saturates(self) -> None:
        assert _squash(FDG._CAL_MID - 0.16, FDG._CAL_MID, FDG._CAL_SCALE) < 0.15

    def test_scale_is_measured_not_default(self) -> None:
        # The default inherited scale was 1.2; the fitted scale is 0.08.
        # A regression to a flat logistic fails the saturation tests above.
        assert FDG._CAL_SCALE < 0.5


class TestBinocularsConstants:
    """binoculars: HIGH binoculars score = HUMAN (inverted logistic).

    The squash is 1/(1+exp((x - MID)/SCALE)) — note the sign. At x == MID it is
    0.5; above MID it drops (AI-like), below it rises (human-like)."""

    def test_midpoint_is_exactly_unsure(self) -> None:
        inv = 1.0 / (1.0 + math.exp((BIN._CAL_MID - BIN._CAL_MID) / BIN._CAL_SCALE))
        assert inv == 0.5

    def test_above_mid_drops(self) -> None:
        x = BIN._CAL_MID + 0.2
        high = 1.0 / (1.0 + math.exp((x - BIN._CAL_MID) / BIN._CAL_SCALE))
        assert high < 0.15

    def test_below_mid_rises(self) -> None:
        x = BIN._CAL_MID - 0.2
        low = 1.0 / (1.0 + math.exp((x - BIN._CAL_MID) / BIN._CAL_SCALE))
        assert low > 0.85
