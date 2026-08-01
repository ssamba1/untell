"""Contradiction veto — catch rewrites that invert the meaning the similarity gate calls "preserved".

The loop's meaning gate is cosine similarity over sentence embeddings. MEASURED, that metric is
blind to negation and antonymy, because an inverted sentence is lexically and topically almost
identical to its source:

    "The build runs significantly faster."  ->  "The build runs significantly slower."
        embedding similarity 0.974  (bar is 0.76 — passes comfortably)

Four of five meaning-inverting rewrites cleared the 0.76 bar in that probe, one at 0.974. So the
gate that exists to guarantee "meaning preserved" will happily pass a rewrite asserting the
opposite of the source — a correctness failure that matters far more than a detector score.

Natural-language inference answers the question the embedding cannot: does the rewrite *contradict*
the source? A cross-encoder NLI model scores (premise, hypothesis) as entailment / neutral /
contradiction. We check BOTH directions and take the maximum contradiction probability, because
contradiction is not symmetric in the model's output and either direction is disqualifying.

Optional: needs ``.[full]`` (torch + transformers). Everything degrades to "unknown" (``None``)
when the deps or the model are unavailable, so the zero-dependency path is never blocked — a
missing veto must never turn into a *silent* veto that rejects every candidate.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Small, fast, and purpose-built for this: a 3-way NLI cross-encoder (~330MB).
_MODEL_ID = "cross-encoder/nli-distilroberta-base"

# A candidate is vetoed at or above this contradiction probability. Measured, genuine inversions
# score >= 0.996 while faithful register-shifting paraphrases sit near zero, so the boundary is not
# delicate — 0.5 sits in a wide empty gap between the two populations.
DEFAULT_CONTRADICTION_BAR = 0.5


class _NLI:
    """Lazily-loaded module-level model cache."""

    tok = None
    model = None
    label_idx: dict[str, int] | None = None
    dead = False
    warned = False


def available() -> bool:
    """True when the NLI stack can be imported. Does not load the model."""
    if _NLI.dead:
        return False
    import os

    if os.environ.get("UNTELL_DISABLE_NLI") == "1":
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


def _load():
    if _NLI.model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID).eval()
        # Resolve label positions from the config rather than assuming an index order — the
        # convention differs between NLI checkpoints and guessing it silently inverts the veto.
        _NLI.label_idx = {str(v).lower(): int(k) for k, v in model.config.id2label.items()}
        _NLI.tok, _NLI.model = tok, model
    return _NLI.tok, _NLI.model


def _pair_probs(premise: str, hypothesis: str):
    import torch

    tok, model = _load()
    enc = tok(premise, hypothesis, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        return torch.softmax(model(**enc).logits, dim=-1)[0]


def contradiction_score(a: str, b: str) -> float | None:
    """Max contradiction probability across both directions, or None if unavailable.

    None means "unknown", never "fine" — callers must not treat it as a pass or a fail on its own.
    """
    if not available() or not a.strip() or not b.strip():
        return None
    try:
        idx = None
        forward = _pair_probs(a, b)
        idx = (_NLI.label_idx or {}).get("contradiction")
        if idx is None:
            return None
        backward = _pair_probs(b, a)
        return max(float(forward[idx]), float(backward[idx]))
    except Exception as exc:
        # One failure disables the veto for the process rather than raising per candidate — but say
        # so once, because a silently absent safety check is worse than a noisy one.
        _NLI.dead = True
        if not _NLI.warned:
            logger.warning(
                "contradiction veto unavailable (%s: %s); meaning inversions will NOT be caught.",
                type(exc).__name__, str(exc)[:140],
            )
            _NLI.warned = True
        return None


def entailment_score(a: str, b: str) -> float | None:
    """Bidirectional entailment: min(P(a entails b), P(b entails a)). None if unavailable.

    The contradiction veto catches meaning INVERSION but is blind to meaning *loss*: dropping half a
    sentence contradicts nothing. Measured, "The cat sat on the mat and watched the rain fall
    outside." -> "The cat sat somewhere." scores contradiction 0.060 (innocent) yet bidirectional
    entailment 0.002 — because the truncation does not entail the source.

    Taking the MIN of both directions is what makes this a meaning-preservation test rather than a
    one-way implication test: b must say everything a says, and a must say everything b says.
    Measured, faithful register-shifting paraphrases land at 0.016-0.921 while meaning-lost or
    inverted rewrites sit at 0.000-0.002.
    """
    if not available() or not a.strip() or not b.strip():
        return None
    try:
        forward = _pair_probs(a, b)
        idx = (_NLI.label_idx or {}).get("entailment")  # resolved during the first load
        if idx is None:
            return None
        backward = _pair_probs(b, a)
        return min(float(forward[idx]), float(backward[idx]))
    except Exception as exc:
        _NLI.dead = True
        if not _NLI.warned:
            logger.warning(
                "entailment check unavailable (%s: %s); meaning loss will NOT be caught.",
                type(exc).__name__, str(exc)[:140],
            )
            _NLI.warned = True
        return None


def contradicts(a: str, b: str, bar: float = DEFAULT_CONTRADICTION_BAR) -> bool:
    """True only when the model positively asserts a contradiction.

    Unknown (model unavailable) returns False: the veto is a *additional* safety net layered on the
    similarity gate, so its absence must degrade to the previous behaviour rather than reject
    everything.
    """
    score = contradiction_score(a, b)
    return score is not None and score >= bar


# Entailment floor for the relaxed gate. Measured, meaning-lost/inverted rewrites sit at
# 0.000-0.002 and faithful register shifts at 0.016-0.921, so 0.005 sits in an 8x-wide empty gap.
DEFAULT_ENTAILMENT_FLOOR = 0.005
# Similarity floor used only when NLI is carrying the meaning check. It exists to catch gross topic
# drift that NLI might rate as merely "neutral", not to judge fidelity — NLI does that far better.
RELAXED_SIM_BAR = 0.30


def meaning_preserved(
    source: str,
    candidate: str,
    sim: float,
    strict_sim_bar: float,
    relaxed_sim_bar: float = RELAXED_SIM_BAR,
    contradiction_bar: float = DEFAULT_CONTRADICTION_BAR,
    entailment_floor: float = DEFAULT_ENTAILMENT_FLOOR,
) -> bool:
    """Decide whether ``candidate`` preserves ``source``'s meaning, adaptively.

    Cosine similarity alone is a poor meaning test in BOTH directions. Measured on a fixed probe
    set, the shipped ``sim >= 0.76`` rule admitted only 2 of 8 faithful formal->casual rewrites (it
    penalises register change, which is exactly what humanizing does) while admitting 4 of 11
    meaning-lost or inverted ones (it is blind to negation).

    With NLI available, similarity stops being the fidelity judge and becomes only a gross-topic-drift
    floor, while contradiction and bidirectional entailment do the real work:

        sim >= relaxed_sim_bar  AND  contradiction < bar  AND  bidirectional entailment >= floor

    That combination admitted 7 of 8 faithful rewrites and 0 of 11 bad ones on the same probe set —
    simultaneously more permissive to genuine paraphrase and strictly safer.

    Without NLI, there is nothing to lean on, so this falls back to the original strict similarity
    bar. Loosening the bar in that case would be pure risk: the metric that would have to catch the
    bad rewrites is the very one measured to be blind to them.
    """
    if not available():
        return sim >= strict_sim_bar

    con = contradiction_score(source, candidate)
    ent = entailment_score(source, candidate)
    if con is None or ent is None:  # model died mid-run -> strict behaviour, never a silent pass
        return sim >= strict_sim_bar

    return sim >= relaxed_sim_bar and con < contradiction_bar and ent >= entailment_floor
