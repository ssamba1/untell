"""Shared base-model loader — full precision (string passthrough) or 4-bit QLoRA.

4-bit (QLoRA) lets a 3B model train on a free 16GB T4 (Colab/Kaggle). When off, returns the model id
string so trl loads it itself (and this module needs no GPU/torch — testable).

Compatible with peft>=0.14 (``prepare_model_for_kbit_training`` was removed/deprecated in newer
versions — modern transformers applies grad checkpointing automatically from the quantization config).
"""

from __future__ import annotations


def load_model(model_id: str, load_4bit: bool = False):
    if not load_4bit:
        return model_id  # trl/transformers loads the string itself

    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb, device_map="auto"
    )
    # prepare_model_for_kbit_training was removed in peft>=0.14; the quantization config
    # already sets up the model for k-bit training in modern transformers. Apply manual
    # grad checkpointing if available for memory savings during training.
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    return model
