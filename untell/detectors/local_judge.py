"""Local LLaMA-as-judge detector — any open-source model as an AI detector, no API key.

Uses a HuggingFace causal LM (LLaMA, Mistral, Qwen, etc.) to rate text AI-likelihood
with the same judge prompt as the hosted ``LLMJudgeDetector``. No API cost, no rate
limits — just a local model and a GPU (or CPU, slowly).

Two tiers:

* ``full`` — ``Qwen/Qwen2.5-1.5B-Instruct`` (~3 GB, runs on CPU in ~seconds).
* ``heavy`` — ``Qwen/Qwen2.5-7B-Instruct`` (~14 GB, GPU recommended).

Select with the ``UNTELL_JUDGE_MODEL`` env var, or pass ``model_id`` at construction.

Usage::

    from untell.detectors.local_judge import LocalJudgeDetector

    d = LocalJudgeDetector()
    print(d.score("Furthermore, we leverage robust solutions."))  # 0.0-1.0
"""

from __future__ import annotations

import os
import re

from .base import clamp01

_NUM = re.compile(r"\d*\.\d+|\d+")

_JUDGE_PROMPT = (
    "You are an expert AI-text detector. Rate how likely the text below was written by an AI language "
    "model, from 0.00 (clearly a human wrote it) to 1.00 (clearly AI-generated). Weigh the overall "
    "read, not any single word, and consider the known AI tells: em-dashes; AI vocabulary (delve, "
    "leverage, robust, seamless, tapestry, testament, pivotal, underscore, multifaceted, meticulous); "
    "formulaic transitions (Moreover, Furthermore, Overall, In conclusion); rule-of-three / tricolons; "
    "negated contrast (\"not X, it's Y\"); participial trailers (\"..., underscoring its importance\"); "
    "inflated copula (serves as, boasts); vague attribution (\"studies show\"); uniform sentence length "
    "(low burstiness); promotional register; sycophancy; over-structured markdown. "
    "Ignore opaque sentinel tokens like ⟦HZ0003⟧ — treat them as neutral placeholders. "
    "Respond with ONLY the number, e.g. 0.73"
)

LIGHT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HEAVY_MODEL = "Qwen/Qwen2.5-7B-Instruct"
_DEFAULT_MODEL = os.environ.get("UNTELL_JUDGE_MODEL") or LIGHT_MODEL


class LocalJudgeDetector:
    """Score text AI-likelihood using a local LLM as the judge.

    Loads the model lazily on the first ``score()`` call. The model stays loaded
    in memory for subsequent calls (class-level cache).

    Args:
        model_id: HuggingFace model ID. Defaults to ``$UNTELL_JUDGE_MODEL`` or
                  ``Qwen/Qwen2.5-1.5B-Instruct``.
        device: Torch device (``"auto"``, ``"cuda"``, ``"cpu"``). Defaults to CUDA if available.
    """

    name = "local_judge"
    tier = "full"  # light model runs on CPU; 7B is "heavy" territory

    _model = None
    _tokenizer = None

    def __init__(self, model_id: str | None = None, device: str | None = None):
        self.model_id = model_id or _DEFAULT_MODEL
        self._device_override = device
        # Heuristic tier: heavy models (7B+) are "heavy" tier; small ones are "full".
        if "7b" in self.model_id.lower() or "8b" in self.model_id.lower() or "13b" in self.model_id.lower():
            self.tier = "heavy"

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if LocalJudgeDetector._model is None:
            tok = AutoTokenizer.from_pretrained(self.model_id)
            if tok.pad_token_id is None:
                tok.pad_token = tok.eos_token
            device = self._device_override or ("cuda" if torch.cuda.is_available() else "cpu")
            # Load, then `.to(device)` — NOT `device_map=`. Passing device_map at all routes the
            # load through `accelerate`, which is not a declared dependency, so every score() call
            # died with "Using a `device_map` ... requires `accelerate`" even though available()
            # had just reported True. `.to()` places the model identically for a single device.
            model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                dtype=torch.bfloat16 if device != "cpu" else torch.float32,
            ).to(device).eval()
            LocalJudgeDetector._tokenizer = tok
            LocalJudgeDetector._model = model
        return LocalJudgeDetector._tokenizer, LocalJudgeDetector._model

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        tok, model = self._load()
        prompt = f"{_JUDGE_PROMPT}\n\n--- TEXT ---\n{text}\n\n--- RATING ---"
        messages = [{"role": "user", "content": prompt}]
        # Apply chat template so instruct models respond properly.
        input_text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        device = next(model.parameters()).device
        inputs = tok(input_text, return_tensors="pt", truncation=True, max_length=2048).to(device)
        import torch

        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=16,
                do_sample=False,
                temperature=None,  # greedy
                top_p=None,
                pad_token_id=tok.pad_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[1]:]
        reply = tok.decode(gen, skip_special_tokens=True).strip()
        m = _NUM.search(reply or "")
        if not m:
            return None
        val = float(m.group(0))
        if val >= 2.0:
            val /= 100.0
        return clamp01(val)
