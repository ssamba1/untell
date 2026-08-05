"""Ensemble rewriter — run every free method and keep the per-input detector-lowest.

Measured, different free rewriters win on different inputs: the rule-based composite crushes some
paragraphs while a neural T5 paraphrase crushes others (and backfires on the first). No single free
method dominates. So the strongest free path is not *a* method but a **selection over all of them**:
run each member on the text, score every output against the same detector tier the loop uses, and
return the lowest-scoring one.

By construction the ensemble is >= its best member **on a single call**: every member sees the same
input, the original text is in the pool too, and the lowest scorer wins, so one `rewrite()` cannot
return something worse than any single member would have on that same draw.

**That guarantee does not survive `--best-of N`, and this docstring used to imply it did.** Under an
outer best-of loop the two paths spend their N draws differently: standalone `neural` spends all N
on independent stochastic T5 samples, while the ensemble spends each draw on an internal contest
that its *deterministic* composite member can win — and when it does, that draw contributes a
convergent composite output instead of a fresh neural one. So N ensemble draws can be markedly less
diverse than N neural draws, and a lucky T5 sample that standalone neural catches in three tries
may never reach the outer selector at all. "The ensemble is >= any single method" is therefore a
per-call statement, not a promise that `--rewriter ensemble --best-of 3` beats
`--rewriter neural --best-of 3`.

Note also that ``max`` is an alias for this class, not a second technique (see
``rewriter/base.py``), so a benchmark listing both is listing one method twice.

Members (all free, all sentinel-safe):
- ``composite``  — structural + surgical (always available, deterministic $0)
- ``neural``     — T5 best-of-N paraphrase + structural + surgical (only if .[full] deps present)
- ``mt_pivot``   — round-trip machine translation (only if .[full] + sentencepiece present)

On a non-scoreable tier (e.g. ``browser:zerogpt``) we cannot select internally, so we run the richest
available member once and let the OUTER loop's best-of pick against the true signal.
"""

from __future__ import annotations

import logging

from .base import Rewriter
from .composite import CompositeRewriter

logger = logging.getLogger(__name__)

# Members that have raised at least once — so the warning fires once, not per rewrite.
_MEMBER_FAILED: set[str] = set()

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
            except Exception as exc:
                # Say it once. This class claims to be ">= its best member on every input"; a
                # member that always raises quietly shrinks the pool that claim is made over, and
                # the ensemble then looks like it is simply not helping.
                if _name not in _MEMBER_FAILED:
                    _MEMBER_FAILED.add(_name)
                    logger.warning(
                        "ensemble member %r failed and is being skipped (%s: %s); the ensemble is "
                        "now selecting over %d of %d members.",
                        _name, type(exc).__name__, str(exc)[:120],
                        len(self._members) - len(_MEMBER_FAILED), len(self._members),
                    )
                continue
            if not cand.strip() or cand == text:
                continue
            scored.append((_rank(score_text(cand, tier=tier)), cand))

        # Among everything within the noise band of the best max (including the ORIGINAL, so a
        # rewrite is only adopted when it genuinely helps), take the lowest mean.
        best_max = min(r[0] for r, _ in scored)
        near = [(r, t) for r, t in scored if r[0] <= best_max + _RANK_EPS]
        # The band is 0.02 wide and nothing kept it off the threshold. A candidate at max 0.295
        # PASSES a 0.30 gate and one at 0.310 does not, yet they are 0.015 apart, so both land in
        # the band and the mean tie-break hands back the FAILING one whenever its mean is lower.
        # MEASURED with exactly those numbers: the failing candidate was selected. Passing is a
        # step change, not a smooth quantity, so it outranks the noise-band heuristic entirely.
        # Fourth site of this shape, after the composite intensity sweep, polish adoption, and the
        # loop's best-of-N tells tie-break.
        passing = [(r, t) for r, t in near if r[0] < threshold]
        near = passing or near
        return min(near, key=lambda rt: (rt[0][1], rt[0][0]))[1]
