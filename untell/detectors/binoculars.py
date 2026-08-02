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

from .base import clamp01, windowed_max

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
            # `.to(dev)`, NOT `device_map=dev`: device_map hard-requires `accelerate`, which is not
            # a runtime dependency, so available() would report True and every score() call would
            # raise. For a single device the placement is identical. This tier is GPU-gated and so
            # never runs in CI — the guard in tests/test_detector_contract.py is what catches it.
            BinocularsDetector._observer = AutoModelForCausalLM.from_pretrained(
                _OBSERVER, dtype=torch.bfloat16
            ).to(dev).eval()
            BinocularsDetector._performer = AutoModelForCausalLM.from_pretrained(
                _PERFORMER, dtype=torch.bfloat16
            ).to(dev).eval()
        return BinocularsDetector._tokenizer, BinocularsDetector._observer, BinocularsDetector._performer

    def score(self, text: str) -> float | None:
        # None == "no signal" (empty / too short / unavailable): excluded from the aggregate
        # rather than folded in as a fake neutral 0.5.
        if not self.available() or not text.strip():
            return None
        import torch

        tok, observer, performer = self._load()
        device = next(observer.parameters()).device
        # Windowed, like every other supervised adapter. `truncation=True, max_length=512` reads
        # roughly the first 380 words and silently discards the rest, so a document with a long
        # human preamble scored as human regardless of what followed it. RADAR had the identical
        # gap and was measured missing a 207-word AI block at the end of a 2887-word document
        # (0.113 windowed-elsewhere vs 0.999); both adapters sit outside the default tiers, which
        # is why they were left behind when the others were fixed.
        return windowed_max(text, lambda w: self._score_window(w, tok, observer, performer, device))

    def _score_window(self, text: str, tok, observer, performer, device) -> float | None:
        import torch

        enc = tok(text, return_tensors="pt", truncation=True, max_length=512).to(device)
        ids = enc["input_ids"]
        if ids.shape[1] < 2:
            return None
        labels = ids[:, 1:]
        with torch.no_grad():
            obs_logits = observer(ids).logits[:, :-1, :].float()
            perf_logits = performer(ids).logits[:, :-1, :].float()

            obs_lprobs = torch.log_softmax(obs_logits, dim=-1)
            perf_lprobs = torch.log_softmax(perf_logits, dim=-1)
            # log-perplexity: the *performer* predicting the actual next tokens.
            log_ppl = -perf_lprobs.gather(-1, labels.unsqueeze(-1)).squeeze(-1).mean()
            # cross-perplexity: cross-entropy H(observer distribution, performer log-probs) =
            # -sum_v softmax(observer)_v * log_softmax(performer)_v, matching the reference
            # implementation (ahans30/Binoculars). Heavy/GPU tier; not exercised on CPU CI.
            x_ppl = -(obs_lprobs.exp() * perf_lprobs).sum(-1).mean()

        binoculars = float(log_ppl / (x_ppl + 1e-8))
        # Lower Binoculars score => more AI-like; invert through the logistic (calibration heuristic).
        return clamp01(1.0 / (1.0 + math.exp((binoculars - _CAL_MID) / _CAL_SCALE)))
