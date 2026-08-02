"""Reward function for RL-against-ensemble training (StealthRL / AuthorMist style).

reward = (1 - P(AI) from the target detector) - meaning-drift penalty - quality penalty

By default the target is our local ensemble (`score_text` max). **But the local ensemble does not
predict commercial detectors** (measured: RADAR 0.008 vs GPTZero 100% on the same humanized text), so
training against it produces a model that beats the local proxies and still fails GPTZero. To target a
real detector, train a surrogate (`training/surrogate.py`) and set ``UNTELL_SURROGATE_DIR`` — the reward
then uses the surrogate's P(AI) instead of the local ensemble, with no other change. That is the
difference between "learns to fool roberta/hc3" and "learns to fool a model that mimics GPTZero".

Pure-python over the chosen detector + semantic similarity, so it is testable on the lite tier with no
GPU (the surrogate path needs `.[train]` + a trained surrogate dir).
"""

import os
import re

from untell.scripts.quality import recommended_bar, similarity
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

_W = re.compile(r"[A-Za-z']+")

_SURROGATE = None  # lazily-loaded SurrogateDetector when UNTELL_SURROGATE_DIR is set

# Free open-detector ensemble weights (NO paid API, NO commercial surrogate). The reward is a
# WEIGHTED mean over whichever detectors the active tier actually produced (renormalized), rather
# than the plain max: a smoother GRPO gradient, and the adversarially-trained detectors (MAGE, RADAR)
# — the ones that don't collapse under naive paraphrase — carry the most weight so the policy has to
# beat the *hard* detectors, not just the weakest link. This is the StealthRL "free ensemble reward"
# regime: it reaches ~97% on open detectors and transfers to held-out ones, with zero API cost.
_FREE_WEIGHTS = {
    "mage": 0.35,
    "radar": 0.20,
    "hc3_roberta": 0.18,
    "fast_detectgpt": 0.15,
    "roberta_openai": 0.10,
    "binoculars": 0.10,
    "perplexity_burstiness": 0.02,
}

# Quality-guard weights (applied on top of the evasion term).
_TELLS_W = 0.015  # per AI-tell-per-100-words; typical AI text 10-30, human 0-3 -> up to ~0.30-0.45
_BURST_W = 0.10  # flat penalty when sentence lengths are uniform (a burstiness tell)


def free_ensemble_score(text: str, tier: str = "full", weights: dict[str, float] | None = None) -> float:
    """Weighted-mean P(AI) over the FREE open detectors the active tier produced (renormalized).

    No commercial API, no surrogate — this is the $0 training target. Detectors absent at the active
    tier (e.g. everything but perplexity_burstiness on lite) simply drop out and the weights of those
    present are renormalized, so the same call works on lite/full/heavy without special-casing.
    """
    weights = weights or _FREE_WEIGHTS
    res = score_text(text, tier=tier)
    dets = res.get("detectors", {})
    present = {
        k: float(v)
        for k, v in dets.items()
        if isinstance(v, (int, float)) and "__" not in k
    }
    if not present:
        # `res["max"]` is a 0.0 PLACEHOLDER when nothing scored, and 0.0 means "not AI at all" —
        # so `humanness_reward` handed back 1.0, the MAXIMUM evasion credit, for text no detector
        # ever looked at. A GRPO/DPO run against a broken ML stack would then optimise a constant
        # perfect reward: every candidate ties, the gradient carries no information, and hours of
        # GPU time produce an adapter trained on nothing, with no error anywhere to show it.
        #
        # This is the same unscored-placeholder-read-as-clean bug fixed in `humanness()` and
        # `report._bypass_rate` this session; it is worst here, because a wrong REWARD is not a
        # misreported number, it is the thing the model learns.
        raise RuntimeError(
            "no detector produced a score, so there is no training signal — refusing to return a "
            f"reward. {res.get('warning') or ''} Failed: {res.get('failed_detectors') or 'unknown'}. "
            "Fix the detector stack, or set UNTELL_REWARD_FAST=1 for the model-free stdlib reward."
        )
    w = {k: weights.get(k, 0.03) for k in present}
    total = sum(w.values()) or 1.0
    return float(sum(w[k] * present[k] for k in present) / total)


def _fast_ai_estimate(text: str) -> float:
    """Zero-model P(AI) estimate from stdlib signals only (AI-tells density + burstiness).

    The transformer detectors (RoBERTa/GPT-2/Fast-DetectGPT) run on CPU here and, called per GRPO
    candidate, stall training on a free T4 (repeated model loads, no step progress). This gives a
    fast, model-free reward signal so GRPO actually runs: dense AI-tells and uniform sentence length
    read as AI. Weaker than the detector reward but real and instant. Gate with UNTELL_REWARD_FAST=1.
    """
    t = score_tells(text)
    tells_est = min(1.0, float(t.get("tells_per_100w", 0.0)) / 15.0)  # ~15 tells/100w -> fully AI
    burst_pen = 0.15 if t.get("low_burstiness") else 0.0
    return float(min(1.0, tells_est + burst_pen))


def target_ai_score(text: str, tier: str = "full") -> float:
    """P(AI) from the training target: the model-free stdlib estimate if ``UNTELL_REWARD_FAST`` is set
    (fast $0 path that runs on a T4), a commercial-mimicking surrogate if ``UNTELL_SURROGATE_DIR`` is
    set (paid), else the FREE weighted open-detector ensemble. The free ensemble reaches the
    open-detector ceiling but is heavy on CPU; the fast path trades some reward fidelity for speed."""
    if os.environ.get("UNTELL_REWARD_FAST") == "1":
        return _fast_ai_estimate(text)
    sd = os.environ.get("UNTELL_SURROGATE_DIR")
    if sd:
        global _SURROGATE
        if _SURROGATE is None:
            from training.surrogate import SurrogateDetector

            _SURROGATE = SurrogateDetector(sd)
        sv = _SURROGATE.score(text)
        if sv is None:
            # Same rule as free_ensemble_score below: no signal is not a reward. The surrogate
            # returns None (per the Detector protocol) when it has nothing to look at, and
            # float(None) would raise a bare TypeError from inside the reward loop.
            raise RuntimeError(
                "the surrogate produced no score for this text (empty or whitespace-only), so "
                "there is no training signal — refusing to return a reward."
            )
        return float(sv)
    return free_ensemble_score(text, tier=tier)


def fluency(text: str) -> float:
    """Cheap quality proxy in [0,1]: distinct-bigram ratio (1.0 = no repetition, low = degenerate).

    Under four words there are too few bigrams to be meaningful, but returning a flat 1.0 there
    made "yes yes yes" indistinguishable from well-formed prose and gave it zero quality penalty —
    exactly the degenerate short completion GRPO is most likely to sample. Distinct *unigram* ratio
    is the same idea at the granularity that is available: 1.0 for "the cat sat", 0.33 for
    "yes yes yes".
    """
    words = [w.lower() for w in _W.findall(text)]
    if not words:
        return 1.0  # nothing to judge; an empty candidate is hard-gated before this is reached
    if len(words) < 4:
        return len(set(words)) / len(words)
    bigrams = list(zip(words, words[1:]))
    return len(set(bigrams)) / len(bigrams)


def humanness_reward(
    original: str,
    candidate: str,
    *,
    tier: str = "full",
    sim_floor: float | None = None,
    w_quality: float = 0.25,
) -> float:
    """Multi-objective reward: evasion + meaning + quality, with HARD meaning/length gates.

    reward = (1 - P(AI) from the target)                    # evade the detectors (weighted ensemble)
             - _TELLS_W * tells_per_100w                     # strip the catalogued AI writing patterns
             - _BURST_W * low_burstiness                     # vary sentence length like a human
             - w_quality * (1 - fluency)                     # don't degenerate into repetition

    HARD gates (return -1.0 outright, no evasion credit):
      * meaning drift below ``sim_floor`` — the policy cannot buy evasion by drifting off-topic
      * output shorter than half the input — nor by deleting content

    The hard gates are the DEPO-style fix for the StealthRL quality-collapse failure mode (2.5/5):
    a soft penalty lets a big evasion reward pay for a small meaning loss every step until the text is
    unrecognizable; a hard gate makes meaning non-negotiable. Targeting evasion + meaning + tells at
    once is the impossibility-triangle win competitors miss (they reward only evasion, so quality rots).
    """
    # None is a real input here: a GRPO generation step that fails or emits an empty token sequence
    # hands the reward fn None, and `None.strip()` raised an AttributeError that propagated out of
    # reward_fn and killed the run with no checkpoint. The docstring's contract for an unusable
    # candidate is -1.0; that now covers None as well.
    if not original or not candidate or not candidate.strip():
        return -1.0
    # The floor MUST match the metric similarity() actually used. It is backend-adaptive — BERTScore
    # (bar 0.88), cosine embeddings (0.76), or the token-overlap fallback (0.50) — and the old
    # hard-coded 0.76 was only meaningful for the middle one. In a lightweight training environment
    # with no sentence-transformers, similarity() falls back to token overlap, where 0.76 is ~50%
    # too strict: a faithful paraphrase that rewords 4 of 11 words scores ~0.64 and was hard-gated to
    # -1.0, the SAME reward as an off-topic rewrite. Every meaningful candidate then earned -1.0, so
    # GRPO trained the policy to make trivially small edits while the loss curve looked plausible.
    if sim_floor is None:
        sim_floor = recommended_bar()
    # Hard gates first — a gated candidate earns nothing regardless of how well it evades.
    if similarity(original, candidate) < sim_floor:
        return -1.0
    if len(candidate) < 0.5 * len(original):
        return -1.0
    ai = target_ai_score(candidate, tier=tier)  # surrogate if UNTELL_SURROGATE_DIR set, else free ensemble
    evade = 1.0 - ai
    tells = score_tells(candidate)
    tells_penalty = _TELLS_W * float(tells.get("tells_per_100w", 0.0))
    burst_penalty = _BURST_W if tells.get("low_burstiness") else 0.0
    quality_penalty = w_quality * (1.0 - fluency(candidate))
    return round(evade - tells_penalty - burst_penalty - quality_penalty, 4)


def batch_rewards(
    original: str, candidates: list[str], *, tier: str = "full", sim_floor: float | None = None
) -> list[float]:
    """Rewards for several candidate rewrites of one source (GRPO scores a group per prompt).

    ``sim_floor`` defaults to None, meaning "ask recommended_bar() for the active similarity
    backend", exactly as humanness_reward does. It used to default to 0.76 — the cosine-embedding
    bar — which silently overrode that adaptation for every batched call: too strict on the
    token-overlap fallback (bar 0.50, so faithful paraphrases were gated to -1.0 alongside
    off-topic ones) and too lenient on BERTScore (bar 0.88). The single-candidate path was fixed
    for this and the batch path, which is the one GRPO actually calls, was not.
    """
    return [humanness_reward(original, c, tier=tier, sim_floor=sim_floor) for c in candidates]
