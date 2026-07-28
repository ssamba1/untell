"""Tests for the local LLaMA-as-judge detector — offline (no model download)."""
from __future__ import annotations

from untell.detectors.local_judge import LocalJudgeDetector


def test_unavailable_without_torch():
    """Without torch/transformers, available() must return False."""
    d = LocalJudgeDetector()
    # On a CI/clean install without torch, this is False.
    # We validate the contract: if unavailable, score returns None.
    if not d.available():
        assert d.score("some text") is None


def test_empty_input_returns_none(monkeypatch):
    d = LocalJudgeDetector()
    monkeypatch.setattr(d, "available", lambda: True)
    assert d.score("   ") is None


def test_registered_in_detector_list():
    from untell.detectors.base import all_detectors

    names = {d.name for d in all_detectors()}
    assert "local_judge" in names


def test_tier_heuristic():
    """Small models should be 'full' tier; 7B+ models should be 'heavy'."""
    d_light = LocalJudgeDetector(model_id="Qwen/Qwen2.5-1.5B-Instruct")
    assert d_light.tier == "full"
    d_heavy = LocalJudgeDetector(model_id="Qwen/Qwen2.5-7B-Instruct")
    assert d_heavy.tier == "heavy"
