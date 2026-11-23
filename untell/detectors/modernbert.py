"""ModernBERT AI-text detector adapter (full tier).

``rasbt/ai-text-detector-modernbert`` — ModernBERT-base (~150M parameters) fine-tuned on
``rasbt/human-vs-ai-50k``; Apache-2.0. Added because it was the one detector in the open-detector
audit that generalised to a 2024 model's essays without accusing non-native writers
(docs/observatory/modern-llm.md, open-detectors.md). In calibration v3 it raised recall on those
essays from 15% to 47% while lowering held-out false flags on TOEFL essays from 19.8% to 15.4%
(docs/observatory/calibration.md).

Run the way its ``detector-config.json`` says: up to 8,192 tokens per forward, logits divided by
the published temperature 1.5662 before the softmax, P(AI) = class 1. Always in float32 — the
weights ship in bfloat16, which rounds every probability to a multiple of 1/256 and ties more than
5% of known-human text at exactly 1.0. Input is normalised first (``normalise_for_scoring``), as
for every untell detector; documents past ~6,000 words are windowed and the highest window kept.
"""

from __future__ import annotations

import logging

from .base import batched_windowed_max, clamp01

logger = logging.getLogger(__name__)

_MODEL_ID = "rasbt/ai-text-detector-modernbert"
_MAX_TOKENS = 8192
_TEMPERATURE = 1.566228609277514
# ~0.75 words per token for English prose; keeps every window inside the 8,192-token context.
_WINDOW_WORDS = 6000


class ModernBertDetector:
    name = "modernbert"
    tier = "full"

    _model = None
    _tokenizer = None
    _dead = False
    _warned = False

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if ModernBertDetector._model is None:
            ModernBertDetector._tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
            ModernBertDetector._model = (
                AutoModelForSequenceClassification.from_pretrained(_MODEL_ID).float().eval())
        return ModernBertDetector._tokenizer, ModernBertDetector._model

    def _score_batch(self, windows: list[str]) -> list[float | None]:
        import torch

        tok, model = self._load()
        out: list[float | None] = []
        # One window per forward: at up to 8,192 tokens, padding a batch to its longest member
        # costs more than it saves, and the scores are identical either way.
        for w in windows:
            enc = tok(w, return_tensors="pt", truncation=True, max_length=_MAX_TOKENS)
            with torch.no_grad():
                logits = model(**enc).logits[0] / _TEMPERATURE
            out.append(float(torch.softmax(logits, dim=-1)[1]))
        return out

    def score(self, text: str) -> float | None:
        if ModernBertDetector._dead:
            return None
        if not text.strip():
            return None
        try:
            self._load()
        except Exception as exc:
            # Disable + EXCLUDE (never a fake neutral 0.5 that would pin the ensemble max).
            ModernBertDetector._dead = True
            if not ModernBertDetector._warned:
                logger.warning("modernbert failed to load and was EXCLUDED from the ensemble (%s: %s).",
                               type(exc).__name__, str(exc)[:140])
                ModernBertDetector._warned = True
            raise
        p_ai = batched_windowed_max(text, self._score_batch, window_words=_WINDOW_WORDS)
        return None if p_ai is None else clamp01(float(p_ai))
