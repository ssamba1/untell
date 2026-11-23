"""Score with any Hugging Face text classifier, as its users deploy it: ``hf:<model id>``.

The open detectors people actually install are not untell's five. This scorer runs a Hub model
the way its model card says to — the raw text, truncated at the model's limit, no untell
normalisation — so the same report cards, stability test and trailing-space test can audit it.

Which label means "AI" is not standardised, and guessing it wrong inverts every result, so it is
taken from a curated registry (each entry checked against the model's config or card), or given
explicitly as ``hf:<model>#<label name or index>``. A model with neither is refused.

Nothing here runs code from a model repository (``trust_remote_code`` is never set). Desklib's
detector ships a custom class; its documented architecture — DeBERTa-v3-large, mean pooling over
the last hidden state, one linear logit, sigmoid — is implemented here from the model card instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from .scorers import Scorer, Verdict

__all__ = ["KNOWN", "HFModel", "hf_scorer"]


@dataclass(frozen=True)
class HFModel:
    ai_index: int
    arch: str = "seqcls"  # "seqcls" | "desklib"
    max_length: int = 512
    note: str = ""


# Checked 2026-11-22 against each model's config.json id2label or its model card.
KNOWN: dict[str, HFModel] = {
    "desklib/ai-text-detector-v1.01": HFModel(1, "desklib", 768,
                                              "card: sigmoid of one logit = P(AI); max_length 768"),
    "fakespot-ai/roberta-base-ai-text-detection-v1": HFModel(1, note="config: 0 Human, 1 AI"),
    "rasbt/ai-text-detector-modernbert": HFModel(1, note="config: 0 HUMAN, 1 AI"),
    "PirateXX/AI-Content-Detector": HFModel(0, note="card: Label_0 represents Fake"),
    "openai-community/roberta-large-openai-detector": HFModel(
        0, note="same convention as roberta-base-openai-detector, whose config says 0 Fake"),
    "openai-community/roberta-base-openai-detector": HFModel(0, note="config: 0 Fake, 1 Real"),
    "Hello-SimpleAI/chatgpt-detector-roberta": HFModel(1, note="config: 0 Human, 1 ChatGPT"),
}


def _parse(spec: str) -> tuple[str, HFModel]:
    model_id, _, label = spec.partition("#")
    known = KNOWN.get(model_id)
    if label:
        idx = int(label) if label.isdigit() else None
        if idx is None:
            from transformers import AutoConfig

            id2label = AutoConfig.from_pretrained(model_id).id2label or {}
            matches = [int(k) for k, v in id2label.items() if str(v).lower() == label.lower()]
            if not matches:
                raise ValueError(f"{model_id} has no label {label!r}; labels: {id2label}")
            idx = matches[0]
        return model_id, HFModel(idx, known.arch if known else "seqcls",
                                 known.max_length if known else 512)
    if known is None:
        raise ValueError(
            f"which label of {model_id} means AI is not on file; pass it explicitly as "
            f"hf:{model_id}#<label name or index> after checking the model card"
        )
    return model_id, known


class _Loaded:
    def __init__(self, model_id: str, spec: HFModel):
        import torch
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

        self.torch, self.spec = torch, spec
        self.tok = AutoTokenizer.from_pretrained(model_id)
        if spec.arch == "desklib":
            from huggingface_hub import hf_hub_download
            from safetensors.torch import load_file
            from transformers import AutoConfig

            cfg = AutoConfig.from_pretrained(model_id)
            self.backbone = AutoModel.from_config(cfg)
            self.head = torch.nn.Linear(cfg.hidden_size, 1)
            state = load_file(hf_hub_download(model_id, "model.safetensors"))
            self.backbone.load_state_dict(
                {k[len("model."):]: v for k, v in state.items() if k.startswith("model.")})
            self.head.load_state_dict(
                {k[len("classifier."):]: v for k, v in state.items() if k.startswith("classifier.")})
            self.backbone.float().eval()
            self.head.float().eval()
        else:
            # Always compute in float32. transformers 5 loads a model in the dtype its config
            # declares, and rasbt/ai-text-detector-modernbert ships bfloat16, whose 8-bit mantissa
            # rounds every probability to a multiple of 1/256: MEASURED, 1,546 documents produced
            # 340 distinct scores, and more than 5% of known-human text scored exactly 1.0. That is
            # the storage format talking, not the detector — transformers 4 upcast by default.
            self.model = AutoModelForSequenceClassification.from_pretrained(model_id).float()
            self.model.eval()

    def score(self, text: str) -> float:
        torch = self.torch
        enc = self.tok(text, truncation=True, max_length=self.spec.max_length, return_tensors="pt")
        with torch.no_grad():
            if self.spec.arch == "desklib":
                hidden = self.backbone(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                return float(torch.sigmoid(self.head(pooled)).item())
            probs = torch.softmax(self.model(**enc).logits, dim=-1)[0]
            return float(probs[self.spec.ai_index].item())


_CACHE: dict[str, _Loaded] = {}


def hf_scorer(spec: str, threshold: float) -> Scorer:
    """Build a scorer from ``<model id>`` or ``<model id>#<label>`` (without the ``hf:`` prefix)."""
    model_id, info = _parse(spec)

    def run(text: str, key: str | None) -> Verdict:
        if model_id not in _CACHE:
            _CACHE[model_id] = _Loaded(model_id, info)
        s = _CACHE[model_id].score(text)
        return Verdict(s, s >= threshold)

    return Scorer(f"hf:{model_id}", "detector", threshold, run, None)
