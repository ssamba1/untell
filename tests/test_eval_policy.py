"""Tests for the offline policy A/B eval.

The module had no tests, and two of its defects are the kind that produce a *flattering* number
rather than an error: an unscored sample counted as a bypass, and a --threshold that moved the
scoreboard without moving the rewriter.
"""

from __future__ import annotations

from unittest.mock import patch

from eval.eval_policy import _eval, _summary


class _FakeRewriter:
    """Records the threshold it was handed so the plumbing can be asserted on."""

    name = "fake"

    def __init__(self):
        self.thresholds: list[float] = []

    def rewrite(self, text, score, threshold):
        self.thresholds.append(threshold)
        return text + " rewritten"


def _rows(*specs):
    return [
        {"pre": pre, "post": post, "sim": 0.9, "scored": scored}
        for pre, post, scored in specs
    ]


def test_summary_excludes_unscored_rows_instead_of_counting_them_as_bypasses():
    """A dead detector stack must not read as a perfect policy.

    score_text returns max: 0.0 as a placeholder when nothing scored, and 0.0 < threshold is
    true — so unscored samples used to inflate the bypass rate to the most flattering value
    available. Here one real sample failed and one is unscored: the honest answer is 0%.
    """
    out = _summary("policy", _rows((0.9, 0.8, True), (0.0, 0.0, False)), 0.30)
    assert "bypass 0%" in out
    assert "1/2 unscored, excluded" in out
    assert "0.900 -> 0.800" in out  # means come from the scored row only


def test_summary_reports_not_measured_when_nothing_scored():
    out = _summary("policy", _rows((0.0, 0.0, False), (0.0, 0.0, False)), 0.30)
    assert "NOT MEASURED" in out
    assert "bypass" not in out  # no number to report, so none is offered
    assert "mean sim" in out  # similarity does not depend on the detector stack


def test_summary_counts_a_real_bypass():
    out = _summary("policy", _rows((0.9, 0.1, True), (0.9, 0.8, True)), 0.30)
    assert "bypass 50%" in out
    assert "unscored" not in out


def test_eval_passes_the_threshold_through_to_the_rewriter():
    """--threshold used to move only the scoreboard: the rewrite call hardcoded 0.30."""
    rw = _FakeRewriter()
    with patch("untell.scripts.score.score_text", return_value={"max": 0.5}), \
         patch("untell.scripts.quality.similarity", return_value=0.9):
        _eval(rw, ["a sample"], "lite", 0.12)
    assert rw.thresholds == [0.12]


def test_eval_marks_rows_unscored_when_no_detector_produced_a_number():
    rw = _FakeRewriter()
    with patch("untell.scripts.score.score_text", return_value={"max": 0.0, "scored": False}), \
         patch("untell.scripts.quality.similarity", return_value=0.9):
        rows = _eval(rw, ["a sample"], "lite", 0.30)
    assert rows[0]["scored"] is False


def test_eval_marks_rows_scored_when_detectors_worked():
    rw = _FakeRewriter()
    with patch("untell.scripts.score.score_text", return_value={"max": 0.42}), \
         patch("untell.scripts.quality.similarity", return_value=0.9):
        rows = _eval(rw, ["a sample"], "lite", 0.30)
    assert rows[0]["scored"] is True
    assert rows[0]["pre"] == 0.42
