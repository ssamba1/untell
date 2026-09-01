"""A fairness arm that needs no protected attribute — and must not pretend it has one.

Status row 28 (detectors against neurodivergent and disabled writers) stayed open from round sixteen
to round thirty on one stated blocker: no corpus carries that label with consent, and asking
applicants to declare a disability so a detector can be audited against them is not a protocol this
project would propose. *Centering the Margins* (2023.emnlp-main.579) removes the blocker by
operationalising the margins of a dataset through **outlier detection** instead of subgroup labels.

`eval/outlier_fairness.py` is that method pointed at AI-text detection. The risk it carries is not
statistical, it is rhetorical: a module that sorts people into "margin" and "centre" is one careless
sentence away from claiming it has identified a protected group. It has not, and these tests hold it
to that as firmly as they hold the arithmetic.
"""

from __future__ import annotations

import pytest

from eval import outlier_fairness as of

# Twelve uniform sentences and one that is nothing like them.
UNIFORM = [f"The system processes input number {i} and returns a result to the caller." for i in range(12)]
ODD = ["Whimsy! Cascading, luminous — a riotous, unpunctuated sprawl of clauses that wanders."]


def test_features_survive_degenerate_input():
    """Empty and punctuation-only text reach this from real corpora; a ZeroDivisionError here would
    take down an audit run partway through."""
    for text in ("", "   ", "!!!", "."):
        f = of.features(text)
        assert f["words"] == 0.0
        assert all(isinstance(v, float) for v in f.values())


def test_a_text_unlike_the_corpus_scores_further_from_the_centre():
    scores = of.outlier_scores(UNIFORM + ODD)
    assert scores[-1] > max(scores[:-1]), "the outlier is not the furthest from the norm"


def test_the_centre_is_robust_to_the_outliers_it_is_measuring():
    """The median and MAD are used rather than mean and standard deviation on purpose. With mean and
    SD, a large outlier inflates the scale it is measured against and reports itself as ordinary —
    which is how an outlier analysis quietly concludes that nothing is unusual."""
    extreme = ["word " * 500]
    with_extreme = of.outlier_scores(UNIFORM + ODD + extreme)
    # The odd sentence must still read as distant even with a much larger outlier present.
    assert with_extreme[len(UNIFORM)] > 1.0


def test_a_corpus_too_small_to_split_refuses_rather_than_guessing():
    result = of.probe_by_distance(["short text"] * 4)
    assert "error" in result and result["gap"] is None if "gap" in result else "error" in result


def test_an_impossible_quantile_is_rejected():
    with pytest.raises(ValueError, match="quantile must be in"):
        of.probe_by_distance(UNIFORM + ODD, quantile=0.9)


def test_the_report_denies_that_outlier_status_is_a_protected_attribute():
    """The claim this module must never make. 'Further from the norm' collects non-native writers,
    disabled writers, unusual subject matter and anyone with a strong idiolect — the whole point is
    that it does not need to know which, and it must not imply that it does."""
    report = of.probe_by_distance(UNIFORM + ODD, tier="lite")
    note = report["note"].lower()
    assert "not a protected attribute" in note
    assert "says nothing about which attribute" in note


def test_a_gap_is_reported_with_whether_the_intervals_overlap():
    """A difference between two small proportions is not a finding. Publishing one without its
    intervals is the defect this repo built `wilson_interval` to prevent."""
    report = of.probe_by_distance(UNIFORM + ODD, tier="lite")
    if report.get("gap") is None:
        pytest.skip("corpus too small on one side in this environment")
    assert report["intervals_overlap"] in (True, False)
    for side in ("margin", "centre"):
        assert len(report[side]["ci95"]) == 2


def test_the_rendering_says_when_a_gap_means_nothing():
    text = of._render({
        "tier": "lite", "quantile": 0.2, "detectors_scoring": 1, "distance_cut": 1.0,
        "margin": {"n": 30, "flagged": 4, "fpr": 0.1333, "ci95": [0.053, 0.297]},
        "centre": {"n": 120, "flagged": 15, "fpr": 0.125, "ci95": [0.077, 0.196]},
        "gap": 0.0083, "intervals_overlap": True, "note": "n/a",
    })
    assert "not evidence of a disparity" in text
    assert "one detector scored" in text, "a single-detector run must say so"


def test_the_rendering_reports_a_corpus_it_could_not_use():
    assert "cannot run" in of._render({"error": "need at least 10 texts", "n": 4})
