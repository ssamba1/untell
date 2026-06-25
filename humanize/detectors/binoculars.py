"""Binoculars detector adapter (heavy tier, GPU).

Implements the Binoculars score (github: ahans30/Binoculars, BSD-3): the ratio of a text's
perplexity under an *observer* LLM to its cross-perplexity against a *performer* LLM. The
reference implementation uses two Falcon-7B models, so this tier expects a GPU and the
``[heavy]`` extras. The strongest training-free proxy in the ensemble.

Guarded: unavailable unless ``transformers``+``torch`` import. Model loading is lazy so merely
listing detectors never pulls 14B params.
"""

from __future__ import annotations

import math

from .base import clamp01

_OBSERVER = "tiiuae/falcon-7b"
_PERFORMER = "tiiuae/falcon-7b-instruct"
# Binoculars threshold ~0.9 (lower score => more AI-like). Logistic-calibrate around it.
_CAL_MID = 0.9
_CAL_SCALE = 0.08


class BinocularsDetector:
    name = "binoculars"
    tier = "heavy"

    _observer = None
    _performer = None
    _tokenizer = None

    def available(self) -> bool:
        try:
            import torch
            import transformers  # noqa: F401
        except Exception:
            return False
        # Heavy tier is GPU-bound; without CUDA the two Falcon-7B models are impractical.
        try:
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if BinocularsDetector._observer is None:
            BinocularsDetector._tokenizer = AutoTokenizer.from_pretrained(_OBSERVER)
            dev = "cuda"
            BinocularsDetector._observer = AutoModelForCausalLM.from_pretrained(
                _OBSERVER, torch_dtype=torch.bfloat16, device_map=dev
            ).eval()
            BinocularsDetector._performer = AutoModelForCausalLM.from_pretrained(
                _PERFORMER, torch_dtype=torch.bfloat16, device_map=dev
            ).eval()
        return BinocularsDetector._tokenizer, BinocularsDetector._observer, BinocularsDetector._performer

    def score(self, text: str) -> float:
        if not self.available() or not text.strip():
            return 0.5
        import torch

        tok, observer, performer = self._load()
        enc = tok(text, return_tensors="pt", truncation=True, max_length=512).to("cuda")
        ids = enc["input_ids"]
        if ids.shape[1] < 2:
            return 0.5
        labels = ids[:, 1:]
        with torch.no_grad():
            obs_logits = observer(ids).logits[:, :-1, :].float()
            perf_logits = performer(ids).logits[:, :-1, :].float()

            obs_lprobs = torch.log_softmax(obs_logits, dim=-1)
            log_ppl = -obs_lprobs.gather(-1, labels.unsqueeze(-1)).squeeze(-1).mean()

            # Cross-entropy of performer's predictions against observer's distribution.
            perf_probs = torch.softmax(perf_logits, dim=-1)
            x_ppl = -(perf_probs * obs_lprobs).sum(-1).mean()

        binoculars = float(log_ppl / (x_ppl + 1e-8))
        # Lower Binoculars score => more AI-like; invert through the logistic.
        return clamp01(1.0 / (1.0 + math.exp((binoculars - _CAL_MID) / _CAL_SCALE)))
