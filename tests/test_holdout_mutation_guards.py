"""Killing tests for eval/holdout.py mutation survivors (2026-08-14 sweep).

  line 208  boundary: >= -> >      out-of-sample flagged_pre (FLAG_BAR 0.45).
  line 213  boundary: < -> <=      improved_on (strict improvement).

Killed here with monkeypatched detector/pairs/untell_text. Other survivors
(89/93/94/99/164/168/172/173/195/201/202/207/278) are constants or boundaries
annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from eval import holdout as H


class TestOutOfSampleFlags:
    """Survivor holdout.py:208 — `holdout_pre >= FLAG_BAR` -> `>`.

    A pre score EXACTLY at FLAG_BAR (0.45) is flagged. The mutation excludes
    it, undercounting flagged_pre."""

    def test_exact_flag_bar_pre_counts_as_flagged(self, monkeypatch) -> None:
        # detector returns exactly 0.45 for every holdout score
        class _FakeDetector:
            name = "fake-radar"

            def score(self, text):
                return 0.45

        def _pairs(dataset, n=10, min_words=60):
            return [(f"human-{i}", f"ai-{i}") for i in range(2)]

        def _untell(*a, **k):
            return {
                "pre": {"max": 0.5, "mean": 0.5},
                "post": {"max": 0.5, "mean": 0.5},
                "similarity": 0.9,
                "final": f"final-{k.get('seed', 0)}",
            }

        monkeypatch.setattr(H, "_holdout_detector", lambda: _FakeDetector())
        monkeypatch.setattr(H, "load_pairs", _pairs)
        monkeypatch.setattr(H, "untell_text", _untell)
        out = H.run(dataset="raid", n=2, tier="lite", seed=1)
        assert out["out_of_sample"]["flagged_pre"] == 2, out["out_of_sample"]


class TestImprovedOn:
    """Survivor holdout.py:213 — `holdout_post < holdout_pre` -> `<=`.

    A post score EQUAL to pre is not an improvement. The mutation counts it,
    inflating improved_on."""

    def test_equal_scores_not_improvement(self, monkeypatch) -> None:
        # holdout_pre and holdout_post BOTH exactly 0.45: equal -> not improved
        class _FakeDetector:
            name = "fake-radar"

            def score(self, text):
                return 0.45

        def _pairs(dataset, n=10, min_words=60):
            return [(f"human-{i}", f"ai-{i}") for i in range(2)]

        def _untell(*a, **k):
            return {
                "pre": {"max": 0.5, "mean": 0.5},
                "post": {"max": 0.5, "mean": 0.5},
                "similarity": 0.9,
                "final": f"final-{k.get('seed', 0)}",
            }

        monkeypatch.setattr(H, "_holdout_detector", lambda: _FakeDetector())
        monkeypatch.setattr(H, "load_pairs", _pairs)
        monkeypatch.setattr(H, "untell_text", _untell)
        out = H.run(dataset="raid", n=2, tier="lite", seed=2)
        # holdout_post == holdout_pre (both 0.45): improved_on must be 0
        assert out["out_of_sample"]["improved_on"] == 0, out["out_of_sample"]
