"""Killing tests for eval/compare_humanizers.py mutation survivors (2026-08-14 sweep).

  line 70   logic: is False -> is True   _ai_max scored-gate.
  line 178  logic: != -> ==             none-baseline similarity branch.

Killed here via _ai_max and compare() with monkeypatched deps. Other survivors
(79/92/133/197/198/200/267/290/295) are constants — annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from eval import compare_humanizers as C


class TestAiMaxScoredGate:
    """Survivor compare_humanizers.py:70 — `scored is False` -> `is True`.

    A scored result (scored=True, the normal case) returns its max. The
    mutation returns None for every scored result, silently dropping every
    technique's numbers."""

    def test_scored_result_returns_max(self, monkeypatch) -> None:
        monkeypatch.setattr(
            C, "score_text",
            lambda text, tier: {"max": 0.42, "scored": True},
        )
        assert C._ai_max("some text", "lite") == 0.42

    def test_unscored_result_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            C, "score_text",
            lambda text, tier: {"max": 0.0, "scored": False},
        )
        assert C._ai_max("some text", "lite") is None


class TestNoneBaselineSimilarity:
    """Survivor compare_humanizers.py:178 — `name != "none (raw AI)"` -> `==`.

    The none-baseline appends 1.0 (raw AI is perfectly similar to itself);
    every other technique appends its real similarity. The mutation swaps the
    branches. Drive the real compare() and inspect sim_mean."""

    def test_none_baseline_sim_is_one(self, monkeypatch) -> None:
        texts = ["original sample text one.", "original sample text two."]

        def _techniques(tier, threshold):
            return {"none (raw AI)": lambda t: t}

        monkeypatch.setattr(C, "_techniques", _techniques)
        monkeypatch.setattr(C, "_ai_max", lambda out, tier: 0.5)
        monkeypatch.setattr(C, "score_tells", lambda out: {"tells_per_100w": 1.0, "tells": 1})
        monkeypatch.setattr("untell.scripts.quality.similarity", lambda a, b: 0.123)
        out = C.compare(texts, tier="lite", threshold=0.3)
        tech = out["techniques"]["none (raw AI)"]
        assert tech["sim_mean"] == 1.0, f"none-baseline sim must be 1.0: {tech}"
