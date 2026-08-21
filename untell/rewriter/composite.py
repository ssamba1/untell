"""Composite rewriter — chains structural (sentence-level) + surgical (word-level) transforms.

The strongest free $0 path: run structural transforms first (transitions, burstiness,
participial trailers), then surgical word-substitution polish. Each targets a different
set of AI tells that the other can't fix.

Always ``available()``. Deterministic.
"""

from __future__ import annotations

from .base import Rewriter, selection_key
from .structural import StructuralRewriter
from .surgical import SurgicalRewriter

# Re-exported under its original private name: this selector moved to `base` when `targeted` was
# found to have the same defect it was written for, and one selector must have one definition.
_selection_key = selection_key

_INTENSITY_SPAN = 0.3


def _intensity_sweep(base: float, n: int) -> list[float]:
    """``n`` structural intensities spread around ``base``, always including ``base`` itself.

    Diversity is what makes best-of selection worth anything — drafts differing only by RNG seed
    score near-identically and waste the draw — so the attempts fan out around the configured
    intensity. But the fan-out must not *replace* it: a plain linear sweep put the draws at the two
    endpoints when ``n == 2`` (0.4 and 1.0 for the default 0.7), so a caller who lowered intensity
    to limit surface change never got a single candidate at the value they asked for. The slot
    nearest ``base`` is pinned to it.
    """
    if n <= 1:
        return [base]
    span = _INTENSITY_SPAN
    out = [
        max(0.4, min(1.0, base - span + 2 * span * k / (n - 1)))
        for k in range(n)
    ]
    # Often base survives the sweep on its own (it is the midpoint whenever n is odd, and clamping
    # can land on it too). Only when it does not is the nearest draw pulled onto it, so this
    # changes nothing about the existing spread except in the case that dropped it.
    if not any(abs(v - base) < 1e-9 for v in out):
        out[min(range(n), key=lambda k: abs(out[k] - base))] = base
    # Clamping can leave TWO draws at the same intensity (e.g. 1.0 -> [0.7, 1.0, 1.0], or
    # 0.4 -> [0.4, 0.4, 0.7]). The docstring above says the whole point of the spread is that
    # drafts differing only by RNG seed score near-identically and waste the draw, so a duplicate
    # intensity is a draw thrown away before it is rolled. MEASURED before this: 161 of 366
    # in-contract (base, n) pairs emitted a duplicate (44%); at the clamping edges it was the
    # base itself that doubled. Resolve runs of equal values by spacing the run evenly between
    # its distinct neighbours, never moving the slot pinned to base.
    base_slot = min(range(n), key=lambda k: abs(out[k] - base))
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(out[j + 1] - out[i]) < 1e-9:
            j += 1
        run_len = j - i + 1
        if run_len > 1:
            lo = max(out[i - 1] if i > 0 else 0.4, 0.4)
            hi = min(out[j + 1] if j + 1 < n else 1.0, 1.0)
            # Base's slot stays exactly at base; the other run members are spaced evenly between
            # the run's neighbours (or a tiny step off the floor/ceiling when the run touches an
            # edge — 0.9999 vs 1.0 is still more diverse than 1.0 vs 1.0, and the seeded RNG does
            # the real separation).
            if lo >= hi - 1e-6:
                # Run touches an edge (all values at the floor or ceiling). Space the members
                # descending from the edge — at the ceiling, 1.0, 0.9996, 0.9992, ... — so every
                # draw is distinct. 0.9996 vs 1.0 is still more diverse than 1.0 vs 1.0, and the
                # seeded RNG does the real separation.
                step = min((hi - lo) / (run_len + 1), 1e-3) if hi > lo else 1e-3
                for k in range(run_len):
                    if i + k == base_slot:
                        out[i + k] = base
                    else:
                        out[i + k] = max(lo, min(hi, hi - (k + 1) * step))
            elif base_slot in range(i, j + 1):
                # Spread left-of-base members between lo and base, right-of-base between base and hi.
                for k in range(run_len):
                    pos = i + k
                    if pos == base_slot:
                        out[pos] = base
                    elif pos < base_slot:
                        left_count = base_slot - i
                        out[pos] = lo + (base - lo) * (k + 1) / (left_count + 1)
                    else:
                        right_count = j - base_slot
                        # If base sits AT the ceiling the span base..hi is zero width, so right
                        # members descend from base toward lo instead of staying pinned at 1.0.
                        if hi <= base + 1e-6:
                            off = right_count + 1 - (k - base_slot + i)
                            out[pos] = lo + (base - lo) * off / (right_count + 1)
                        else:
                            out[pos] = base + (hi - base) * (k - base_slot + i) / (right_count + 1)
            else:
                for k in range(run_len):
                    out[i + k] = lo + (hi - lo) * (k + 1) / (run_len + 1)
        i = j + 1
    return out


class CompositeRewriter(Rewriter):
    """Chain StructuralRewriter → SurgicalRewriter for the strongest free rewrite.

    Structural transforms fix sentence-level tells (transitions, burstiness, trailers).
    Surgical fixes word-level tells (AI vocabulary).

    Internally draws ``best_of`` candidates with different random seeds and returns
    the one with the lowest detector score — guaranteeing visible improvement on
    almost every call.

    WHERE THE GAIN ACTUALLY COMES FROM. This used to say the two "combined are far more effective
    than either alone, at no cost". Half of that is right and the attribution is not. Mean detector
    max over 10 seeds, one rewrite call each:

        text              before   surgical   structural   composite
        ai vocab heavy    0.664     0.607       0.332        0.294
        delve tapestry    0.511     0.485       0.358        0.284
        hedged report     0.533     0.482       0.284        0.123
        plain academic    0.565     0.565       0.202        0.195

    Composite beats surgical by a mile, so "more effective than either alone" holds against that
    member. Against STRUCTURAL the margin is real too — but it is not the surgical stage producing
    it. Replacing that stage with an identity function inside this class, same seeds, same draws:

        ai vocab heavy    with 0.2939   without 0.2939   byte-identical 10/10
        hedged report     with 0.1227   without 0.1227   byte-identical 10/10
        delve tapestry    with 0.2840   without 0.2840   byte-identical 10/10

    Identical output, to four decimal places, with the second stage removed. The margin over a
    single structural call is the best-of-N SELECTION described above, not the chaining. Surgical
    acts on AI vocabulary that structural has already removed, so there is nothing left for it to
    substitute — measured at 0 changes out of 60 draws across five texts, and 0 of 12 on two more.
    That is the same thing the polish knob ran into a layer up (see
    `tests/test_every_knob_has_an_effect.py`): not a gate rejecting a candidate, nothing left to
    swap.

    The stage is kept, because it is the cheap half and it is the one that fires when structural
    declines — on text the structural transforms do not match, surgical is what changes anything at
    all. What is corrected here is only the claim about where the improvement comes from.
    """

    name = "composite"

    def __init__(
        self,
        intensity: float = 0.7,
        max_subs: int = 12,
        best_of: int = 3,
        use_t5: bool = False,
        t5_best_of: int = 4,
    ):
        self._structural = StructuralRewriter(intensity=intensity)
        self._surgical = SurgicalRewriter(max_subs=max_subs)
        self.best_of = best_of
        self.t5_best_of = t5_best_of
        # Optional neural front-stage (``prefer="neural"``). A neural paraphrase moves detectors far
        # more than any rule-based transform (DIPPER-class paraphrasing drove DetectGPT 70%->4.6%),
        # but T5-base is heavy (CPU, per-sentence generation) and HIGH-VARIANCE — one draw can crush a
        # detector (0.97->0.07) while another backfires (0.02->0.99). So it is OFF by default (the
        # plain composite stays the always-available, rule-based $0 path — rule-based, not
        # deterministic: it draws `best_of` candidates under different seeds, see the class
        # docstring), and when ON it is used
        # as a best-of-N SAMPLER: draw ``t5_best_of`` diverse paraphrases and keep the lowest-scoring
        # one that also beats the original — turning the variance into an advantage. Sentinel-safe:
        # the paraphraser restores every locked span or falls back per sentence.
        #
        # WHAT THE NEURAL STAGE BUYS, on the one axis the rule-based path cannot reach. Repeated
        # phrasing is the largest untreated tell in the catalogue: the structural rewriter closes
        # 7-17% of the gap to human text and leaves output repeating about 6x more (see the note in
        # structural.py). Measured as the share of tokens inside a repeated 3-gram, on RAID:
        #
        #     structural       10.27 -> 8.92    13% less repetition   (20 docs)
        #     t5_paraphrase     9.12 -> 4.50    51%                   ( 8 docs)
        #     t5_paraphrase     9.88 -> 6.93    30%                   (10 docs, different slice)
        #
        # Two to four times the reduction, because the half structural cannot touch is clause
        # restatement and a paraphraser rewrites clauses. That is the concrete reason to reach for
        # `--rewriter neural` on repetitive input.
        #
        # The two t5 figures are also the argument for the sampler, and for never quoting one run:
        # 51% and 30% on different slices of the same corpus, and per document the reduction ranges
        # from -87% to +71%. It makes some documents materially worse. Best-of-N with a
        # score-beats-original guard is what converts that spread into a floor.
        self._t5 = None
        if use_t5:
            try:
                from .t5_paraphrase import T5ParaphraseRewriter

                t5 = T5ParaphraseRewriter(sample=True)  # diverse draws for best-of-N selection
                self._t5 = t5 if t5.available() else None
            except Exception:
                self._t5 = None
        if use_t5 and self._t5 is not None:
            self.name = "neural"  # distinguish in logs/results when the neural stage is live

    def available(self) -> bool:
        return True

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.scripts.score import score_text

        tier = score_result.get("tier", "lite")
        _scoreable = tier in ("lite", "full", "heavy", "commercial")

        # Neural front-stage (opt-in): BEST-OF-N sampling. T5-base paraphrase quality is high-variance
        # — measured, one draw crushes a detector (roberta 0.973->0.066) while another backfires
        # (0.017->0.999) because its own paraphrase style can read MORE AI. So draw several diverse
        # sampled paraphrases and keep the LOWEST-scoring one that also beats the original; if none
        # beats it, keep the original and let the rule-based chain work on it. On a non-scoreable tier
        # we can't select here, so take a single draw and rely on the OUTER loop's best-of (run.py only
        # adopts a candidate that beats the running best) as the safety net.
        if self._t5 is not None:
            try:
                if not _scoreable:
                    para = self._t5.rewrite(text, score_result, threshold)
                    if para.strip() and para != text:
                        text = para
                else:
                    # Same (max, mean) key as the rule-based selector below: a saturating detector
                    # pins `max` here too, and "no draw beat the original" would then discard every
                    # paraphrase for the same non-reason. See `_selection_key`.
                    base = _selection_key(score_text(text, tier=tier))
                    best_para, best_para_score = None, base
                    for _ in range(max(1, self.t5_best_of)):
                        para = self._t5.rewrite(text, score_result, threshold)
                        if not para.strip() or para == text:
                            continue
                        ps = _selection_key(score_text(para, tier=tier))
                        if ps < best_para_score:
                            best_para, best_para_score = para, ps
                    if best_para is not None:
                        text = best_para  # a sampled paraphrase beat the original signal
            except Exception:
                pass  # any neural failure -> fall through to the rule-based chain unchanged

        # Score the (possibly paraphrased) text to establish baseline.
        if not _scoreable:
            # Non-scoreable tier (e.g. "browser:zerogpt"): score_text can't reproduce the real
            # signal the outer loop uses, and silently falling back to "lite" would make this
            # internal best-of optimize the WRONG objective — picking the lite-best candidate to
            # hand up, which may be browser-worst. Skip internal scoring entirely: run the
            # structural -> surgical chain once and let the outer loop's best-of do the selection
            # against the true (browser) signal.
            restructured = self._structural.rewrite(text, score_result, threshold)
            return self._surgical.rewrite(restructured, score_result, threshold)
        try:
            baseline = _selection_key(score_text(text, tier=tier))
        except Exception:
            # A candidate scoring failure below is swallowed; this one used to propagate and abort
            # the whole rewrite. Same transient cause (detector timeout, OOM spike), opposite
            # outcome. With no baseline there is nothing to select against, so take the same route
            # as a non-scoreable tier: run the chain once and let the outer loop choose.
            restructured = self._structural.rewrite(text, score_result, threshold)
            return self._surgical.rewrite(restructured, score_result, threshold)

        # Try multiple candidates and keep the best. Selection is only as good as the DIVERSITY of
        # what it selects among: drafts that differ merely by RNG seed score near-identically and
        # waste the draw. So each attempt also varies the structural intensity across a spread around
        # the configured value — a light-touch draft and an aggressive one explore genuinely different
        # rewrites, which is what gives the selector something to choose between.
        best_text = text
        best_score = baseline
        base_intensity = getattr(self._structural, "intensity", 0.7)
        intensities = _intensity_sweep(base_intensity, self.best_of)
        for _attempt in range(self.best_of):
            # Passed per call, NOT assigned to self._structural. Assigning and restoring left the
            # shared rewriter holding a swept value whenever anything in between raised, and
            # corrupted it permanently under concurrent use: a second caller reads the swept value
            # as its own baseline and "restores" that. Measured with 8 threads, the configured 0.7
            # came back as 0.4 and stayed there.
            restructured = self._structural.rewrite(
                text, score_result, threshold, intensity=intensities[_attempt]
            )
            # Step 2: surgical (word-level polish)
            polished = self._surgical.rewrite(restructured, score_result, threshold)
            # No-op draw: polished == text means this candidate is byte-identical to the
            # original.  Scoring it cannot improve best_text: cand_score would equal
            # baseline (same bytes → same score), and best_score starts at baseline and
            # only decreases when a genuine improvement is adopted, so cand_score <
            # best_score is impossible.  Skip the score_text() call entirely.
            if polished == text:
                continue
            # Score the candidate
            try:
                cand_score = _selection_key(score_text(polished, tier=tier))
                if cand_score < best_score:
                    best_text = polished
                    best_score = cand_score
            except Exception:
                pass
        # No restore needed any more: nothing was mutated.

        # No "consolation" rewrite. This used to force a rewrite when no candidate improved the
        # score, on the theory that changing the text was worth something anyway. MEASURED, it is
        # actively harmful: on an already-clean paragraph (roberta 0.017) the forced rewrite pushed
        # the score UP to 0.127 while spending meaning-similarity for nothing. If none of the draws
        # beat the original, the original IS the best candidate — return it unchanged and let the
        # outer loop decide what to do next (it stops on a no-op, which is the correct outcome).
        return best_text
