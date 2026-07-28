"""RADAR detector adapter (full tier, opt-in).

RADAR (IBM, NeurIPS 2023, arXiv 2307.03838) is a RoBERTa-large detector **adversarially trained
against a paraphraser**, so it is notably robust to paraphrase/humanizer attacks — the hardest open
detector to fool, which makes it the most valuable target to optimize our loop against.

⚠️ LICENSE: ``TrustSafeAI/RADAR-Vicuna-7B`` inherits Vicuna's **NON-COMMERCIAL** license. We do not
redistribute the weights — you download them yourself, and only if you opt in. Because of the
license, RADAR is **opt-in**: set ``UNTELL_ENABLE_RADAR=1`` to include it. Use for research /
evaluation, not in a commercial product path.

The detector is RoBERTa-large (~355M params, CPU-feasible but slow); the "7B" in the name refers to
the Vicuna paraphraser it was trained against, not the detector. P(AI) = ``softmax(logits)[:, 0]``
(index 0 = AI-generated; confirmed verbatim in the IBM RADAR notebook + HF Space app.py).
"""

from __future__ import annotations

import logging
import os

from .base import clamp01

logger = logging.getLogger(__name__)

_MODEL_ID = "TrustSafeAI/RADAR-Vicuna-7B"


class RadarDetector:
    name = "radar"
    tier = "full"

    _model = None
    _tokenizer = None
    _warned = False

    def available(self) -> bool:
        if not (os.environ.get("UNTELL_ENABLE_RADAR") or os.environ.get("HUMANIZE_ENABLE_RADAR")):
            return False  # opt-in only (non-commercial license)
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if RadarDetector._model is None:
            RadarDetector._tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
            RadarDetector._model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID).eval()
        return RadarDetector._tokenizer, RadarDetector._model

    def score(self, text: str) -> float | None:
        # None == "no signal" (empty / unavailable): excluded from the aggregate rather than
        # folded in as a fake neutral 0.5. A load/scoring failure propagates so score_text records
        # it in failed_detectors (matching the other supervised adapters' contract).
        if not self.available() or not text.strip():
            return None
        if not RadarDetector._warned:
            logger.info(
                "RADAR enabled - TrustSafeAI/RADAR-Vicuna-7B is NON-COMMERCIAL licensed; "
                "research/evaluation use only."
            )
            RadarDetector._warned = True
        import torch
        import torch.nn.functional as F

        tok, model = self._load()
        inputs = tok(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            p_ai = F.softmax(model(**inputs).logits, dim=-1)[0, 0].item()  # index 0 = AI
        return clamp01(float(p_ai))
