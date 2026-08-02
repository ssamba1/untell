"""Perplexity + burstiness detector.

Two implementations behind one adapter:

* **lite** (always available, stdlib only): a GPTZero-style heuristic. AI text tends to be
  low-perplexity (predictable word choice) and low-burstiness (uniform sentence length).
  We approximate perplexity with a corpus word-rarity score and burstiness with the
  coefficient of variation of sentence lengths, then map the pair to P(AI) ∈ [0, 1].
  No model download, fully deterministic.

* **full** (when ``torch``+``transformers`` are importable): true GPT-2 token perplexity and
  per-sentence perplexity variance — the honest version of the same signal.

The lite path is intentionally a *weak* proxy: good enough to drive the feedback loop and to
demo zero-install, not a ground-truth detector. See README caveats.
"""

from __future__ import annotations

import logging
import math
import re

from .base import clamp01

logger = logging.getLogger(__name__)

# (sentence splitting lives in untell.text_split — imported lazily inside `_sentences`)
_WORD = re.compile(r"[A-Za-z']+")

# Calibration for the full (GPT-2) path. `_NLL_*` govern mean token surprisal over the whole
# passage; `_SPREAD_*` govern the standard deviation of per-sentence mean surprisal. Lower on both
# axes => more machine-like.
#
# MEASURED on 120 HC3 human/ChatGPT paragraph pairs (`untell-detector-audit --pairs 120`):
#   mean surprisal   human 3.87 +- 0.40   ai 2.21 +- 0.23
#   sentence spread  human 0.72 +- 0.33   ai 0.53 +- 0.17
# The midpoints do NOT sit at the class midpoint, which is where they used to sit and which is a
# mistake worth spelling out. A midpoint halfway between the classes maps the boundary case to 0.5,
# so every human document in the lower part of its range lands well above the 0.30 default
# threshold. Measured with the old NLL_MID of 3.036 — the exact midpoint of human 3.85 and AI 2.23 —
# this detector reported a mean of 0.244 on human text and flagged 32% of it, and the ensemble
# takes `max`, so that became the full tier's false-positive floor.
#
# What matters is not where the classes divide but where the THRESHOLD lands relative to the human
# distribution. Refit on 40 HC3 pairs and checked against 60 unseen ones:
#
#   raw quantities       mean surprisal  human 3.85 [3.09, 5.15]   ai 2.23 [1.85, 2.62]
#                        sentence spread human 0.78 [0.23, 1.74]   ai 0.48 [0.19, 0.89]
#
#   NLL_MID 3.036 / SPREAD_MID 0.625   held-out FPR 37%  TPR 100%  AUROC 1.000  human mean 0.260
#   NLL_MID 2.680 / SPREAD_MID 0.400   held-out FPR 12%  TPR 100%  AUROC 0.999  human mean 0.154
#
# The true-positive rate is unchanged at 100% and AUROC moves by 0.001 — the detector separated the
# classes just as well before, it was reporting them on a scale that put ordinary human writing
# over the line. Scales are unchanged; only the midpoints moved.
#
# Tokens of preceding text carried into each scoring window past the first, so that a long document
# is scored with context throughout instead of being cut off at GPT-2's 1024-token limit.
_CONTEXT = 256
_NLL_MID = 2.680
_NLL_SCALE = 0.315
_SPREAD_MID = 0.400
_SPREAD_SCALE = 0.250
# Perplexity carries most of the signal (AUROC 1.00 alone on HC3 vs 0.70 for spread), but the
# blend keeps burstiness contributing: it is an independent axis, so a rewriter that lowers only
# perplexity cannot walk the whole score down on its own.
_PPL_WEIGHT = 0.55
# Held out from the fit: AUROC 0.999 over 200 unseen HC3 pairs, nothing saturated at 0.0 or 1.0.
#
# CAVEAT, and it is a real one: HC3's machine side is 2022-era ChatGPT, whose register is far more
# distinctive than a current model's. Spot-checked against modern formal AI prose the classes
# overlap substantially, so 0.999 is a statement about this dataset, not a general accuracy claim.
# It does establish the thing that matters here — the detector responds in the correct direction
# across the range instead of anti-correlating and pinning to a constant.

# A tiny stop/common-word list. High coverage by these high-frequency tokens correlates with
# low perplexity (predictable text). This is a heuristic stand-in for a real LM, not lexicon.
_COMMON = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on",
    "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we",
    "say", "her", "she", "or", "an", "will", "my", "one", "all", "would", "there", "their",
    "what", "so", "up", "out", "if", "about", "who", "get", "which", "go", "me", "when", "make",
    "can", "like", "time", "no", "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then", "now", "look", "only",
    "come", "its", "over", "think", "also", "back", "after", "use", "two", "how", "our", "work",
    "first", "well", "way", "even", "new", "want", "because", "any", "these", "give", "day",
    "most", "us", "is", "are", "was", "were", "been", "has", "had", "more", "very", "such",
    "additionally", "moreover", "furthermore", "however", "therefore", "thus", "overall",
}


def _sentences(text: str) -> list[str]:
    # Shared, abbreviation-aware splitter (untell.text_split): a naive split on ".\s" made "Dr."
    # its own "sentence", and per-sentence surprisal over a one-token fragment is noise fed
    # straight into the burstiness term.
    from untell.text_split import split_sentences

    parts = split_sentences(text)
    return parts or ([text.strip()] if text.strip() else [])


def _burstiness(sentences: list[str]) -> float:
    """Coefficient of variation of sentence word-counts. Low CV => uniform => AI-like."""
    lengths = [len(_WORD.findall(s)) for s in sentences]
    lengths = [n for n in lengths if n > 0]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    return math.sqrt(var) / mean


def _common_ratio(text: str) -> float:
    """Fraction of tokens that are very common words. High => predictable => AI-like."""
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return 0.0
    return sum(1 for w in words if w in _COMMON) / len(words)


# Below this word count the common-word ratio is not a ratio. MEASURED on the stdlib path:
#   "a" -> 1.0     "the" -> 1.0     "I" -> 1.0      "it is" -> 1.0     "the of and" -> 1.0
#   "Hello" -> 0.0             "xylophone" -> 0.0
# The answer is decided entirely by whether the handful of words appear in a 120-word stoplist, and
# it is returned at FULL confidence in both directions. That is not a weak signal, it is noise
# reported as certainty, and it reaches the loop as a real detector score.
_MIN_WORDS_FOR_SIGNAL = 5


# Tell density that reads as "clearly AI" for one sentence. AI sentences in the probe set carried
# 1-3 tells in ~10-15 words (roughly 10-25 per 100 words); human ones carried none.
_SENTENCE_TELL_SATURATION = 22.0

# Hard ceiling on the (measured-backwards) common-word term for a lone sentence. Must stay strictly
# BELOW the default detection threshold so this term can never flag text by itself.
_RATIO_CEILING = 0.25


def _single_sentence_signal(text: str, fallback: float, cap: float = _RATIO_CEILING) -> float:
    """P(AI) for a lone sentence, where burstiness carries no information.

    The common-word ratio must NOT drive this. Measured on 5 AI and 5 human single sentences, the
    common-word signal alone scored **AUROC 0.000** — perfectly inverted, every AI sentence ranked
    below every human one. The cause is that the ratio was calibrated on a kind of AI text that is
    no longer typical: modern model prose reaches for inflated vocabulary ("leverage",
    "transformative", "numerous"), which drives the common-word ratio DOWN, while casual human
    speech ("we tried it twice and it still didn't work") is nearly all common words and drives it
    UP. So the one surviving signal ranked the AI text as maximally human.

    That was not merely a dead detector. `sentences.py` scores each sentence in isolation, so
    per-sentence targeting — the skill's step 4b — was pointed at whichever sentences read most
    human, telling the rewriter to attack exactly the wrong spans.

    AI-tell density is the primary term: it counts markers actually characteristic of machine prose
    and is stdlib-only, so the zero-dependency tier keeps working. ``fallback`` is whatever
    predictability signal the active backend produced, kept as a floor via ``max`` so it can still
    carry a sentence the tells miss.

    ``cap`` is what separates the two backends, and it is not cosmetic:

    * **lite** (common-word ratio) caps at ``_RATIO_CEILING``, below the detection threshold. That
      term is backwards — casual human speech is nearly all common words — so it may position a
      sentence but must never flag one alone.
    * **GPT-2 perplexity** passes ``cap=1.0``. MEASURED on 60 real HC3 pairs, it ranks single
      sentences at AUROC ~0.97, so capping it is not conservatism, it is discarding the best signal
      available. Capping it at 0.25 was tried and regressed real text badly: every HC3 AI sentence
      pinned to exactly 0.250, under the 0.30 threshold, and `sentences.py` (which flags the worst
      third AND requires >= threshold) flagged 0 of 46 sentences across six AI paragraphs.

    The two terms cover different failure modes, which is why this maxes rather than replaces:
    perplexity catches bland, predictable AI prose; tells catch the modern flowery register where
    perplexity inverts because the rare vocabulary reads as *surprising*.
    """
    from untell.scripts.tells import (
        score_tells,  # local: avoids a detectors -> scripts import cycle
    )

    try:
        density = float(score_tells(text).get("tells_per_100w") or 0.0)
    except Exception:
        # Never let a tells failure resurrect an unreliable term as the whole answer.
        return min(fallback, cap)

    tell_signal = clamp01(density / _SENTENCE_TELL_SATURATION)
    return max(tell_signal, min(fallback, cap))


def lite_score(text: str) -> float | None:
    """Deterministic, stdlib-only P(AI) heuristic in [0, 1], or None when the text is too short.

    ``None`` is the Detector protocol's "no signal" — ``score_text`` excludes it and reports
    ``scored: False`` rather than folding a fabricated number into the ensemble max.
    """
    if not text or not text.strip():
        return None
    if len(_WORD.findall(text)) < _MIN_WORDS_FOR_SIGNAL:
        return None
    sents = _sentences(text)
    nonempty = [s for s in sents if _WORD.findall(s)]
    common = _common_ratio(text)          # ~0.3 (varied) .. ~0.6 (formulaic)
    # Map common-word ratio: above ~0.45 trends AI-formulaic.
    common_signal = clamp01((common - 0.30) / 0.30)

    # Burstiness needs >= 2 sentences to mean anything. On a single sentence/fragment it is
    # *undefined* (the CV of one length is 0), so treating that as low-burstiness wrongly scored
    # every short sentence as ~AI — the degeneracy that flooded per-sentence targeting.
    #
    # The fix for that degeneracy used to be `burst_signal = 0.5`, described as "neutral". It is not
    # neutral: at weight 0.6 it contributes a FIXED 0.30 to every single-sentence score, and 0.30 is
    # exactly the default detection threshold (which compares with >=). So the lower half of the
    # range was unreachable and every single-sentence input sat on the decision boundary no matter
    # how human it read. Genuinely leaning on the common-word signal — using it alone, at full
    # weight, when burstiness carries no information — is what the comment always intended.
    if len(nonempty) < 2:
        return clamp01(_single_sentence_signal(text, common_signal))

    burst = _burstiness(sents)        # ~0.0 (uniform) .. ~0.8+ (varied human prose)
    # Map burstiness to an AI-likelihood contribution: low burstiness -> high P(AI).
    # CV around 0.5 is typical human prose; below ~0.25 reads as machine-uniform.
    burst_signal = clamp01((0.55 - burst) / 0.55)

    # Blend (burstiness weighted higher — it's the stronger of the two weak signals).
    return clamp01(0.6 * burst_signal + 0.4 * common_signal)


class PerplexityBurstinessDetector:
    """Adapter: GPT-2 perplexity+burstiness when torch is present, else lite heuristic."""

    name = "perplexity_burstiness"
    tier = "lite"  # always available at lite; auto-upgrades its math when torch is importable

    _model = None
    _tokenizer = None

    def available(self) -> bool:  # always — the lite path needs nothing
        return True

    def _torch_ready(self) -> bool:
        # UNTELL_LITE_NO_TORCH=1 forces the stdlib heuristic even when torch is importable.
        #
        # This detector silently upgrades to GPT-2 perplexity whenever torch is present — better
        # math, but MEASURED at 10.6s on the first call. That makes `--tier lite` take ~12s on any
        # machine with torch installed, while the tier is documented and marketed as the instant,
        # zero-dependency path. The upgrade is worth keeping (it is a genuinely better signal), but
        # "lite" must have a way to actually be lite.
        import os

        if os.environ.get("UNTELL_LITE_NO_TORCH") == "1":
            return False
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _token_nll(self, text: str):
        """Per-token negative log-likelihood under GPT-2, **in context**, plus token offsets.

        Returns ``(nll, offsets)`` where ``nll[i]`` is the surprisal of the token spanning
        ``offsets[i]`` given every token before it. One forward pass over the whole passage.
        """
        import torch
        from transformers import GPT2LMHeadModel, GPT2TokenizerFast

        if PerplexityBurstinessDetector._model is None:
            PerplexityBurstinessDetector._tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
            PerplexityBurstinessDetector._model = GPT2LMHeadModel.from_pretrained("gpt2").eval()

        tok = PerplexityBurstinessDetector._tokenizer
        model = PerplexityBurstinessDetector._model

        # NOT truncated. GPT-2's context is 1024 tokens and a document can be far longer; scoring
        # only the opening ~750 words would let everything after that drift unmeasured. The text is
        # instead walked in windows, each carrying `_CONTEXT` tokens of preceding text whose
        # surprisals are discarded — so every token after the first is scored *with* real context
        # rather than as if it opened the document.
        # verbose=False: without truncation the tokenizer warns that the sequence exceeds the
        # model's 1024-token limit, which is alarming and wrong here — the windowing below never
        # feeds the model more than it can take.
        enc = tok(text, return_tensors="pt", return_offsets_mapping=True, verbose=False)
        ids = enc["input_ids"]
        total = ids.shape[1]
        if total < 2:
            return None, None

        window = 1024
        stride = window - _CONTEXT
        chunks = []
        start = 0
        while start < total - 1:
            end = min(start + window, total)
            chunk = ids[:, start:end]
            with torch.no_grad():
                logits = model(chunk).logits
            lp = torch.log_softmax(logits[:, :-1, :].float(), dim=-1)
            targets = chunk[:, 1:]
            chunk_nll = -lp.gather(-1, targets.unsqueeze(-1)).squeeze(-1)[0]
            # Drop the context prefix on every window but the first: those tokens were already
            # scored by the previous window, with at least as much context.
            keep_from = 0 if start == 0 else _CONTEXT - 1
            chunks.append(chunk_nll[keep_from:])
            if end >= total:
                break
            start += stride

        nll = torch.cat(chunks) if len(chunks) > 1 else chunks[0]
        # offsets align with `targets`, i.e. tokens 1..T-1 — the first token has no prediction.
        offsets = enc["offset_mapping"][0][1:].tolist()
        n = min(len(nll), len(offsets))
        return nll[:n], offsets[:n]

    def _full_score(self, text: str) -> float | None:
        """GPT-2 perplexity + per-sentence perplexity variance -> P(AI), or None on no signal.

        Both quantities are read off ONE in-context forward pass over the whole passage.
        The previous implementation re-encoded every sentence **in isolation** and averaged the
        resulting perplexities, which discards exactly the signal it was trying to measure:
        predictability comes from context, and a sentence scored alone has none. Measured, that
        made the detector anti-correlated at paragraph length — formulaic AI prose read as
        *surprising* while a long, repetitive human sentence read as predictable — and the linear
        clamps below saturated it to exactly 0.0 on a large class of ordinary input, so the loop
        declared such text human and rewrote nothing at all.
        """
        import math

        nll, offsets = self._token_nll(text)
        if nll is None:
            return lite_score(text)

        mean_nll = float(nll.mean())

        # Burstiness = spread of per-sentence mean surprisal, grouped from the same in-context
        # pass via character offsets. Human prose varies (some sentences land, some surprise);
        # generated prose holds a near-constant surprisal.
        bounds = []
        pos = 0
        for s in _sentences(text):
            idx = text.find(s, pos)
            if idx < 0:
                continue
            bounds.append((idx, idx + len(s)))
            pos = idx + len(s)
        per_sent: list[float] = []
        for start, end in bounds:
            vals = [float(v) for v, (a, b) in zip(nll, offsets) if a >= start and b <= end and b > a]
            if len(vals) >= 3:
                per_sent.append(sum(vals) / len(vals))
        if len(per_sent) >= 2:
            m = sum(per_sent) / len(per_sent)
            spread = math.sqrt(sum((x - m) ** 2 for x in per_sent) / len(per_sent))
        else:
            # One sentence: no burstiness information. Lean entirely on perplexity rather than
            # substituting a fixed "neutral" that would pin the score to a constant band.
            spread = None

        # Logistic calibration, not a linear clamp. A clamp maps everything outside its window to
        # exactly 0.0 or 1.0, which is how the old constants (mean_ppl < 60, variance < 400 — both
        # far outside the range these quantities actually take) turned the detector into a
        # near-constant. Midpoints and scales below are fitted to the measured GPT-2 distribution
        # over paragraph-length human/AI pairs; see eval/detector_audit.py for the harness.
        ppl_signal = 1.0 / (1.0 + math.exp((mean_nll - _NLL_MID) / _NLL_SCALE))
        if spread is None:
            # One sentence. Perplexity alone is INVERTED here, measured: human_mean 0.224 vs
            # ai_mean 0.154 on the audit's sentence probes. The midpoint above is fitted to
            # paragraph-length text, and at sentence length the quantity itself flips sign for the
            # distribution this tool exists to handle — casual human speech ("we tried it twice and
            # it still didn't work") is extremely predictable, while modern formal AI prose reaches
            # for rarer words ("transformative", "stakeholders") that GPT-2 finds MORE surprising.
            # Same failure the lite path had, arrived at from the opposite direction: both terms
            # measure predictability, and predictability stops tracking authorship at this length.
            # So the predictability term is capped as a floor and tell density decides, exactly as
            # on the lite path — one rule for single sentences regardless of which backend ran.
            return _single_sentence_signal(text, ppl_signal, cap=1.0)
        burst_signal = 1.0 / (1.0 + math.exp((spread - _SPREAD_MID) / _SPREAD_SCALE))
        return clamp01(_PPL_WEIGHT * ppl_signal + (1.0 - _PPL_WEIGHT) * burst_signal)

    def score(self, text: str) -> float | None:
        # This detector deliberately does NOT use `windowed_max`, unlike every supervised adapter.
        # That looks like an oversight and was "fixed" once; the measurement says otherwise.
        #
        # Their problem was TRUNCATION — `truncation=True, max_length=512` meant they physically
        # could not see past ~380 words, so windowing let them read the document at all. This
        # detector already sees all of it, and both its terms are AGGREGATE properties: burstiness
        # is the variation of sentence lengths ACROSS a document, and the common-word ratio is a
        # document-wide proportion. Cutting the document into windows destroys the very quantity
        # being measured, and taking the max of many noisy window scores inflates every long input.
        #
        # MEASURED on real HC3 documents, windowed vs whole-document:
        #     3 paragraphs   AUROC 0.887 / FPR 90%   vs   0.975 / FPR 30%
        #     6 paragraphs   AUROC 0.980 / FPR 90%   vs   1.000 / FPR  0%
        # True-positive rate was 100% either way, so windowing bought nothing and flagged nine out
        # of ten human documents.
        #
        # The known cost of keeping it global: a long human tail dilutes an embedded AI section
        # (measured 0.624 -> 0.239 on the stdlib path). That is the correct trade for a
        # document-level aggregate, the supervised adapters DO window so the full tier still catches
        # it, and `sentences.py` scores sentences individually for per-section targeting.
        #
        # Empty/whitespace input carries no signal. The Detector protocol (base.py) requires None
        # here so the ensemble EXCLUDES it: returning a number folds a fabricated score into the
        # max/mean aggregation. Previously this path reached lite_score(), which answered 0.5 for
        # empty text, and score_text("") duly reported flagged=True — an empty string classified as
        # AI-generated.
        if not text or not text.strip():
            return None
        # The same abstention floor both paths are supposed to share. It lived only inside
        # `lite_score`, so whenever torch was importable — the default once `.[full]` is installed —
        # `_full_score` ran instead and no floor applied at all. Its own guard is on TOKEN count
        # (it needs an in-context pass to produce anything), which trips at one token, not five
        # words. Measured before:
        #     "Hi."                     -> 0.811   a two-token fragment called AI
        #     "word word"   (2 words)   -> 0.000   "definitely human", from two words
        #     "word word word word"     -> 0.000   same
        # Both directions are confident verdicts drawn from no stylometric evidence, and both feed
        # the ensemble max as if they were measurements.
        if len(_WORD.findall(text)) < _MIN_WORDS_FOR_SIGNAL:
            return None
        if self._torch_ready():
            try:
                full = self._full_score(text)
                # None propagates as "no signal" — clamp01(None) would raise, and clamping a
                # fabricated substitute is exactly what this detector's history warns against.
                return None if full is None else clamp01(full)
            except Exception as exc:  # model/load failure -> heuristic, but say so (don't fail silently)
                logger.warning(
                    "perplexity_burstiness full path failed (%s: %s); falling back to lite heuristic.",
                    type(exc).__name__, str(exc)[:120],
                )
        return lite_score(text)
