"""Killing tests for base.py mutation survivors (2026-08-14 sweep, wave 2).

Killability designed by swarm-a (budget-limited, never materialized) and
verified here:

  line 66  constant: False -> True   AnthropicRewriter.available() no-key gate.
  line 98  constant: False -> True   OpenAIRewriter.available() no-key gate.
  line 78  constant: 2048 -> 2049    Anthropic max_tokens payload.
  line 79  constant: 3 -> 4          Anthropic max_attempts.

The key-gated rewrite paths are exercised via a fake _client that records the
payload and returns a canned response.
"""

from __future__ import annotations

import pytest

from untell.rewriter.base import AnthropicRewriter, OpenAIRewriter


class TestAvailableNoKey:
    """Survivors 66/98 — `return False` -> `return True` in the no-key branch.

    Without ANTHROPIC_API_KEY/OPENAI_API_KEY the rewriter must report
    unavailable. The mutation flips it to True, claiming a client that cannot
    exist."""

    def test_anthropic_unavailable_without_key(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert AnthropicRewriter().available() is False

    def test_openai_unavailable_without_key(self, monkeypatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert OpenAIRewriter().available() is False


class TestPayloadPinned:
    """Survivor 78 — `max_tokens: 2048` -> 2049 in the Anthropic payload.

    The API payload is captured through a fake client."""

    def test_anthropic_max_tokens_payload(self, monkeypatch) -> None:
        rw = AnthropicRewriter()
        captured = {}

        class _FakeMessages:
            def create(self, **kw):
                captured.update(kw)
                return type("R", (), {"content": [type("B", (), {"text": "ok"})]})()

        class _FakeClient:
            messages = _FakeMessages()

        monkeypatch.setattr(rw, "_client", lambda: _FakeClient())
        monkeypatch.setattr(
            "untell.rewriter.base.build_rewrite_prompt",
            lambda *a, **k: "prompt",
        )
        out = rw.rewrite("text", {"tier": "lite"}, threshold=0.30)
        assert out == "ok"
        assert captured["max_tokens"] == 2048, captured


class TestRetryCount:
    """Survivor 79 — `max_attempts: 3` -> 4 in the retry wrapper.

    A client that always fails must be tried exactly 3 times (the retry
    wrapper's own max_attempts), then raise."""

    def test_anthropic_retry_count(self, monkeypatch) -> None:
        rw = AnthropicRewriter()
        calls = {"n": 0}

        class _FakeMessages:
            def create(self, **kw):
                calls["n"] += 1
                raise ConnectionError("connection reset")

        class _FakeClient:
            messages = _FakeMessages()

        monkeypatch.setattr(rw, "_client", lambda: _FakeClient())
        monkeypatch.setattr(
            "untell.rewriter.base.build_rewrite_prompt",
            lambda *a, **k: "prompt",
        )
        monkeypatch.setattr("untell._retry.time.sleep", lambda s: None)
        with pytest.raises(ConnectionError):
            rw.rewrite("text", {"tier": "lite"}, threshold=0.30)
        assert calls["n"] == 3, calls
