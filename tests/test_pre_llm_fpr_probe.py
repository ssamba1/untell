"""A false-positive rate measured against text that predates the models needs no labels to dispute.

`eval/pre_llm_fpr.py` implements the probe Bohler et al. used: score writing published before LLMs
existed, and every flag is a false positive by construction. These tests cover the statistics and
the two ways the report could mislead — a degenerate single-detector run presented as consensus, and
a corpus silently contaminated with post-cutoff text.
"""

from __future__ import annotations

import pytest

from eval.pre_llm_fpr import _render, pre_llm_abstracts, wilson_interval


def test_wilson_interval_matches_the_published_worked_example():
    """The repo's docs say a 17% rate on n=30 spans roughly 7-35%. That claim is checked here."""
    low, high = wilson_interval(5, 30)
    assert 0.06 < low < 0.09, low
    assert 0.31 < high < 0.36, high


def test_a_zero_rate_still_carries_an_upper_bound():
    """0/50 is not 'a 0% false-positive rate'. The normal approximation gives a degenerate [0, 0];
    Wilson keeps the upper bound that makes the claim honest."""
    low, high = wilson_interval(0, 50)
    assert low == 0.0
    assert high > 0.05, "zero observed failures must not read as proof of zero risk"


def test_intervals_narrow_as_the_sample_grows():
    narrow = wilson_interval(10, 1000)
    wide = wilson_interval(1, 100)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_no_sample_is_maximally_uncertain_rather_than_confident():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_the_year_filter_excludes_post_cutoff_volumes(tmp_path):
    """Contamination is the one failure that would invert the result: a post-ChatGPT abstract in a
    'pre-LLM' corpus turns a false positive into a possible true one, and the number stops meaning
    what the module's docstring says it means."""
    (tmp_path / "v.xml").write_text(
        "<collection id='2021.acl'><volume id='long'>"
        "<paper id='1'><title>Old</title><abstract>" + "word " * 70 + "</abstract></paper>"
        "</volume></collection>", encoding="utf-8")
    (tmp_path / "w.xml").write_text(
        "<collection id='2024.acl'><volume id='long'>"
        "<paper id='1'><title>New</title><abstract>" + "token " * 70 + "</abstract></paper>"
        "</volume></collection>", encoding="utf-8")
    kept = pre_llm_abstracts(tmp_path, min_words=60, max_year=2021)
    assert len(kept) == 1
    assert kept[0].startswith("word")


def test_short_abstracts_are_excluded(tmp_path):
    """Below the length floor the ensemble measures its own short-text failure rather than the
    corpus — this repo has measured one member flagging 100% of human text at 40 words."""
    (tmp_path / "v.xml").write_text(
        "<collection id='2021.acl'><volume id='long'>"
        "<paper id='1'><title>T</title><abstract>too short</abstract></paper>"
        "</volume></collection>", encoding="utf-8")
    assert pre_llm_abstracts(tmp_path, min_words=60, max_year=2021) == []


def test_a_single_detector_run_says_it_is_not_agreement():
    """Three identical rows look like consensus. With one detector they are one measurement printed
    three times, and the report has to say so or it flatters itself."""
    report = {
        "n_scored": 10, "tier": "lite", "detectors_scoring": 1,
        "by_rule": {r: {"flagged": 2, "n": 10, "fpr": 0.2, "ci95": [0.05, 0.51]}
                    for r in ("any", "majority", "unanimous")},
        "by_detector": {"only": {"flagged": 2, "n": 10, "fpr": 0.2, "ci95": [0.05, 0.51]}},
    }
    assert "not agreement" in _render(report)


def test_a_multi_detector_run_does_not_carry_the_warning():
    report = {
        "n_scored": 10, "tier": "full", "detectors_scoring": 3,
        "by_rule": {"any": {"flagged": 3, "n": 10, "fpr": 0.3, "ci95": [0.1, 0.6]},
                    "majority": {"flagged": 1, "n": 10, "fpr": 0.1, "ci95": [0.0, 0.4]},
                    "unanimous": {"flagged": 0, "n": 10, "fpr": 0.0, "ci95": [0.0, 0.3]}},
        "by_detector": {},
    }
    assert "not agreement" not in _render(report)


@pytest.mark.parametrize("successes,total", [(0, 10), (5, 10), (10, 10)])
def test_intervals_stay_inside_zero_and_one(successes, total):
    low, high = wilson_interval(successes, total)
    assert 0.0 <= low <= high <= 1.0
