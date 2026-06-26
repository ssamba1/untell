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

import math
import re

from .base import clamp01

_SENT_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")
_WORD = re.compile(r"[A-Za-z']+")

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
    # every short sentence as ~AI — the degeneracy that flooded per-sentence targeting. Use a neutral
    # burst contribution there and lean on the common-word signal instead.
    if len(nonempty) < 2:
        burst_signal = 0.5
    else:
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
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _full_score(self, text: str) -> float:
        """True GPT-2 perplexity + per-sentence perplexity variance -> P(AI)."""
        import torch
        from transformers import GPT2LMHeadModel, GPT2TokenizerFast

        if PerplexityBurstinessDetector._model is None:
            PerplexityBurstinessDetector._tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
            PerplexityBurstinessDetector._model = GPT2LMHeadModel.from_pretrained("gpt2").eval()

        tok = PerplexityBurstinessDetector._tokenizer
        model = PerplexityBurstinessDetector._model

        def ppl(s: str) -> float:
            enc = tok(s, return_tensors="pt", truncation=True, max_length=512)
            ids = enc["input_ids"]
            if ids.shape[1] < 2:
                return 100.0
            with torch.no_grad():
                out = model(ids, labels=ids)
            return float(torch.exp(out.loss))

        sents = _sentences(text)
        ppls = [ppl(s) for s in sents] or [ppl(text)]
        mean_ppl = sum(ppls) / len(ppls)
        # Low mean perplexity + low variance across sentences => AI-like.
        var = (sum((p - mean_ppl) ** 2 for p in ppls) / len(ppls)) if len(ppls) > 1 else 0.0
        ppl_signal = clamp01((60.0 - mean_ppl) / 60.0)          # ppl<60 trends AI
        var_signal = clamp01((400.0 - var) / 400.0)             # low variance trends AI
        return clamp01(0.7 * ppl_signal + 0.3 * var_signal)

    def score(self, text: str) -> float:
        if self._torch_ready():
            try:
                return clamp01(self._full_score(text))
            except Exception as exc:  # model/load failure -> heuristic, but say so (don't fail silently)
                import sys

                print(
                    f"[untell] perplexity_burstiness full path failed ({type(exc).__name__}: "
                    f"{str(exc)[:120]}); falling back to lite heuristic.",
                    file=sys.stderr,
                )
        return lite_score(text)
