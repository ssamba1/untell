"""Local LoRA-policy rewriter — the RL-trained moat as a rewriter backend.

Loads the GRPO/LoRA adapter produced by ``training/rl_humanizer.py`` (path in ``UNTELL_POLICY_DIR``)
on top of its base instruct model and rewrites in a SINGLE forward pass — the whole point of the moat:
no API key, no inference loop, runs local (GPU, or CPU slowly). Heavy deps (torch/transformers/peft)
are imported lazily so this module stays importable on a no-GPU box; ``available()`` just returns
False there, exactly like the hosted (Anthropic/OpenAI) rewriters.

Wire-up: set ``UNTELL_POLICY_DIR=out/rl-humanizer`` and ``get_rewriter()`` returns this in preference
to the API rewriters, so the existing loop / eval harness uses the trained policy with no other change.

Env:
    UNTELL_POLICY_DIR    adapter dir (the trained LoRA). Required for ``available()``.
    UNTELL_POLICY_BASE   base model id (default ``Qwen/Qwen2.5-3B-Instruct``; must match training).
    UNTELL_POLICY_4BIT   "1" to load the base in 4-bit (QLoRA inference, fits a 16GB GPU).
    UNTELL_POLICY_MAXTOK max new tokens (default 512).
"""

from __future__ import annotations

import os
from typing import Any

# The single source of truth for the training prompt: rl_humanizer, dpo_humanizer and distill all
# import it from here. It used to be re-typed as a literal in two of them, so a change here would
# have left DPO and the distilled SFT data tuned on one instruction while inference used another —
# with nothing to detect the drift but the quality of the output.
#
# The policy was RL-trained on THIS exact instruction, so feeding it the loop's richer rubric prompt
# (rewriter/prompts.py) would be out-of-distribution. The moat is single-pass by design — the
# per-iteration detector feedback the API rewriter consumes does not apply here; we just (re)sample
# from the trained prompt.
_TRAIN_PROMPT = (
    "Rewrite the following text so it reads as natural human writing while preserving its exact "
    "meaning:\n\n{text}"
)
DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"


class LocalPolicyRewriter:
    """Rewriter backed by a locally-loaded base model + trained LoRA adapter.

    Set ``use_adapter=False`` to load the *base* model with no adapter — used by the eval harness to
    A/B the trained policy against the untuned base on identical inputs.
    """

    name = "local-policy"

    def __init__(
        self,
        adapter_dir: str | None = None,
        base_model: str | None = None,
        *,
        use_adapter: bool = True,
    ):
        self.adapter_dir = adapter_dir or os.environ.get("UNTELL_POLICY_DIR", "")
        self.base_model = base_model or os.environ.get("UNTELL_POLICY_BASE", DEFAULT_BASE)
        self.use_adapter = use_adapter
        self._model = None
        self._tok = None
        if not use_adapter:
            self.name = "base-model"

    def available(self) -> bool:
        """True when the adapter dir exists (when using one) and torch/transformers/peft import."""
        if self.use_adapter and (not self.adapter_dir or not os.path.isdir(self.adapter_dir)):
            return False
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            if self.use_adapter:  # peft is only needed to load the adapter; base-only eval doesn't use it
                import peft  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kw: dict[str, Any] = {}
        if os.environ.get("UNTELL_POLICY_4BIT") == "1":
            if not torch.cuda.is_available():
                # bitsandbytes 4-bit needs CUDA; without it from_pretrained dies with an opaque BNB
                # error. Fail with a clear message instead.
                raise RuntimeError(
                    "UNTELL_POLICY_4BIT=1 requires a CUDA GPU (bitsandbytes 4-bit). "
                    "Unset it to load on CPU."
                )
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
            )
        else:
            kw["dtype"] = "auto"  # torch_dtype= is deprecated in transformers 5.x
        if torch.cuda.is_available():
            # `device_map="auto"` is the right call for a policy model that may not fit one GPU —
            # but it hard-requires `accelerate`, which transformers does NOT pull in. Without it
            # from_pretrained dies with "Using a `device_map` ... requires `accelerate`", the same
            # opaque failure that made local_judge dead on arrival. Fail with a clear message
            # instead, exactly as the 4-bit branch above already does for bitsandbytes.
            import importlib.util

            if importlib.util.find_spec("accelerate") is None:
                raise RuntimeError(
                    "loading the policy model on a GPU needs `accelerate` (device_map='auto'); "
                    "install it with `pip install accelerate`, or run on CPU."
                )
            kw["device_map"] = "auto"

        model = AutoModelForCausalLM.from_pretrained(self.base_model, **kw)
        if self.use_adapter:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, self.adapter_dir)
        model.eval()
        tok = AutoTokenizer.from_pretrained(self.base_model)
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token
        self._model, self._tok = model, tok

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        """Single-pass rewrite. ``score_result``/``threshold`` are accepted for the ``Rewriter``
        protocol but unused — the policy was trained to untell from the bare prompt, not from
        detector feedback."""
        import torch

        self._load()
        messages = [{"role": "user", "content": _TRAIN_PROMPT.format(text=text)}]
        # UNTELL_POLICY_NO_SYSTEM=1 suppresses the tokenizer's default system turn (e.g. Qwen's
        # "You are a helpful assistant") — some base models read as more human without it. Not every
        # template accepts the kwarg, so fall back to the plain call on any failure.
        tmpl_kw = {"tokenize": False, "add_generation_prompt": True}
        if os.environ.get("UNTELL_POLICY_NO_SYSTEM") == "1":
            try:
                prompt = self._tok.apply_chat_template(messages, system_prompt="", **tmpl_kw)
            except (TypeError, ValueError):
                prompt = self._tok.apply_chat_template(messages, **tmpl_kw)
        else:
            prompt = self._tok.apply_chat_template(messages, **tmpl_kw)
        # Use a real parameter's device, not self._model.device: when accelerate dispatches the model
        # across devices (device_map="auto" with >1 GPU or CPU offload) there is no single .device.
        device = next(self._model.parameters()).device
        inputs = self._tok(prompt, return_tensors="pt", truncation=True, max_length=2048).to(device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=int(os.environ.get("UNTELL_POLICY_MAXTOK", "512")),
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=self._tok.pad_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[1] :]
        return self._tok.decode(gen, skip_special_tokens=True).strip()
