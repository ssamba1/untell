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

import logging
import os
import re

from .base import clamp01
from .llm_judge import _JUDGE_PROMPT

logger = logging.getLogger(__name__)

_NUM = re.compile(r"\d*\.\d+|\d+")

# Two model sizes this prompt has been used with. `HEAVY_MODEL` is not a default and never has
# been — it is the value to put in `$UNTELL_JUDGE_MODEL` if you have the VRAM and want the larger
# judge. It sat here unreferenced by anything, which makes a constant indistinguishable from an
# abandoned one; `suggested_models()` below exists so the suggestion is reachable rather than
# implied, and `untell-score --help` and the README both point at it.
LIGHT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HEAVY_MODEL = "Qwen/Qwen2.5-7B-Instruct"
_DEFAULT_MODEL = os.environ.get("UNTELL_JUDGE_MODEL") or LIGHT_MODEL


def suggested_models() -> dict[str, str]:
    """Model IDs known to work with this judge prompt, smallest first.

    The judge already sits in the **heavy** tier at the light model: measured at 3.7s per call
    against 0.03-0.06s for every other detector, for AUROC 0.514 on labelled pairs. The 7B is
    slower again and has not been measured here, so it is offered as an option rather than a
    recommendation — if you run it, measure it before believing it.
    """
    return {"light": LIGHT_MODEL, "heavy": HEAVY_MODEL}


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
    # HEAVY, including the "light" 1.5B model. It was tier "full" — the documented default — but had
    # been raising on every call, so nothing noticed. Once it actually ran, MEASURED on CPU against
    # the rest of the full tier on the same paragraph:
    #
    #   perplexity_burstiness 0.06s   roberta_openai 0.03s   hc3_roberta 0.04s
    #   fast_detectgpt        0.06s   local_judge    3.71s
    #
    # 60-120x the cost of any other detector, and inside a best-of-N loop that is per candidate per
    # iteration. What it buys, measured over 40 labelled HC3 pairs (`untell-detector-audit --pairs
    # 40`), is AUROC 0.514 — a coin flip, mean 0.90 on human text and 0.95 on AI: a 1.5B model asked
    # to judge answers "AI" to almost anything. Paying seconds per candidate for that would make the
    # default tier an order of magnitude slower for no signal, so it belongs behind --tier heavy.
    tier = "heavy"

    _model = None
    _tokenizer = None
    _dead = False  # set once a load fails so we never re-attempt the heavy download per call
    # Tracks which model_id was loaded into the class-level cache. A second instance constructed
    # with a DIFFERENT model_id reuses the first-loaded model and logs a warning — the class-level
    # cache holds one model per process. Set UNTELL_JUDGE_MODEL before the first score() call.
    _loaded_model_id: str | None = None

    def __init__(self, model_id: str | None = None, device: str | None = None):
        self.model_id = model_id or _DEFAULT_MODEL
        self._device_override = device
        # Every size is "heavy" (see the class comment) — a generation per candidate is heavy-tier
        # work whether the model has 1.5B parameters or 7B.

    def available(self) -> bool:
        # OPT-IN ONLY. This detector does not discriminate and it wrecks the tier it sits in.
        # MEASURED on 20 labelled HC3 pairs, at the default 0.30 threshold:
        #
        #     local_judge alone   human mean 0.853, flags 89% of HUMAN documents   AUROC 0.591
        #     heavy tier          human mean 0.846, FPR 90%
        #     full tier           human mean 0.168, FPR 15%
        #
        # AUROC 0.591 is barely above chance, so it contributes almost no separation — but the
        # ensemble aggregates with `max`, so its near-constant "yes, AI" verdict became the whole
        # heavy tier's answer. The strongest tier was the least trustworthy one: it told 90% of
        # human writers their own text was machine-generated, and the loop would then rewrite it.
        #
        # The failure is inherent to the approach, not a calibration constant: a 1.5B instruct model
        # asked "rate how likely this is AI" answers high almost regardless of input, which is
        # ordinary instruction-following bias, not detection. It was already demoted out of the full
        # tier earlier for scoring at chance; this finishes the job rather than leaving it deciding
        # heavy-tier verdicts.
        #
        # Same opt-in shape as RADAR, so the module stays usable for anyone experimenting with it.
        if not os.environ.get("UNTELL_ENABLE_LOCAL_JUDGE"):
            return False
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
            LocalJudgeDetector._loaded_model_id = self.model_id
        elif LocalJudgeDetector._loaded_model_id != self.model_id:
            # A second instance with a different model_id was constructed after the cache was
            # populated. Warn rather than silently serve wrong weights. Set UNTELL_JUDGE_MODEL
            # before the first score() call to control which model loads.
            logger.warning(
                "LocalJudgeDetector: model_id %r requested but %r is already loaded "
                "(class-level cache holds one model per process). Using the loaded model.",
                self.model_id, LocalJudgeDetector._loaded_model_id,
            )
        return LocalJudgeDetector._tokenizer, LocalJudgeDetector._model

    def score(self, text: str) -> float | None:
        if LocalJudgeDetector._dead:
            return None
        if not self.available() or not text.strip():
            return None
        try:
            tok, model = self._load()
        except Exception as exc:
            LocalJudgeDetector._dead = True
            logger.warning(
                "local_judge failed to load and was EXCLUDED from the ensemble "
                "(%s: %s). Check network access and the HuggingFace cache.",
                type(exc).__name__, str(exc)[:140],
            )
            raise
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
