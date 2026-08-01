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


def contradicts(a: str, b: str, bar: float = DEFAULT_CONTRADICTION_BAR) -> bool:
    """True only when the model positively asserts a contradiction.

    Unknown (model unavailable) returns False: the veto is a *additional* safety net layered on the
    similarity gate, so its absence must degrade to the previous behaviour rather than reject
    everything.
    """
    score = contradiction_score(a, b)
    return score is not None and score >= bar
