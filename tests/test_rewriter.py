"""Hosted-LLM rewriter tests — all offline (SDK/clients mocked; no network, no keys needed)."""

from __future__ import annotations

from untell.rewriter import build_rewrite_prompt, get_rewriter
from untell.rewriter.base import AnthropicRewriter, OpenAIRewriter

SCORE = {"detectors": {"mage": 0.88, "roberta_openai": 0.71, "fast_detectgpt": 0.40}, "max": 0.88}


def test_prompt_names_worst_detectors_and_threshold():
    p = build_rewrite_prompt("Some flagged text here.", SCORE, threshold=0.30)
    assert "mage" in p and "0.88" in p  # worst detector + its score
    assert "0.30" in p  # target threshold
    assert "sentinel" in p.lower()  # preserve-sentinel instruction
    assert "Some flagged text here." in p  # the text itself
    # the instruction forbids injecting AI tells and pushes plain prose (not score-gaming)
    assert "em-dash" in p.lower()
    assert "plain" in p.lower()


def test_prompt_handles_no_detectors():
    p = build_rewrite_prompt("text", {"detectors": {}, "max": 0.5}, threshold=0.2)
    assert "0.20" in p


def test_prompt_includes_flagged_sentences():
    sr = {"detectors": {"mage": 0.8}, "max": 0.8, "flagged_sentences": ["This sentence reads as AI."]}
    p = build_rewrite_prompt("text", sr, threshold=0.30)
    assert "This sentence reads as AI." in p
    assert "REWRITE THESE" in p


def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert AnthropicRewriter().available() is False
    assert OpenAIRewriter().available() is False


def test_get_rewriter_none_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_rewriter() is None


def test_anthropic_rewrite_sends_prompt_and_returns_text(monkeypatch):
    rw = AnthropicRewriter()
    captured: dict = {}

    class _Block:
        def __init__(self, t):
            self.text = t

    class _Resp:
        content = [_Block("REWRITTEN HUMAN TEXT")]

    class _Messages:
        def create(self, **kw):
            captured.update(kw)
            return _Resp()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(rw, "_client", lambda: _Client())
    out = rw.rewrite("AI text", SCORE, threshold=0.30)
    assert out == "REWRITTEN HUMAN TEXT"
    sent = captured["messages"][0]["content"]
    assert "mage" in sent and "AI text" in sent


def test_openai_rewrite_sends_prompt_and_returns_text(monkeypatch):
    rw = OpenAIRewriter()

    class _Msg:
        content = "OPENAI REWRITE"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kw):
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(rw, "_client", lambda: _Client())
    assert rw.rewrite("AI text", SCORE) == "OPENAI REWRITE"
