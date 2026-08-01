"""Ensemble rewriter — run every free method and keep the per-input detector-lowest.

Measured, different free rewriters win on different inputs: the rule-based composite crushes some
paragraphs while a neural T5 paraphrase crushes others (and backfires on the first). No single free
method dominates. So the strongest free path is not *a* method but a **selection over all of them**:
run each member on the text, score every output against the same detector tier the loop uses, and
return the lowest-scoring one. By construction the ensemble is >= its best member on every input — it
can only match or beat any single free rewriter.

Members (all free, all sentinel-safe):
- ``composite``  — structural + surgical (always available, deterministic $0)
- ``neural``     — T5 best-of-N paraphrase + structural + surgical (only if .[full] deps present)
- ``mt_pivot``   — round-trip machine translation (only if .[full] + sentencepiece present)

On a non-scoreable tier (e.g. ``browser:zerogpt``) we cannot select internally, so we run the richest
available member once and let the OUTER loop's best-of pick against the true signal.
"""

from __future__ import annotations

from .base import Rewriter
from .composite import CompositeRewriter


class EnsembleRewriter(Rewriter):
    """Best-of-all-free-methods selector. ``available()`` is always True (composite always is)."""

    name = "ensemble"

    def __init__(self, intensity: float = 0.7, max_subs: int = 12, best_of: int = 3):
        # Ordered so the richest member is LAST — it is the fallback on a non-scoreable tier.
        self._members: list[tuple[str, Rewriter]] = [
            ("composite", CompositeRewriter(intensity=intensity, max_subs=max_subs, best_of=best_of))
        ]
        try:
            from .mt_pivot import MTPivotRewriter

            mt = MTPivotRewriter()
            if mt.available():
                self._members.append(("mt_pivot", mt))
        except Exception:
            pass
        try:
            neural = CompositeRewriter(
                intensity=intensity, max_subs=max_subs, best_of=best_of, use_t5=True
            )
            if neural._t5 is not None:  # T5 deps present
                self._members.append(("neural", neural))
        except Exception:
            pass

    def available(self) -> bool:
        return True

    @property
    def member_names(self) -> list[str]:
        return [n for n, _ in self._members]

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.scripts.score import score_text

        tier = score_result.get("tier", "lite")
        if tier not in ("lite", "full", "heavy", "commercial"):
            # Non-scoreable tier: run the richest member once; outer loop selects against the real signal.
            return self._members[-1][1].rewrite(text, score_result, threshold)

        base = float(score_text(text, tier=tier)["max"])
        best_text, best_score = text, base
        for _name, member in self._members:
            try:
                cand = member.rewrite(text, score_result, threshold)
            except Exception:
                continue
            if not cand.strip() or cand == text:
                continue
            cand_score = float(score_text(cand, tier=tier)["max"])
            if cand_score < best_score:
                best_text, best_score = cand, cand_score
        return best_text
