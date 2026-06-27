"""LLM-as-judge detector — the frontier model scores AI-likelihood against the ai-tells catalog.

The local proxy detectors are weak (they don't predict commercial detectors). But the skill's
*rewriter* is a frontier LLM, and that same capability makes a strong *detector*: ask it to rate how
AI-written the text reads, weighing the known tells (see ``references/ai-tells.md``). This is often
the best signal available for free — in the Claude skill, Claude plays this role directly per
SKILL.md; headless, it uses an Anthropic or OpenAI key.

Key-gated (``commercial`` tier): ``available()`` is true only when a key + SDK is present, so with no
key it is simply absent from the ensemble. ``score`` returns ``None`` for empty/unavailable input and
lets API failures propagate (``score_text`` records them) — matching the other adapters' contract.
"""

from __future__ import annotations

import os
import re

from .base import clamp01

_NUM = re.compile(r"\d*\.\d+|\d+")

_JUDGE_PROMPT = (
    "You are an expert AI-text detector. Rate how likely the text below was written by an AI language "
    "model, from 0.00 (clearly a human wrote it) to 1.00 (clearly AI-generated). Weigh the overall "
    "read, not any single word, and consider the known AI tells: em-dashes; AI vocabulary (delve, "
    "leverage, robust, seamless, tapestry, testament, pivotal, underscore, multifaceted, meticulous); "
    "formulaic transitions (Moreover, Furthermore, Overall, In conclusion); rule-of-three / tricolons; "
    "negated contrast (\"not X, it's Y\"); participial trailers (\"..., underscoring its importance\"); "
    "inflated copula (serves as, boasts); vague attribution (\"studies show\"); uniform sentence length "
    "(low burstiness); promotional register; sycophancy; over-structured markdown. "
    "Ignore opaque sentinel tokens like ⟦HZ0003⟧ — treat them as neutral placeholders. "
    "Respond with ONLY the number, e.g. 0.73"
)


class LLMJudgeDetector:
    name = "llm_judge"
    tier = "commercial"

    def __init__(self, model: str | None = None):
        self.model = model

    def available(self) -> bool:
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic  # noqa: F401

                return True
            except Exception:
                pass
        if os.environ.get("OPENAI_API_KEY"):
            try:
                import openai  # noqa: F401

                return True
            except Exception:
                pass
        return False

    def _complete(self, prompt: str) -> str:
        """Return the model's raw completion (a tiny number). Anthropic preferred, then OpenAI."""
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
            except Exception:
                anthropic = None
            if anthropic is not None:
                resp = anthropic.Anthropic().messages.create(
                    model=self.model or "claude-sonnet-4-6",
                    max_tokens=8,
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(getattr(b, "text", "") for b in resp.content)
        import openai

        resp = openai.OpenAI().chat.completions.create(
            model=self.model or "gpt-4o-mini",
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        out = self._complete(f"{_JUDGE_PROMPT}\n\n--- TEXT ---\n{text}")
        m = _NUM.search(out or "")
        if not m:
            return None
        val = float(m.group(0))
        if val >= 2.0:  # answered as a percentage (e.g. "73"). Values in (1.0, 2.0) are just slightly
            val /= 100.0  # out-of-range probabilities and should clamp to ~1.0, not become 0.01-0.02.
        return clamp01(val)
