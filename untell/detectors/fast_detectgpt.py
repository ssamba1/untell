"""Fast-DetectGPT adapter (full tier, optional).

Implements the Fast-DetectGPT conditional-probability-curvature statistic
(github: baoguangsheng/fast-detect-gpt) with a single scoring model (GPT-Neo by default).
Zero-shot — no trained classifier head — and a strong proxy, but slower than the supervised
detectors. Guarded: unavailable unless ``transformers``+``torch`` import.

The raw curvature is unbounded; we squash it through a logistic with literature-typical
calibration constants to land a probability in [0, 1].
"""

from __future__ import annotations

import math

from .base import clamp01

_SCORING_MODEL = "EleutherAI/gpt-neo-125m"
# Logistic calibration: curvature ~ N(0,1)-ish for human, shifted positive for AI.
_CAL_MID = 1.0
_CAL_SCALE = 1.2


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
            raise RuntimeError("fast_detectgpt disabled after a prior load failure")
        if not text.strip():
            return None
        try:
            import torch

            tok, model = self._load()
        except Exception as exc:
            FastDetectGPTDetector._dead = True
            if not FastDetectGPTDetector._warned:
                import sys

                print(
                    f"[untell] fast_detectgpt failed to load and was EXCLUDED from the ensemble "
                    f"({type(exc).__name__}: {str(exc)[:140]}). "
                    "Often a NumPy 2.x / torch mismatch — see README troubleshooting.",
                    file=sys.stderr,
                )
                FastDetectGPTDetector._warned = True
            raise
        enc = tok(text, return_tensors="pt", truncation=True, max_length=512)
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
        return clamp01(1.0 / (1.0 + math.exp(-(discrepancy - _CAL_MID) / _CAL_SCALE)))
