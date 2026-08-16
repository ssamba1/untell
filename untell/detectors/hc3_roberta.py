"""HC3 ChatGPT-detector adapter (full tier).

``Hello-SimpleAI/chatgpt-detector-roberta`` — RoBERTa-base (~125M, fast on CPU) fine-tuned on HC3
(human vs ChatGPT answers). A cheap, more-modern supervised proxy than RoBERTa-OpenAI; adds ensemble
diversity. License: CC-BY-SA (inherited from HC3). Guarded: unavailable unless torch+transformers.

P(AI) = ``softmax(logits)[0, 1]`` (config id2label: 0 = Human, 1 = ChatGPT).
"""

from __future__ import annotations

import logging

from .base import batched_windowed_max, clamp01

logger = logging.getLogger(__name__)

_MODEL_ID = "Hello-SimpleAI/chatgpt-detector-roberta"


class HC3RobertaDetector:
    name = "hc3_roberta"
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

        if HC3RobertaDetector._model is None:
            HC3RobertaDetector._tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
            HC3RobertaDetector._model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID).eval()
        return HC3RobertaDetector._tokenizer, HC3RobertaDetector._model

    def _score_batch(self, windows: list[str]) -> list[float | None]:
        """P(AI) per window from ONE batched forward.

        Windows are tokenised together with per-window truncation at 512 tokens
        (identical to the single-window path), then padded to the longest in the
        batch. With the attention mask, every sample's logits are the same as a
        single-sample forward — no cross-sample interaction — so each window's
        P(AI) is unchanged and the ensemble ``max`` sees the same candidates.
        """
        import torch
        import torch.nn.functional as F

        tok, model = self._load()
        enc = tok(windows, return_tensors="pt", truncation=True, max_length=512,
                  padding="longest")
        ids, mask = enc["input_ids"], enc["attention_mask"]
        with torch.no_grad():
            probs = F.softmax(model(ids, attention_mask=mask).logits, dim=-1)[:, 1]
        return [float(p) for p in probs]

    def score(self, text: str) -> float | None:
        if HC3RobertaDetector._dead:
            return None
        if not text.strip():
            return None
        try:
            import torch  # noqa: F401
            import torch.nn.functional as F  # noqa: F401

            self._load()
        except Exception as exc:
            # Disable + EXCLUDE (never a fake neutral 0.5 that would pin the ensemble max).
            HC3RobertaDetector._dead = True
            if not HC3RobertaDetector._warned:
                logger.warning(
                    "hc3_roberta failed to load and was EXCLUDED from the ensemble "
                    "(%s: %s). Often a NumPy 2.x / torch mismatch - see README troubleshooting.",
                    type(exc).__name__, str(exc)[:140],
                )
                HC3RobertaDetector._warned = True
            raise
        # Whitespace is normalised first. This model is the one that learned HC3's space-before-
        # punctuation artefact as a proxy for "human" — see `normalise_whitespace`. Without this,
        # a space before each period takes AUROC on RAID from 0.9871 to 0.1571: not blinded,
        # inverted. On clean text the normalisation is a no-op and the score is unchanged.
        # Windowed: truncation at 512 tokens made everything past ~380 words invisible.
        p_ai = batched_windowed_max(text, self._score_batch)
        return None if p_ai is None else clamp01(float(p_ai))
