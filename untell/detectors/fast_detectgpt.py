"""Fast-DetectGPT adapter (full tier, optional).

Implements the Fast-DetectGPT conditional-probability-curvature statistic
(github: baoguangsheng/fast-detect-gpt) with a single scoring model (GPT-Neo by default).
Zero-shot — no trained classifier head — and a strong proxy, but slower than the supervised
detectors. Guarded: unavailable unless ``transformers``+``torch`` import.

The raw curvature is unbounded; we squash it through a logistic with literature-typical
calibration constants to land a probability in [0, 1].
"""

from __future__ import annotations

import logging
import math

from .base import clamp01, windowed_max

logger = logging.getLogger(__name__)

_SCORING_MODEL = "EleutherAI/gpt-neo-125m"
# Logistic calibration. The inherited constants (_CAL_MID = 1.0, _CAL_SCALE = 1.2) assumed a
# curvature that is ~N(0,1) for human text and shifted positive for AI. MEASURED with this scoring
# model on paragraph-length text, the discrepancy actually lands in roughly [-0.20, 0.38] — so a
# midpoint of 1.0 sat far outside the entire observed range and squashed EVERY input to ~0.30,
# regardless of content. The detector was emitting a near-constant and contributing no signal to the
# ensemble (which is why it appeared to be an "immovable" 0.31 -> 0.28 wall in the ceiling
# measurements: it never moved because it never responded to anything).
#
# Re-centred a second time, and this is the important one. The previous constants were fitted on
# n=10 and placed the midpoint at the HUMAN mean rather than between the classes, so human prose
# squashed to ~0.5 — above the 0.30 default threshold. Because the ensemble aggregates with `max`,
# this one detector decided the full tier's verdict: it told 95% of human writers their own text
# was machine-written, and the loop then rewrote it, spending meaning-similarity for nothing.
#
# MEASURED on HC3, 40 pairs to fit and 60 unseen pairs to check (the discrepancy is per window;
# windowed_max takes the MAX, so the fit is against the per-document max, not the mean):
#
#     per-document max discrepancy   human  mean -0.023, range [-0.171, +0.167]
#                                    ai     mean +0.265, range [+0.162, +0.430]
#
# The classes separate at roughly +0.16, which is where the midpoint belongs.
#
#     constants           fit FPR/TPR      held-out FPR/TPR    held-out AUROC
#     MID -0.03 SC 0.12   92% / 100%       88% / 100%          0.996
#     MID +0.20 SC 0.08    8% / 100%        2% /  97%          0.996
#
# AUROC is identical either way — the detector always separated the classes, it was only reporting
# them on the wrong scale. Three points of true-positive rate for eighty-six points of false-positive
# rate is the right trade for a tool whose worst failure is accusing a human of writing with AI.
# The scale is deliberately not the sharpest option the grid offered (0.02 scored marginally better
# on the fit set): the loop drives this value down and needs a graded response, not a step.
_CAL_MID = 0.20
_CAL_SCALE = 0.08


class FastDetectGPTDetector:
    name = "fast_detectgpt"
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
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if FastDetectGPTDetector._model is None:
            FastDetectGPTDetector._tokenizer = AutoTokenizer.from_pretrained(_SCORING_MODEL)
            FastDetectGPTDetector._model = AutoModelForCausalLM.from_pretrained(_SCORING_MODEL).eval()
        return FastDetectGPTDetector._tokenizer, FastDetectGPTDetector._model

    def score(self, text: str) -> float | None:
        if FastDetectGPTDetector._dead:
            return None
        if not text.strip():
            return None
        try:
            import torch

            tok, model = self._load()
        except Exception as exc:
            FastDetectGPTDetector._dead = True
            if not FastDetectGPTDetector._warned:
                logger.warning(
                    "fast_detectgpt failed to load and was EXCLUDED from the ensemble "
                    "(%s: %s). Often a NumPy 2.x / torch mismatch - see README troubleshooting.",
                    type(exc).__name__, str(exc)[:140],
                )
                FastDetectGPTDetector._warned = True
            raise
        def _one(window: str) -> float | None:
            enc = tok(window, return_tensors="pt", truncation=True, max_length=512)
            ids = enc["input_ids"]
            if ids.shape[1] < 2:
                return None
            with torch.no_grad():
                logits = model(ids).logits[:, :-1, :]
                labels = ids[:, 1:]
                lprobs = torch.log_softmax(logits, dim=-1)
                # Log-prob the model assigns to the *actual* next tokens.
                actual = lprobs.gather(-1, labels.unsqueeze(-1)).squeeze(-1)
                # Expected log-prob and its variance under the model's own distribution.
                probs = lprobs.exp()
                mean_ref = (probs * lprobs).sum(-1)
                var_ref = (probs * (lprobs - mean_ref.unsqueeze(-1)) ** 2).sum(-1)
                # Conditional-probability curvature (Fast-DetectGPT discrepancy).
                discrepancy = ((actual - mean_ref) / torch.sqrt(var_ref + 1e-8)).mean().item()
            # Higher discrepancy => more AI-like; squash to [0, 1].
            return 1.0 / (1.0 + math.exp(-(discrepancy - _CAL_MID) / _CAL_SCALE))

        # Windowed: truncation at 512 tokens made everything past ~380 words invisible.
        score = windowed_max(text, _one)
        return None if score is None else clamp01(score)
