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

from .base import clamp01, windowed_max

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

        def _one(window: str) -> float:
            inputs = tok(window, return_tensors="pt", truncation=True, max_length=513)
            with torch.no_grad():
                return F.softmax(model(**inputs).logits, dim=-1)[0, 0].item()  # index 0 = AI

        # Windowed, like every other supervised adapter. `truncation=True, max_length=512` reads
        # roughly the first 380 words and silently discards the rest, so a document with a human
        # preamble scored as human no matter what followed. MEASURED on a 2887-word document whose
        # last 207 words were AI: RADAR 0.113 (missed it) against hc3_roberta 0.999 (windowed); on
        # the AI block alone RADAR scores 0.995, so the detector was fine and simply never saw it.
        #
        # This adapter was left behind when the others were fixed — it is opt-in, so it is absent
        # from the default tiers the fix was verified against. It is also the paraphrase-robust one,
        # the hardest to fool and therefore the most valuable to be reading the whole document.
        score = windowed_max(text, _one)
        return None if score is None else clamp01(float(score))
