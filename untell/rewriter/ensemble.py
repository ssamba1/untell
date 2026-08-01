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

# Detector-max noise band: candidates whose max is within this of the best are ranked by the
# whole-ensemble mean instead, so a near-tie on the peak detector is resolved toward the candidate
# that improved the others too.
_RANK_EPS = 0.02


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

        # Rank on (max, mean), not max alone. MEASURED: `max` aggregation is dominated by whichever
        # detector is highest — typically the content/genre one that a meaning-preserving rewrite
        # cannot move. Selecting on it alone let a member that nudged `max` by a hair while WRECKING
        # a lower detector win: on one sample the max-only ensemble returned a candidate scoring
        # roberta 0.933 where a member had reached 0.002. Ranking by the whole-ensemble mean once the
        # max ties (within the noise band) picks the candidate that is better everywhere, not just at
        # its peak — the same fix applied to the loop's best-of-N selection.
        def _rank(s: dict) -> tuple[float, float]:
            return (float(s["max"]), float(s.get("mean", s["max"])))

        base = score_text(text, tier=tier)
        scored: list[tuple[tuple[float, float], str]] = [(_rank(base), text)]
        for _name, member in self._members:
            try:
                cand = member.rewrite(text, score_result, threshold)
            except Exception:
                continue
            if not cand.strip() or cand == text:
                continue
            scored.append((_rank(score_text(cand, tier=tier)), cand))

        # Among everything within the noise band of the best max (including the ORIGINAL, so a
        # rewrite is only adopted when it genuinely helps), take the lowest mean.
        best_max = min(r[0] for r, _ in scored)
        near = [(r, t) for r, t in scored if r[0] <= best_max + _RANK_EPS]
        return min(near, key=lambda rt: (rt[0][1], rt[0][0]))[1]
