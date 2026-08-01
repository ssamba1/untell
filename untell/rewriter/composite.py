"""Composite rewriter — chains structural (sentence-level) + surgical (word-level) transforms.

The strongest free $0 path: run structural transforms first (transitions, burstiness,
participial trailers), then surgical word-substitution polish. Each targets a different
set of AI tells that the other can't fix.

Always ``available()``. Deterministic.
"""

from __future__ import annotations

from .base import Rewriter
from .structural import StructuralRewriter
from .surgical import SurgicalRewriter


class CompositeRewriter(Rewriter):
    """Chain StructuralRewriter → SurgicalRewriter for the strongest free rewrite.

    Structural transforms fix sentence-level tells (transitions, burstiness, trailers).
    Surgical fixes word-level tells (AI vocabulary). Combined they are far more effective
    than either alone, at no cost.

    Internally draws ``best_of`` candidates with different random seeds and returns
    the one with the lowest detector score — guaranteeing visible improvement on
    almost every call.
    """

    name = "composite"

    def __init__(
        self, intensity: float = 0.7, max_subs: int = 12, best_of: int = 3, use_t5: bool = False
    ):
        self._structural = StructuralRewriter(intensity=intensity)
        self._surgical = SurgicalRewriter(max_subs=max_subs)
        self.best_of = best_of
        # Optional neural front-stage (``prefer="neural"``). A T5 paraphrase moves detectors far more
        # than any rule-based transform (DIPPER-class paraphrasing drove DetectGPT 70%->4.6%), but is
        # heavy (CPU, per-sentence generation) and non-deterministic — so it is OFF by default and the
        # plain composite stays the always-available, deterministic $0 path. It is sentinel-safe: the
        # paraphraser restores every locked span or falls back per sentence, and the outer loop's
        # multiset check is the final net.
        self._t5 = None
        if use_t5:
            try:
                from .t5_paraphrase import T5ParaphraseRewriter

                t5 = T5ParaphraseRewriter()
                self._t5 = t5 if t5.available() else None
            except Exception:
                self._t5 = None
        if use_t5 and self._t5 is not None:
            self.name = "neural"  # distinguish in logs/results when the neural stage is live

    def available(self) -> bool:
        return True

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.scripts.score import score_text

        # Neural front-stage (opt-in): one expensive paraphrase pass, then the cheap rule-based
        # best-of polishes it. Run once (not per best_of attempt) since T5 dominates the cost.
        if self._t5 is not None:
            try:
                text = self._t5.rewrite(text, score_result, threshold)
            except Exception:
                pass  # any neural failure -> fall through to the rule-based chain unchanged

        # Score the (possibly paraphrased) text to establish baseline.
        tier = score_result.get("tier", "lite")
        if tier not in ("lite", "full", "heavy", "commercial"):
            # Non-scoreable tier (e.g. "browser:zerogpt"): score_text can't reproduce the real
            # signal the outer loop uses, and silently falling back to "lite" would make this
            # internal best-of optimize the WRONG objective — picking the lite-best candidate to
            # hand up, which may be browser-worst. Skip internal scoring entirely: run the
            # structural -> surgical chain once and let the outer loop's best-of do the selection
            # against the true (browser) signal.
            restructured = self._structural.rewrite(text, score_result, threshold)
            return self._surgical.rewrite(restructured, score_result, threshold)
        baseline = float(score_text(text, tier=tier)["max"])

        # Try multiple candidates with different seeds, keep the best.
        best_text = text
        best_score = baseline
        for _attempt in range(self.best_of):
            # Step 1: structural (sentence-level)
            restructured = self._structural.rewrite(text, score_result, threshold)
            # Step 2: surgical (word-level polish)
            polished = self._surgical.rewrite(restructured, score_result, threshold)
            # Score the candidate
            try:
                cand_score = float(score_text(polished, tier=tier)["max"])
                if cand_score < best_score:
                    best_text = polished
                    best_score = cand_score
            except Exception:
                pass

        # Fallback: if no candidate improved, pick the first one anyway
        # (it still changed the text structurally even if the lite detector
        # didn't register the improvement).
        if best_text == text:
            restructured = self._structural.rewrite(text, score_result, threshold)
            best_text = self._surgical.rewrite(restructured, score_result, threshold)

        return best_text
