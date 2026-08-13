"""What best-of-N ranks on, and the guarantee that changing it cannot change the default.

Result 163 measured that improving the tier `max` stops improving a detector the loop never sees, so
the objective itself is the thing under test. These modes exist to be measured against the holdout,
which means two properties matter more than the modes themselves: an unset or unknown
`UNTELL_SELECT` must reproduce today's behaviour exactly, and the adoption guard must stay on `max`
so an alternative objective can reorder safe candidates without ever adopting a worse one.
"""

from __future__ import annotations

import random

import pytest

from untell.scripts import run as R

SCORE = {
    "max": 0.9,
    "mean": 0.5,
    "detectors": {"a": 0.9, "b": 0.4, "c": 0.3, "d": 0.2, "e": 0.1, "f__error": "boom"},
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("UNTELL_SELECT", raising=False)


class TestTheDefaultIsUntouched:
    def test_unset_ranks_on_the_tier_max(self):
        assert R._selection_mode() == "max"
        assert R._objective(SCORE, None) == 0.9

    def test_an_unknown_mode_falls_back_rather_than_failing(self, monkeypatch):
        """A typo in an env var must not silently select a different objective."""
        monkeypatch.setenv("UNTELL_SELECT", "maximum")
        assert R._selection_mode() == "max"
        assert R._objective(SCORE, None) == 0.9

    def test_max_mode_never_asks_for_a_subset(self):
        assert R._selection_subset(SCORE, random) is None


class TestMean:
    def test_mean_mode_ranks_on_the_ensemble_mean(self, monkeypatch):
        monkeypatch.setenv("UNTELL_SELECT", "mean")
        assert R._objective(SCORE, None) == 0.5

    def test_a_missing_mean_falls_back_to_max(self, monkeypatch):
        """Some score dicts carry no `mean`; ranking on None would raise mid-loop."""
        monkeypatch.setenv("UNTELL_SELECT", "mean")
        assert R._objective({"max": 0.7, "detectors": {"a": 0.7}}, None) == 0.7


class TestDropout:
    def test_the_subset_is_a_strict_subset_of_the_live_detectors(self, monkeypatch):
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        random.seed(0)
        subset = R._selection_subset(SCORE, random)
        assert subset is not None
        assert subset < set(R._live_detectors(SCORE)), "dropout must actually drop something"

    def test_the_error_key_is_never_rankable(self, monkeypatch):
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        assert "f__error" not in R._live_detectors(SCORE)

    def test_the_subset_is_reproducible_from_the_loop_seed(self, monkeypatch):
        """A run has to be re-runnable; an unseeded objective is the Result 144 defect again."""
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        random.seed(7)
        first = R._selection_subset(SCORE, random)
        random.seed(7)
        assert R._selection_subset(SCORE, random) == first

    def test_successive_draws_differ_so_no_member_is_always_present(self, monkeypatch):
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        random.seed(0)
        draws = [R._selection_subset(SCORE, random) for _ in range(12)]
        assert len(set(draws)) > 1
        always = set.intersection(*(set(d) for d in draws))
        assert not always, f"{always} appears in every subset, so it can still be gamed"

    def test_too_few_detectors_falls_back_to_the_whole_tier(self, monkeypatch):
        """Ranking on a subset of two is noise, not an ensemble."""
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        thin = {"max": 0.8, "mean": 0.5, "detectors": {"a": 0.8, "b": 0.2}}
        assert R._selection_subset(thin, random) is None

    def test_ranking_on_a_subset_can_differ_from_the_tier_max(self, monkeypatch):
        """The whole point: a candidate is not judged on the member it may be exploiting."""
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        without_a = frozenset({"b", "c", "d"})
        assert R._objective(SCORE, without_a) == 0.4
        assert R._objective(SCORE, without_a) < SCORE["max"]

    def test_an_empty_subset_falls_back_rather_than_ranking_on_nothing(self, monkeypatch):
        monkeypatch.setenv("UNTELL_SELECT", "dropout")
        assert R._objective(SCORE, frozenset({"nonexistent"})) == 0.9
