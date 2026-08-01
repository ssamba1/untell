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

_SENT_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")
_WORD = re.compile(r"[A-Za-z']+")

# Calibration for the full (GPT-2) path. `_NLL_*` govern mean token surprisal over the whole
# passage; `_SPREAD_*` govern the standard deviation of per-sentence mean surprisal. Lower on both
# axes => more machine-like.
#
# MEASURED on 120 HC3 human/ChatGPT paragraph pairs (`untell-detector-audit --pairs 120`):
#   mean surprisal   human 3.87 +- 0.40   ai 2.21 +- 0.23
#   sentence spread  human 0.72 +- 0.33   ai 0.53 +- 0.17
# Each midpoint sits between the class means and each scale spans the observed spread, so the
# logistic stays responsive across the whole range instead of saturating at the ends. The
# constants it replaced (mean per-sentence perplexity < 60, variance < 400) sat far outside the
# range those quantities take, which pinned a large class of ordinary input to exactly 0.0.
_NLL_MID = 3.036
_NLL_SCALE = 0.315
_SPREAD_MID = 0.625
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
    parts = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
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


def lite_score(text: str) -> float:
    """Deterministic, stdlib-only P(AI) heuristic in [0, 1]."""
    if not text or not text.strip():
        return 0.5
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
        return clamp01(common_signal)

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

        enc = tok(text, return_tensors="pt", truncation=True, max_length=1024,
                  return_offsets_mapping=True)
        ids = enc["input_ids"]
        if ids.shape[1] < 2:
            return None, None
        with torch.no_grad():
            logits = model(ids).logits
        lp = torch.log_softmax(logits[:, :-1, :].float(), dim=-1)
        targets = ids[:, 1:]
        nll = -lp.gather(-1, targets.unsqueeze(-1)).squeeze(-1)[0]
        # offsets align with `targets`, i.e. tokens 1..T-1 — the first token has no prediction.
        offsets = enc["offset_mapping"][0][1:].tolist()
        return nll, offsets

    def _full_score(self, text: str) -> float:
        """GPT-2 perplexity + per-sentence perplexity variance -> P(AI).

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
            return clamp01(ppl_signal)
        burst_signal = 1.0 / (1.0 + math.exp((spread - _SPREAD_MID) / _SPREAD_SCALE))
        return clamp01(_PPL_WEIGHT * ppl_signal + (1.0 - _PPL_WEIGHT) * burst_signal)

    def score(self, text: str) -> float | None:
        # Empty/whitespace input carries no signal. The Detector protocol (base.py) requires None
        # here so the ensemble EXCLUDES it: returning a number folds a fabricated score into the
        # max/mean aggregation. Previously this path reached lite_score(), which answered 0.5 for
        # empty text, and score_text("") duly reported flagged=True — an empty string classified as
        # AI-generated.
        if not text or not text.strip():
            return None
        if self._torch_ready():
            try:
                return clamp01(self._full_score(text))
            except Exception as exc:  # model/load failure -> heuristic, but say so (don't fail silently)
                logger.warning(
                    "perplexity_burstiness full path failed (%s: %s); falling back to lite heuristic.",
                    type(exc).__name__, str(exc)[:120],
                )
        return lite_score(text)
