"""Killing tests for llm_judge.py mutation survivors (2026-08-14 sweep).

  line 102  boundary: >= -> >      percentage-vs-P(AI) disambiguation at exactly 2.0
                                   (same bug class as local_judge.py:178).

Killed here. The other 10 survivors (51/58/70/74/75/78/86/87/90/92) are
key/provider-dependent or API-payload constants — annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from untell.detectors.llm_judge import LLMJudgeDetector


class TestPercentageBoundary:
    """Survivor llm_judge.py:102 — `val >= 2.0` mutated to `>`.

    A judge reply of exactly "2.0" is a percentage (2.0% => 0.02 P(AI)), not a
    P(AI) of 2.0. The mutation would clamp 2.0 to 1.0 — a percentage read as
    certainty. Same class as the local_judge.py:178 kill."""

    def test_exactly_two_point_zero_is_percent(self, monkeypatch) -> None:
        d = LLMJudgeDetector()
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
        monkeypatch.setattr(d, "available", lambda: True)
        monkeypatch.setattr(d, "_complete", lambda text: "2.0")
        result = d.score("some text to judge")
        assert result is not None
        assert result == pytest.approx(0.02), f"expected 0.02, got {result}"

    def test_just_above_two_is_percent(self, monkeypatch) -> None:
        d = LLMJudgeDetector()
        monkeypatch.setattr(d, "available", lambda: True)
        monkeypatch.setattr(d, "_complete", lambda text: "73")
        result = d.score("some text to judge")
        assert result == pytest.approx(0.73), f"expected 0.73, got {result}"

    def test_below_two_is_not_percent(self, monkeypatch) -> None:
        d = LLMJudgeDetector()
        monkeypatch.setattr(d, "available", lambda: True)
        monkeypatch.setattr(d, "_complete", lambda text: "1.5")
        result = d.score("some text to judge")
        assert result == pytest.approx(1.0), f"expected clamped 1.0, got {result}"
