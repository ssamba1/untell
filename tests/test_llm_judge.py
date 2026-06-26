"""LLM-as-judge detector tests — offline (no key => unavailable; completion mocked otherwise)."""

from __future__ import annotations

from untell.detectors.llm_judge import LLMJudgeDetector


def test_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    d = LLMJudgeDetector()
    assert d.available() is False
    assert d.score("some text") is None  # unavailable => no signal (excluded from the ensemble)


def test_score_parses_number(monkeypatch):
    d = LLMJudgeDetector()
    monkeypatch.setattr(d, "available", lambda: True)
    monkeypatch.setattr(d, "_complete", lambda prompt: "0.82")
    assert d.score("text") == 0.82


def test_score_handles_percentage(monkeypatch):
    d = LLMJudgeDetector()
    monkeypatch.setattr(d, "available", lambda: True)
    monkeypatch.setattr(d, "_complete", lambda prompt: "I'd rate this 73")
    assert d.score("text") == 0.73  # a percentage answer is normalized to [0,1]


def test_empty_and_unparseable_return_none(monkeypatch):
    d = LLMJudgeDetector()
    monkeypatch.setattr(d, "available", lambda: True)
    monkeypatch.setattr(d, "_complete", lambda prompt: "0.5")
    assert d.score("   ") is None  # empty input => no signal
    monkeypatch.setattr(d, "_complete", lambda prompt: "no idea")
    assert d.score("real text") is None  # no number in the reply => None, not a crash


def test_registered_in_commercial_tier():
    from untell.detectors.base import all_detectors

    names = {d.name for d in all_detectors()}
    assert "llm_judge" in names
