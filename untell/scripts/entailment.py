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
import re
from functools import lru_cache

from untell.text_split import aligned_chunks

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
# Applied to BOTH scores. It was contradiction-only at first, because chunking entailment with a
# proportional splitter caused false vetoes; that reason expired when the cut points moved to
# difflib, and leaving entailment whole-text meant deletions past ~130 words scored 0.98 and passed
# every gate. The measurement for both halves is recorded in `entailment_score`.
#
# Cost, over 30 real rewrites of median 298 words: 0.17s -> 0.57s per pair, so the gate is roughly
# 3.4x dearer on long input and unchanged on short (one chunk reproduces the old call exactly).
# Veto rate on those same 30 went 1 -> 2, and the one added veto was inspected and is a TRUE
# catch: "applied to various tasks" -> "applied to all sorts of tasks", an overclaim the whole-text
# score diluted to 0.29 and the aligned chunk scores at 0.61.


def contradiction_score(a: str, b: str) -> float | None:
    """Max contradiction probability across both directions, or None if unavailable.

    None means "unknown", never "fine" — callers must not treat it as a pass or a fail on its own.
    """
    if not available() or not a.strip() or not b.strip():
        return None
    try:
        idx = None
        if _NLI.label_idx is None:
            # One forward pass to resolve the label positions from the model config. Guarded,
            # because this used to run on EVERY call: it scores the whole (a, b) pair and then
            # throws the result away, since the chunk loop below is what actually decides. That was
            # free only when `entailment_score` ran afterwards and hit the cache with the same pair
            # — a caller that wants the contradiction score alone paid for a pass it never used,
            # about 11% of this gate's cost on a four-chunk document.
            _pair_probs(a, b)
        idx = (_NLI.label_idx or {}).get("contradiction")
        if idx is None:
            return None
        # One contradicted chunk disqualifies the whole rewrite, so: max over chunks, and over
        # both directions within each chunk. Short inputs yield a single chunk of (a, b), which is
        # exactly the previous behaviour.
        #
        # An UNCHANGED chunk scores 0 without asking the model. Text cannot contradict itself, and
        # the model does not know that: MEASURED, `contradiction_score(doc, doc)` on a real 301-word
        # RAID abstract returns 0.6091 — over the 0.50 bar — so `meaning_preserved(text, text)` was
        # False and no rewrite of that document could ever be adopted. 1 of 30 RAID documents and
        # 3 of 60 across both corpora sit at or above 0.25 on the identity case alone.
        #
        # The cause is not alignment: the offending chunk is byte-identical on both sides. It is
        # that a chunk is a mid-document slice, so it starts mid-sentence ("extensively evaluated
        # on a large dataset of SAS images, showcasing…"), and an NLI model given a fragment as both
        # premise and hypothesis returns noise. Comparing a string with itself is the one case where
        # the answer is known in advance, so it is answered here instead of asked.
        #
        # This also removes the model call for every untouched chunk of a real rewrite, which is
        # most of them — the rewriter edits a fraction of a long document.
        return max(
            0.0
            if ca == cb
            else max(float(_pair_probs(ca, cb)[idx]), float(_pair_probs(cb, ca)[idx]))
            for ca, cb in aligned_chunks(a, b)
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
        # One pass to resolve the label positions on first use; the chunk loop below does the work.
        if _NLI.label_idx is None:
            _pair_probs(a, b)
        idx = (_NLI.label_idx or {}).get("entailment")
        if idx is None:
            return None
        # CHUNKED, and the history matters because it was deliberately not for a while. Chunking
        # this was implemented and reverted once: over 30 real rewrites it took the veto count from
        # 0 to 2, and the responsible chunk pair showed misalignment rather than damage —
        #
        #     SRC chunk: "Our results demonstrate that the attention mechanism improves ..."
        #     OUT chunk: "We also perform a series of ablation studies ... Our results show that
        #                 the attention mechanism improves ..."
        #
        # The rewrite chunk began a sentence earlier because PROPORTIONAL splitting drifts once the
        # rewriter has changed sentence lengths. Contradiction survived that drift (a MAX over
        # chunks, and unrelated text is neutral rather than contradictory) but entailment is a MIN
        # over directional scores, so every misaligned pair dragged it down.
        #
        # That reason no longer holds: `aligned_chunks` cuts on difflib opcodes, not proportions.
        # RE-MEASURED against the current aligner — of 25 candidates the gate accepts today,
        # chunked entailment newly vetoes 0.
        #
        # And leaving it unchunked was not free. The whole-pair call truncates, so it stops seeing
        # anything past roughly the first 130 words. MEASURED, deleting most of a sentence at
        # increasing depth into a document:
        #
        #     loss after  10 words   entailment 0.0017   caught
        #     loss after 140 words   entailment 0.9800   MISSED
        #     loss after 280 words   entailment 0.9800   MISSED
        #
        # with contradiction innocent at 0.003 (dropping content contradicts nothing), similarity
        # 0.965, and the numeral, certainty and polarity guards all clean. So a rewriter could
        # delete the second half of any sentence past the first ~130 words and the whole gate passed
        # it. Chunked, the same edits score 0.0038 and 0.0032 — under the floor, caught. This is the
        # meaning-LOSS half of the failure the repo's own worked example describes for inversion;
        # the inversion half was fixed by chunking contradiction and this half was left open.
        #
        # An unchanged chunk is perfectly entailed in both directions, so it scores 1.0 without a
        # model call — same reasoning as in `contradiction_score`, and it is most chunks of a real
        # rewrite.
        #
        # KNOWN LIMIT, measured rather than assumed. Chunking moves the blind spot; it does not
        # remove it. A deletion is scored against the whole chunk it lands in, so the surrounding
        # identical text dilutes it. Deleting the same 27-word clause at increasing depth:
        #
        #     document  30-174 words   entailment 0.0014-0.0032   caught
        #     document      318 words   entailment 0.0842         MISSED
        #
        # At 318 words the text splits into four ~80-word chunks; three are identical and the
        # fourth holds 80 source words against 53, so the deleted clause is a third of a chunk that
        # is otherwise word-for-word the same, and the model reads the chunk as largely entailed.
        # Smaller deletions run out of margin earlier: a 9-word clause lands at 0.0021-0.0054
        # against a 0.005 floor, straddling it, which is the same narrow gap the floor's own note
        # records (bad rewrites 0.003-0.011, faithful ones down to 0.012).
        #
        # Not fixed here because the obvious repair — smaller chunks — trades against the
        # misalignment that caused the original revert, and neither bound has been measured. What
        # is fixed is the case that was unconditional: before chunking, ANY deletion past ~130
        # words scored 0.98 and passed.
        return min(
            1.0
            if ca == cb
            else min(float(_pair_probs(ca, cb)[idx]), float(_pair_probs(cb, ca)[idx]))
            for ca, cb in aligned_chunks(a, b)
        )
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

# Deletion is the one defect class the zero-dependency path cannot see, and it is not hypothetical:
# this pipeline now contains a transform that removes whole sentences.
#
# MEASURED. Dropping one of three sentences from a paragraph scores cosine similarity **0.949** —
# above the strict 0.76 bar, so the similarity-only path ADMITS it — with contradiction 0.007, also
# clear. Only the entailment floor rejects it, at 0.0015, and that floor needs the NLI stack:
#
#     candidate         sim     entailment   contradiction   NLI verdict   similarity-only
#     drop 1 of 3     0.949        0.0015         0.007        rejected       ADMITTED
#     drop 2 of 3     0.897        0.0014         0.009        rejected       ADMITTED
#     half a clause   0.761        0.0012         0.021        rejected       ADMITTED
#
# **Counted in WORDS, not as a ratio, and that correction is the whole design.** A ratio floor of
# 0.80 looked clean against 445 corpus-length rewrites (min 0.902) and broke the loop on a 24-word
# input, where removing "Moreover," and "it is important to note that" — the actual job — costs 25%
# of the document. Filler is roughly constant in words and the documents are not, so the ratio was a
# property of the corpus it was measured on rather than of the rewriters.
#
# Re-measured as words lost, over 223 genuine rewrites from structural, surgical and composite,
# short probes and HC3/RAID together:
#
#     source length     n     max lost   median lost
#         0-40 words    18        5           1
#       120-400 words  205        9           0
#
# against 12, 26 and 36 words for the three deletions above. So a rewrite may lose the LARGER of a
# fixed slack and a share of the document — the fixed part covers short input where a few filler
# words are a large fraction, the share covers long input where filler scales with length.
_LENGTH_SLACK_WORDS = 10
_LENGTH_SLACK_SHARE = 0.10

# **The margin is one word, and that is a real limit rather than a number to tune.** The largest
# observed legitimate loss is 9 words; the smallest deletion this catches is 12. A dropped sentence
# of ten words or fewer is not separable from aggressive filler removal by length alone — no choice
# of constants fixes that, because the two populations genuinely touch there. What this buys is
# sentence-scale deletion on the path that has no model to catch it; smaller losses still need NLI.

_LENGTH_WORD = re.compile(r"[A-Za-z0-9']+")


def words_lost(source: str, candidate: str) -> int:
    """How many words ``candidate`` drops relative to ``source``. Negative when it grew."""
    return len(_LENGTH_WORD.findall(source)) - len(_LENGTH_WORD.findall(candidate))


def deletion_allowance(source: str) -> float:
    """The most a faithful rewrite of ``source`` may drop. See the measurement above."""
    return max(_LENGTH_SLACK_WORDS, _LENGTH_SLACK_SHARE * len(_LENGTH_WORD.findall(source)))


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
    from untell.scripts.hedges import certainty_kept, polarity_kept
    from untell.scripts.numerals import numbers_kept

    if not numbers_kept(source, candidate):
        return False
    if not certainty_kept(source, candidate):
        return False
    # Polarity, which the NLI pair below does not reliably catch inside a long sentence. MEASURED
    # with every gate live: negating the main clause of a 24-word clinical sentence scored
    # contradiction 0.066 and entailment 0.929, and passed. Cost of the check on real output:
    # 0 of 30 HC3 and 0 of 30 RAID loop results change their negation count, because the
    # rewriter's transforms are substitutions, merges and splits — none of which touches polarity.
    if not polarity_kept(source, candidate):
        return False
    # Deletion, which is the ONE defect class the zero-dependency path cannot otherwise see: a
    # dropped sentence scores similarity 0.949 against a 0.76 bar and contradicts nothing, so only
    # the entailment floor rejects it and that floor needs the NLI stack. See the measurement at
    # `_LENGTH_SLACK_WORDS`. Mechanical, so it runs on every path — which is the whole point.
    if words_lost(source, candidate) > deletion_allowance(source):
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
