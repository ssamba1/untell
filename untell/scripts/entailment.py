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

import difflib
import logging
from functools import lru_cache

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


@lru_cache(maxsize=16)
def _pair_probs(premise: str, hypothesis: str):
    """Softmax over (entailment, neutral, contradiction) for one ordered pair.

    Cached because the caller asks for the same pair twice. `meaning_preserved` calls
    `contradiction_score` and then `entailment_score`, and each of those runs BOTH directions — so
    four forward passes covering only two distinct pairs. The softmax already contains every label,
    so the second pass of each pair recomputes a result it is about to discard.

    MEASURED: this was the loop's dominant cost. In a warm 3-iteration best-of-3 profile,
    `meaning_preserved` accounted for 4.5s of the run at ~1.5s per call, essentially all of it in
    RoBERTa forward passes.

    16 entries is enough for the loop's access pattern (the same pair back-to-back, then the next
    candidate) without pinning many long strings. Safe to cache: the model loads once and is
    deterministic under `no_grad`, so the same pair always yields the same probabilities.
    """
    import torch

    tok, model = _load()
    enc = tok(premise, hypothesis, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        return torch.softmax(model(**enc).logits, dim=-1)[0]


# --- long inputs -------------------------------------------------------------------------------
# `_pair_probs` tokenises (premise, hypothesis) as ONE sequence truncated at 256 tokens, so each
# side gets roughly 128. Everything past that is not scored — it is not scored *badly*, it is
# absent from the model's input entirely.
#
# MEASURED, same edit, same document, only its position changed:
#
#     "The treatment improved outcomes." -> "The treatment did NOT improve outcomes."
#
#     length   edit at the START   edit at the END
#       7 w    contra 0.9976       contra 0.9971    both vetoed
#      75 w    contra 0.9769       contra 0.9748    both vetoed
#     143 w    contra 0.9833       contra 0.0179    END NOT VETOED
#     279 w    contra 0.9833       contra 0.0179    END NOT VETOED
#
# 0.0179 is the score for two identical strings: past the cut the model is comparing the same
# truncated prefix against itself. A rewriter could invert any claim after roughly the first 130
# words of a document and no gate in this project would see it. The same class of bug was found
# and fixed for the DETECTORS (windowed scoring); the meaning gate never got the fix.
#
# Chunked and aligned rather than a sliding window, because this is a PAIRED comparison: piece i
# of the original has to be scored against the piece of the rewrite that corresponds to it. How
# that alignment is done matters more than it sounds — see `_aligned_chunks`.
#
# Applied to CONTRADICTION only. `entailment_score` stays whole-text, with the measurement for why
# recorded there.
#
# Cost, over 30 real rewrites of median 298 words: 0.17s -> 0.57s per pair, so the gate is roughly
# 3.4x dearer on long input and unchanged on short (one chunk reproduces the old call exactly).
# Veto rate on those same 30 went 1 -> 2, and the one added veto was inspected and is a TRUE
# catch: "applied to various tasks" -> "applied to all sorts of tasks", an overclaim the whole-text
# score diluted to 0.29 and the aligned chunk scores at 0.61.
_CHUNK_WORDS = 90


def _aligned_chunks(a: str, b: str) -> list[tuple[str, str]]:
    """Pair up ``a`` and ``b`` piecewise so neither side reaches the tokeniser's cut.

    Cut points come from ``difflib``, not from proportion. Cutting each side into k equal pieces
    was tried first and drifts: the rewriter merges and splits sentences, so by the third chunk the
    two sides are a sentence apart and the gate compares text that was never meant to correspond.
    Measured, that produced false vetoes on faithful rewrites —

        SRC chunk: "Our results demonstrate that the attention mechanism improves ..."
        OUT chunk: "We also perform a series of ablation studies ... Our results show that ..."

    A rewrite keeps most of its words, so the longest matching word blocks between the two are a
    direct anchor. Each source cut point is mapped through those blocks to the corresponding place
    in the rewrite, and both sides are then cut at genuinely corresponding positions.
    """
    aw, bw = a.split(), b.split()
    longest = max(len(aw), len(bw))
    k = max(1, -(-longest // _CHUNK_WORDS))
    if k == 1 or len(aw) < 2 or len(bw) < 2:
        return [(a, b)]

    matcher = difflib.SequenceMatcher(a=aw, b=bw, autojunk=False)
    blocks = matcher.get_matching_blocks()  # ends with a zero-length sentinel

    def map_index(i: int) -> int:
        """Where in ``b`` does word ``i`` of ``a`` correspond to?"""
        for blk in blocks:
            if blk.a <= i < blk.a + blk.size:
                return blk.b + (i - blk.a)
            if blk.a > i:  # fell in a gap — anchor to the start of the next matching block
                return blk.b
        return len(bw)

    cuts_a = [round(len(aw) * n / k) for n in range(1, k)]
    bounds_a = [0, *cuts_a, len(aw)]
    bounds_b = [0, *[map_index(c) for c in cuts_a], len(bw)]
    # Monotonicity is not guaranteed if a block anchor jumps backwards; enforce it rather than
    # emitting a reversed slice, which would silently produce an empty chunk.
    for n in range(1, len(bounds_b)):
        bounds_b[n] = max(bounds_b[n], bounds_b[n - 1])

    out: list[tuple[str, str]] = []
    for n in range(k):
        ca = " ".join(aw[bounds_a[n] : bounds_a[n + 1]])
        cb = " ".join(bw[bounds_b[n] : bounds_b[n + 1]])
        if ca.strip() and cb.strip():
            out.append((ca, cb))
    return out or [(a, b)]


def contradiction_score(a: str, b: str) -> float | None:
    """Max contradiction probability across both directions, or None if unavailable.

    None means "unknown", never "fine" — callers must not treat it as a pass or a fail on its own.
    """
    if not available() or not a.strip() or not b.strip():
        return None
    try:
        idx = None
        _pair_probs(a, b)  # forces the load so label_idx is resolved
        idx = (_NLI.label_idx or {}).get("contradiction")
        if idx is None:
            return None
        # One contradicted chunk disqualifies the whole rewrite, so: max over chunks, and over
        # both directions within each chunk. Short inputs yield a single chunk of (a, b), which is
        # exactly the previous behaviour.
        return max(
            max(float(_pair_probs(ca, cb)[idx]), float(_pair_probs(cb, ca)[idx]))
            for ca, cb in _aligned_chunks(a, b)
        )
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
        # NOT chunked, unlike `contradiction_score`. Chunking this was implemented and reverted:
        # over 30 real rewrites it took the veto count from 0 to 2, and printing the responsible
        # chunk pair showed the cause was misalignment, not damage —
        #
        #     SRC chunk: "Our results demonstrate that the attention mechanism improves ..."
        #     OUT chunk: "We also perform a series of ablation studies ... Our results show that
        #                 the attention mechanism improves ..."
        #
        # The rewrite chunk begins a sentence earlier, because proportional splitting drifts once
        # the rewriter has changed sentence lengths. Contradiction survives that drift (it is a MAX
        # over chunks, and unrelated text is "neutral" rather than contradictory — measured
        # unchanged at 1 veto in 30 either way), but entailment is a MIN over eight directional
        # scores and every misaligned pair drags it down. A safety check that rejects faithful
        # output is not a safer check.
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
#
# DO NOT RAISE THIS to catch more. It is tempting: rewrites that ADD content the source never
# stated ("The study found an effect." -> "The peer-reviewed study found a large effect.") score
# 0.003-0.011, above the floor, and a bar around 0.02 would reject them. Re-measured on 26 real
# composite/structural/surgical rewrites, that bar also rejects genuinely faithful work:
#
#     faithful (real rewriter output, n=26)   min 0.01201, three samples below 0.02
#     added-content rewrites (n=8)            max 0.01102
#
# The two populations are 0.001 apart with no margin, so any floor that separates them on one
# sample is fitting noise. Heavy rewording — which is what humanizing IS — genuinely lowers
# bidirectional entailment, and the metric cannot tell that from a fabricated detail.
#
# That is why added/lost specifics are caught by narrow mechanical checks instead —
# :mod:`untell.scripts.numerals` for quantities, :mod:`untell.scripts.hedges` for claim strength,
# :mod:`untell.scripts.roles` for argument swaps. Each answers a question NLI cannot, without
# putting faithful rewrites at risk.
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

    TIGHTENING it does not work either, and that is worth stating because it is the obvious next
    idea. Measured on the embedding backend, 5 faithful rewrites against 5 meaning inversions:

        faithful    0.376 - 0.954   (register shift 0.376, voice change 0.954)
        inversions  0.730 - 0.991   (negation added 0.730, role swap 0.991)

    The ranges overlap and the ordering is backwards — the *most* similar pair in the whole set is a
    role swap at 0.991, and the *least* similar is a faithful register shift at 0.376. No threshold
    admits the faithful set and rejects the inversions, so this fallback is not a bar that needs
    tuning; it is a check that cannot be built from this metric. The only fixes are installing the
    NLI stack, or saying that it is missing — which the loop result now does via ``meaning_gate``.

    NLI has one blind spot of its own, and :mod:`untell.scripts.roles` covers it: rewrites that keep
    every content word and only permute the *roles* ("the company sued the regulator" -> "the
    regulator sued the company") score as near-perfect paraphrases, because as bags of tokens they
    are. Four of the thirteen bad rewrites in the probe set had that shape and all four passed. The
    predicate-argument veto catches 9 of 9 role permutations with 0 false vetoes on 13 faithful
    rewrites, and is skipped entirely when spaCy's model is absent.
    """
    # The mechanical checks first, on EVERY path. They need no model — pure stdlib regex — so
    # gating them behind NLI's availability meant the zero-dependency tier, which is the advertised
    # default, silently ran neither. A rewrite could drop a stated quantity or upgrade a hedged
    # claim there and nothing would object.
    #
    # Running them first is also the cheap order: a candidate rejected here skips four NLI forward
    # passes and a spaCy parse. All the checks are conjunctive vetoes, so order cannot change the
    # verdict, only the cost of reaching it.
    from untell.scripts.hedges import certainty_kept
    from untell.scripts.numerals import numbers_kept

    if not numbers_kept(source, candidate):
        return False
    if not certainty_kept(source, candidate):
        return False

    if not available():
        return sim >= strict_sim_bar

    con = contradiction_score(source, candidate)
    ent = entailment_score(source, candidate)
    if con is None or ent is None:  # model died mid-run -> strict behaviour, never a silent pass
        return sim >= strict_sim_bar

    if not (sim >= relaxed_sim_bar and con < contradiction_bar and ent >= entailment_floor):
        return False

    # Positive evidence only: `role_swap` returns None when the parser is unavailable, and an
    # unavailable check must not become a veto.
    from untell.scripts.roles import role_swap

    return role_swap(source, candidate) is not True


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python scripts/entailment.py "<original>" "<rewrite>"`` -> JSON (``-m`` form works too).

    Exists so the SKILL.md workflow can reach this check. The headless loop got the NLI meaning gate
    (contradiction veto + bidirectional entailment); the skill path — where Claude is the rewriter,
    and which is the flagship product — had no way to call it and was still gating on cosine
    similarity alone. That is the metric measured to pass meaning INVERSIONS at 0.974 ("runs faster"
    -> "runs slower" against a 0.76 bar) while rejecting 6 of 8 faithful register shifts.

    Exit code is the verdict, so a shell step can branch on it without parsing:
      0 = meaning preserved, 1 = rejected (contradiction or no entailment), 2 = usage error.
    """
    import json as _json
    import sys as _sys

    args = argv if argv is not None else _sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(
            'usage: entailment.py "<original>" "<rewrite>"\n\n'
            "Prints JSON: contradiction, entailment, available, preserved.\n"
            "Exit 0 if meaning is preserved, 1 if the rewrite contradicts or fails to entail the\n"
            "original, 2 on usage error. Needs the .[full] extra; without it `available` is false\n"
            "and the check is skipped rather than guessed (exit 0)."
        )
        return 0
    if len(args) < 2:
        logger.error('usage: entailment.py "<original>" "<rewrite>"')
        return 2

    a, b = args[0], args[1]
    con = contradiction_score(a, b)
    ent = entailment_score(a, b)
    if con is None or ent is None:
        # Unknown is NOT a failure: without the model there is nothing to judge with, and refusing
        # every rewrite would be worse than falling back to the similarity gate the skill already runs.
        print(_json.dumps({"available": False, "contradiction": None, "entailment": None,
                           "preserved": True, "note": "NLI unavailable — install .[full] to enable"}))
        return 0
    preserved = con < DEFAULT_CONTRADICTION_BAR and ent >= DEFAULT_ENTAILMENT_FLOOR
    print(_json.dumps({"available": True, "contradiction": round(con, 4),
                       "entailment": round(ent, 4), "preserved": preserved}))
    return 0 if preserved else 1


if __name__ == "__main__":
    raise SystemExit(main())
