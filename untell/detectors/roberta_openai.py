"""RoBERTa-OpenAI detector adapter (full tier).

Wraps ``openai-community/roberta-base-openai-detector`` via a HF text-classification pipeline
on CPU. Weak on modern text (trained on GPT-2 outputs) but a cheap, real supervised proxy that
contributes ensemble diversity. Guarded: unavailable unless ``transformers``+``torch`` import.
"""

from __future__ import annotations

import logging

from .base import clamp01, windowed_max

logger = logging.getLogger(__name__)

_MODEL_ID = "openai-community/roberta-base-openai-detector"


class RobertaOpenAIDetector:
    name = "roberta_openai"
    tier = "full"

    _pipe = None
    _dead = False
    _warned = False

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return False

    def _load(self):
        if RobertaOpenAIDetector._pipe is None:
            from transformers import pipeline

            RobertaOpenAIDetector._pipe = pipeline(
                "text-classification",
                model=_MODEL_ID,
                tokenizer=_MODEL_ID,
                truncation=True,
                max_length=512,
                top_k=None,
                device=-1,  # CPU
            )
        return RobertaOpenAIDetector._pipe

    def score(self, text: str) -> float | None:
        if RobertaOpenAIDetector._dead:
            return None
        if not text.strip():
            return None
        try:
            pipe = self._load()
        except Exception as exc:
            RobertaOpenAIDetector._dead = True
            if not RobertaOpenAIDetector._warned:
                logger.warning(
                    "roberta_openai failed to load and was EXCLUDED from the ensemble "
                    "(%s: %s). Often a NumPy 2.x / torch mismatch - see README troubleshooting.",
                    type(exc).__name__, str(exc)[:140],
                )
                RobertaOpenAIDetector._warned = True
            raise
        def _one(window: str) -> float:
            out = pipe(window)
            # `top_k=None` => list[list[{label, score}]]; labels are "Real"/"Fake" (Fake == AI).
            scores = out[0] if isinstance(out[0], list) else out
            fake = next(
                (s["score"] for s in scores if str(s["label"]).lower() in ("fake", "label_1", "ai")),
                None,
            )
            if fake is None:
                # Fall back: 1 - P(real) if only the real label is present.
                real = next(
                    (s["score"] for s in scores if str(s["label"]).lower() in ("real", "label_0")), 0.5
                )
                fake = 1.0 - real
            return fake

        # Whitespace normalised for the same reason as hc3_roberta, though this model is far less
        # sensitive to it: MEASURED on 100 RAID pairs, a space before each period costs it 0.0339
        # AUROC (0.8858 -> 0.8519) where it costs hc3_roberta 0.8300. Small, and free to recover.
        # Windowed: the pipeline truncates at 512 tokens, so everything past ~380 words was
        # invisible — a long document was scored on its opening paragraph alone.
        fake = windowed_max(text, _one)
        return None if fake is None else clamp01(fake)
