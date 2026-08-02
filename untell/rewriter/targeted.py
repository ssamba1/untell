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

from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE

from .base import Rewriter

# Split on sentence-final punctuation followed by whitespace, keeping the delimiter with the sentence.
_SENT_SPLIT = re.compile(r"(?<=[.!?])(\s+)")


def split_sentences(text: str) -> list[str]:
    """Split into sentences, preserving the exact whitespace so a join round-trips the input.

    Abbreviation-aware. A naive split on ".\\s" made "Dr. Smith published the results" into the
    fragments "Dr. " and "Smith published the results", and in THIS module that is worse than a
    cosmetic split: each fragment is independently scored and independently rewritten. A one- or
    two-word fragment gets a confident, meaningless detector score (measured: a single word scores
    0.998 on roberta_openai), so "Dr. " clears the min_score gate on nothing, is handed to the inner
    rewriter, and is accepted whenever the mangled version scores lower — which for noise is easy.
    It also spends a full detector pass per fragment.

    Kept as its own splitter rather than reusing untell.text_split.split_sentences because that one
    normalises whitespace, and this module must reassemble the text byte-for-byte.
    """
    from untell.text_split import ends_with_abbreviation

    parts = _SENT_SPLIT.split(text)
    chunks: list[str] = []
    for i in range(0, len(parts), 2):
        sent = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if sent or sep:
            chunks.append(sent + sep)

    out: list[str] = []
    for chunk in chunks:
        if out and ends_with_abbreviation(out[-1]):
            out[-1] += chunk
        else:
            out.append(chunk)
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
            # Single sentence: still validated, as one unit. This path used to return the inner
            # rewriter's output UNCONDITIONALLY, skipping both the sentinel check and the
            # improvement guard that the multi-sentence path applies. MEASURED with a rewriter that
            # drops a locked span:
            #     "The trial enrolled ⟦HZ0000⟧ patients"        -> "...the figure patients"  (lost)
            #     the same rewriter on two sentences            -> correctly rejected
            # A dropped sentinel is silent fact loss: restore() puts nothing back, and the number
            # or citation the lock existed to protect is simply gone from the output.
            return self._accept_or_keep(text, score_result, threshold, tier)

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

    def _accept_or_keep(self, body: str, score_result: dict, threshold: float, tier: str) -> str:
        """Rewrite one unit, returning the candidate only if it is safe AND better.

        The same three conditions the per-sentence loop applies: every locked span survives with its
        original multiplicity, the rewrite actually lowers the score, and any failure anywhere keeps
        the original. Factored out so the single-sentence path cannot drift away from the guarded
        one again — it did, and the drift was invisible because both paths "worked".
        """
        from untell.scripts.score import score_text

        stripped = body.strip()
        if not stripped:
            return body
        try:
            before = float(score_text(stripped, tier=tier)["max"])
        except Exception:
            return body
        if before < self.min_score:
            return body
        try:
            cand = self._inner.rewrite(stripped, score_result, threshold).strip()
        except Exception:
            return body
        if Counter(_SENTINEL_RE.findall(cand)) != Counter(_SENTINEL_RE.findall(stripped)):
            return body
        try:
            after = float(score_text(cand, tier=tier)["max"])
        except Exception:
            return body
        if cand and after < before:
            return cand + body[len(body.rstrip()):]  # preserve original trailing whitespace
        return body
