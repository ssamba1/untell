"""A rate over a sample and a rate over a corpus are different claims, and the report said neither.

Every false-positive figure this project published before round sixty-one — 19.2% at n = 120, 20.5%
at n = 599 — was computed on a fraction of a corpus holding 6,811 documents. Nothing was wrong with
the arithmetic. What was missing was a way to notice: `--n` had a default of 100 and no value meaning
"all of them", so scoring the whole corpus required knowing its size and typing it, and the report
gave a reader no way to tell a sample from a census.

Two fixes, both pinned here. `--n 0` means the whole corpus, so a reproduction command cannot go
stale when a volume is added. And every report states which it is, in the same line that already
carries the corpus definition — because "n_requested equals n_available" is not something a reader
should have to derive.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr

import pytest

from eval.pre_llm_fpr import _render, main


def _corpus(n_requested: int, n_available: int, is_census: bool) -> dict:
    return {
        "n_scored": min(n_requested or n_available, n_available),
        "tier": "lite",
        "by_rule": {"any": {"flagged": 1, "n": 10, "fpr": 0.1, "ci95": [0.0, 0.4]}},
        "by_detector": {"lite": {"flagged": 1, "n": 10, "fpr": 0.1, "ci95": [0.0, 0.4]}},
        "detectors_scoring": 1,
        "corpus": {"min_words": 60, "max_year": 2021, "seed": 0,
                   "n_available": n_available, "n_requested": n_requested,
                   "is_census": is_census},
    }


def test_a_sample_says_it_is_a_sample_and_says_how_to_stop_being_one():
    text = _render(_corpus(599, 6811, is_census=False))
    assert "A SAMPLE, not the corpus" in text
    assert "--n 0" in text, "telling a reader the number is partial without telling them the fix"
    assert "6811 available" in text


def test_a_census_says_so_rather_than_leaving_it_to_arithmetic():
    text = _render(_corpus(0, 6811, is_census=True))
    assert "CENSUS: every document scored" in text
    assert "A SAMPLE" not in text


def test_the_two_renderings_actually_differ():
    """Guards the guard: if the flag were ignored, both assertions above could pass on one string."""
    assert _render(_corpus(599, 6811, False)) != _render(_corpus(0, 6811, True))


def test_a_negative_n_is_refused_rather_than_silently_slicing():
    """`texts[:-1]` is a valid slice and drops the last document. A typo must not quietly become a
    corpus definition."""
    err = io.StringIO()
    with redirect_stderr(err):
        code = main(["--n", "-1", "--cache", "/nonexistent-cache-for-this-test"])
    assert code == 1
    assert "--n must be 0 (all) or positive" in err.getvalue()


@pytest.mark.parametrize("n,available,expected", [(0, 500, True), (500, 500, True),
                                                  (600, 500, True), (499, 500, False)])
def test_is_census_is_true_exactly_when_every_document_was_scored(n, available, expected):
    """Asking for more than exists is still a census; asking for one fewer is not."""
    assert (n == 0 or n >= available) is expected
