"""The default rewriter must not go silent because one detector saturates.

`composite` selected candidates on `max` alone with a strict `<`. A detector that returns exactly
1.0 pins `max`, `1.0 < 1.0` is false, and every candidate — however different, however much better
on every other detector — was discarded. The rewriter returned its input byte-identical on the
input it exists for, while `structural`, `surgical` and `targeted` each changed the same text.
"""

from __future__ import annotations

from untell.rewriter.composite import _selection_key


def _result(max_value: float, detectors: dict) -> dict:
    return {"max": max_value, "detectors": detectors, "tier": "full"}


def test_a_tie_on_max_is_broken_by_the_mean():
    """The bug, in one comparison: identical max, materially different ensembles."""
    baseline = _selection_key(_result(1.0, {"mage": 1.0, "roberta_openai": 0.99, "hc3": 0.95}))
    candidate = _selection_key(_result(1.0, {"mage": 1.0, "roberta_openai": 0.30, "hc3": 0.20}))

    assert candidate[0] == baseline[0], "premise: the saturating member pins max for both"
    assert candidate < baseline, "a candidate better on every other detector must be selectable"


def test_a_worse_candidate_is_still_rejected():
    """Guards against re-introducing the reverted 'consolation rewrite'.

    That behaviour adopted a candidate scoring WORSE on the theory that changing the text was
    worth something. Tie-breaking on the mean must not become a back door to it.
    """
    baseline = _selection_key(_result(1.0, {"mage": 1.0, "roberta_openai": 0.20}))
    worse = _selection_key(_result(1.0, {"mage": 1.0, "roberta_openai": 0.90}))
    assert not (worse < baseline)


def test_an_exact_tie_on_both_keeps_the_original():
    same = {"mage": 1.0, "roberta_openai": 0.5}
    assert not (_selection_key(_result(1.0, same)) < _selection_key(_result(1.0, same)))


def test_max_still_dominates_the_mean():
    """Lexicographic, not averaged: a real drop in max wins even if the mean rises."""
    baseline = _selection_key(_result(0.90, {"a": 0.90, "b": 0.10, "c": 0.10}))
    lower_max = _selection_key(_result(0.60, {"a": 0.60, "b": 0.55, "c": 0.55}))

    assert lower_max[1] > baseline[1], "premise: this candidate has the WORSE mean"
    assert lower_max < baseline, "max is the objective; it must still win"


def test_non_numeric_detector_entries_do_not_break_the_key():
    key = _selection_key(_result(0.8, {"a": 0.8, "b": "__error: oom", "c": None}))
    assert key == (0.8, 0.8), "only the numeric members may enter the mean"


def test_booleans_are_not_treated_as_scores():
    """`isinstance(True, int)` is True in Python; a flag in the dict must not become a 1.0 score."""
    assert _selection_key(_result(0.5, {"a": 0.5, "flagged": True}))[1] == 0.5


def test_an_empty_ensemble_falls_back_to_max():
    assert _selection_key(_result(0.42, {})) == (0.42, 0.42)
