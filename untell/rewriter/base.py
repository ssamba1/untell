"""Rewriter protocol + provider factory.

Two providers are supported, both optional: Anthropic (``ANTHROPIC_API_KEY``) and OpenAI
(``OPENAI_API_KEY``). A rewriter is *available* only when its SDK is importable and its key is
set; otherwise ``get_rewriter`` returns ``None`` and the caller falls back to the scripted
rewriter. Network calls live behind ``rewrite`` so importing this module stays cheap and offline.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from untell._retry import retry

from .prompts import build_rewrite_prompt

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@runtime_checkable
class Rewriter(Protocol):
    """A programmatic rewriter that turns flagged text into a humanized rewrite."""

    name: str

    def available(self) -> bool:
        """True when the SDK is importable and an API key is configured."""
        ...

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        """Return a rewritten version of ``text`` guided by ``score_result``."""
        ...


class AnthropicRewriter:
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL):
        self.model = model

    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return True

    def _client(self):
        import anthropic

        return anthropic.Anthropic()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        prompt = build_rewrite_prompt(text, score_result, threshold)
        resp = retry(
            self._client().messages.create,
            kw={"model": self.model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]},
            max_attempts=3,
        )
        # content is a list of blocks; concatenate the text blocks.
        parts = [getattr(b, "text", "") for b in resp.content]
        return "".join(parts).strip()


class OpenAIRewriter:
    name = "openai"

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL):
        self.model = model

    def available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except Exception:
            return False
        return True

    def _client(self):
        import openai

        return openai.OpenAI()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        prompt = build_rewrite_prompt(text, score_result, threshold)
        resp = retry(
            self._client().chat.completions.create,
            kw={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            max_attempts=3,
        )
        return (resp.choices[0].message.content or "").strip()


def get_rewriter(prefer: str | None = None) -> Rewriter | None:
    """Return the first available rewriter, or ``None`` if none are configured.

    ``prefer`` (``"anthropic"`` | ``"openai"`` | ``"local"`` | ``"surgical"`` |
    ``"structural"`` | ``"composite"``) forces a provider order.

    * ``"surgical"`` — deterministic word-substitution rewriter (always available, $0).
    * ``"structural"`` — sentence-level structural rewriter (always available, $0).
    * ``"composite"`` — structural + surgical chained (always available, $0).
    * ``"local"`` — trained LoRA policy if available.
    * ``"anthropic"`` or ``"openai"`` — hosted LLM (needs API key).

    A trained local policy (``UNTELL_POLICY_DIR`` set + adapter present) is preferred by
    default — it's the moat: local, no key, single forward pass. ``prefer="surgical"`` returns the
    deterministic no-key word-substitution rewriter, making the loop runnable at $0.
    """
    from .composite import CompositeRewriter
    from .local_policy import LocalPolicyRewriter
    from .structural import StructuralRewriter
    from .surgical import SurgicalRewriter

    # Always-available free rewriters.
    if prefer == "surgical":
        return SurgicalRewriter()
    if prefer == "structural":
        return StructuralRewriter()
    if prefer == "composite":
        return CompositeRewriter()
    if prefer == "neural":
        # Neural composite: T5 paraphrase front-stage + structural + surgical. Falls back to the
        # plain rule-based composite when T5's deps (.[full]) are absent, so it is never None.
        return CompositeRewriter(use_t5=True)
    if prefer == "mt_pivot":
        from .mt_pivot import MTPivotRewriter

        rw = MTPivotRewriter()
        return rw if rw.available() else None
    if prefer == "t5_paraphrase":
        from .t5_paraphrase import T5ParaphraseRewriter

        rw = T5ParaphraseRewriter()
        return rw if rw.available() else None

    # Hosted / local-policy rewriters.
    local = LocalPolicyRewriter()
    candidates = [AnthropicRewriter(), OpenAIRewriter()]
    if prefer == "openai":
        candidates = [OpenAIRewriter(), AnthropicRewriter()]
    if prefer == "local":
        candidates = [local, *candidates]
    elif local.available() and prefer is None:
        candidates = [local, *candidates]
    for rw in candidates:
        if rw.available():
            return rw
    return None
