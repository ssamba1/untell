"""Sentence-targeted rewriter — rewrite only the sentences that actually read as AI.

Every free rewriter rewrites the WHOLE text, including sentences that already read as human. That
is wasteful and measurably harmful: rewriting a clean sentence spends meaning-similarity and can
push its score UP (a clean paragraph was measured going from roberta 0.017 to 0.127 under a forced
whole-text rewrite). The loop already computes ``flagged_sentences`` every iteration — but only the
hosted-LLM rewriter ever consumed it; the free path ignored it entirely.

This wraps any inner rewriter and applies it **per flagged sentence**, keeping unflagged sentences
byte-identical. Each rewritten sentence is accepted only if it improves that sentence's own score,
so the no-harm guarantee holds at sentence granularity rather than only for the whole text.

Sentinel-safe: sentences containing locked spans are rewritten by the inner rewriter, which carries
its own sentinel protection, and the result is verified — any sentence that loses or duplicates a
locked span falls back to the original.
"""

from __future__ import annotations

import re
from collections import Counter

from .base import Rewriter

_SENTINEL_RE = re.compile(r"⟦HZ\d{4,}⟧")
# Split on sentence-final punctuation followed by whitespace, keeping the delimiter with the sentence.
_SENT_SPLIT = re.compile(r"(?<=[.!?])(\s+)")


def split_sentences(text: str) -> list[str]:
    """Split into sentences, preserving the exact whitespace so a join round-trips the input."""
    parts = _SENT_SPLIT.split(text)
    out: list[str] = []
    for i in range(0, len(parts), 2):
        sent = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if sent or sep:
            out.append(sent + sep)
    return out


class TargetedRewriter(Rewriter):
    """Apply an inner rewriter only to the sentences a detector flags."""

    name = "targeted"

    def __init__(self, inner: Rewriter | None = None, min_score: float = 0.30):
        if inner is None:
            from .composite import CompositeRewriter

            inner = CompositeRewriter()
        self._inner = inner
        self.min_score = min_score

    def available(self) -> bool:
        return self._inner.available()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.scripts.score import score_text

        tier = score_result.get("tier", "lite")
        if tier not in ("lite", "full", "heavy", "commercial"):
            # Non-scoreable tier: cannot score per sentence, so defer to the inner rewriter wholesale
            # and let the outer loop select against the real signal.
            return self._inner.rewrite(text, score_result, threshold)

        sentences = split_sentences(text)
        if len(sentences) < 2:
            return self._inner.rewrite(text, score_result, threshold)

        out: list[str] = []
        changed = False
        for sent in sentences:
            body = sent.strip()
            if not body:
                out.append(sent)
                continue
            try:
                before = float(score_text(body, tier=tier)["max"])
            except Exception:
                out.append(sent)
                continue
            # Leave sentences that already read as human completely untouched.
            if before < self.min_score:
                out.append(sent)
                continue
            try:
                cand = self._inner.rewrite(body, score_result, threshold).strip()
            except Exception:
                out.append(sent)
                continue
            # Locked spans must survive this sentence exactly (no drop, no duplicate).
            if Counter(_SENTINEL_RE.findall(cand)) != Counter(_SENTINEL_RE.findall(body)):
                out.append(sent)
                continue
            try:
                after = float(score_text(cand, tier=tier)["max"])
            except Exception:
                out.append(sent)
                continue
            if cand and after < before:  # adopt only a genuine per-sentence improvement
                trailing = sent[len(sent.rstrip()):]  # preserve the original inter-sentence spacing
                out.append(cand + trailing)
                changed = True
            else:
                out.append(sent)

        return "".join(out) if changed else text
