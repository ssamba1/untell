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

import logging
import re
from collections import Counter

from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE

from .base import Rewriter, selection_key

logger = logging.getLogger(__name__)

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
        targetable = 0
        for sent in sentences:
            body = sent.strip()
            if not body:
                out.append(sent)
                continue
            try:
                before = selection_key(score_text(body, tier=tier))
            except Exception:
                out.append(sent)
                continue
            # Leave sentences that already read as human completely untouched.
            if before[0] < self.min_score:
                out.append(sent)
                continue
            targetable += 1
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
                after = selection_key(score_text(cand, tier=tier))
            except Exception:
                out.append(sent)
                continue
            # `(max, mean)`, not `max` — the same selector `composite` uses, for the same reason,
            # found here after it was fixed there. MEASURED over 8 HC3 AI answers, per sentence:
            #
            #     max improved (adopted)        4
            #     max worse (rejected)          0
            #     max TIED, mean improved      15   <- every one of these was discarded
            #     max TIED, mean not improved   0
            #
            # `roberta_openai` returns 0.9992 on nearly every sentence of that genre, so `max` is
            # a constant and `after < before` is false on text that genuinely improved: mean
            # 0.6839 -> 0.5821, 0.7663 -> 0.6978, 0.7504 -> 0.6792. Fifteen of nineteen real
            # improvements thrown away, and not one tie that was neutral or worse.
            if cand and after < before:  # adopt only a genuine per-sentence improvement
                trailing = sent[len(sent.rstrip()):]  # preserve the original inter-sentence spacing
                out.append(cand + trailing)
                changed = True
            else:
                out.append(sent)

        if changed:
            return "".join(out)
        if targetable == 0:
            # NOT ONE sentence cleared min_score, so nothing was even attempted — a different
            # outcome from "tried and could not improve", and previously indistinguishable: both
            # returned the input and said nothing.
            #
            # MEASURED on 8 real HC3 AI texts, 64 sentences, comparing the two lite paths:
            #     torch-backed lite            32/64 sentences >= 0.30   -> targets normally
            #     pure stdlib (NO_TORCH=1)      0/64 sentences >= 0.30   -> targets NOTHING
            # and through the loop on 15 real texts, stdlib: 0/15 texts changed, 0.00 adopted,
            # score and tells both bit-identical to the input.
            #
            # The cause is a scale mismatch, not a bug in any one sentence. `min_score` is an
            # ABSOLUTE 0.30 applied per sentence, but detector scores on a single sentence run
            # systematically below scores on the paragraph containing it (mean 0.326 per sentence
            # against 0.619 per document on the same texts). On the stdlib heuristic the gap is
            # wide enough that a document at 0.57 contains no sentence above 0.30 at all.
            #
            # Falling back to a whole-text rewrite is the same answer this method already gives
            # for a non-scoreable tier a few lines above: when per-sentence targeting cannot be
            # done, defer to the inner rewriter and let the OUTER loop select against the real
            # signal. Silently returning the input is strictly worse than that — `--rewriter
            # targeted` degrades to `composite` instead of to nothing.
            logger.warning(
                "targeted: no sentence scored at or above min_score=%.2f, so per-sentence "
                "targeting had nothing to work on — falling back to a whole-text rewrite. This is "
                "expected on the pure-stdlib detector path, where single sentences score far below "
                "the paragraphs containing them; install .[full] for per-sentence scores that "
                "separate.",
                self.min_score,
            )
            return self._inner.rewrite(text, score_result, threshold)
        # Sentences WERE targeted and none improved. Keep the input: that is the no-harm guarantee,
        # and re-running the same inner rewriter over the whole text would spend meaning on
        # sentences already judged not worth touching.
        return text

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
            before = selection_key(score_text(stripped, tier=tier))
        except Exception:
            return body
        if before[0] < self.min_score:
            return body
        try:
            cand = self._inner.rewrite(stripped, score_result, threshold).strip()
        except Exception:
            return body
        if Counter(_SENTINEL_RE.findall(cand)) != Counter(_SENTINEL_RE.findall(stripped)):
            return body
        try:
            after = selection_key(score_text(cand, tier=tier))
        except Exception:
            return body
        if cand and after < before:
            return cand + body[len(body.rstrip()):]  # preserve original trailing whitespace
        return body
