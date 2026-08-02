"""Free neural paraphraser rewriter — T5 sequence-to-sequence, no API key.

Rule-based transforms (structural/surgical) have a measured ceiling against trained classifiers
(~5-8% AUROC drop vs RoBERTa; the content is the tell). A **neural paraphraser** rewrites at the
sentence level and moves detectors far more — DIPPER-class paraphrasing drove DetectGPT 70%->4.6%
TPR@1%FPR (Krishna et al., NeurIPS 2023). This wraps a free, downloadable T5 paraphrase model
(``humarin/chatgpt_paraphraser_on_T5_base``, ~850MB) as a ``Rewriter`` backend: no key, no GPU
required (CPU works, slowly). Needs ``.[full]`` (torch + transformers); degrades to a safe no-op
when unavailable, exactly like the other optional rewriters.

Sentinel-safe: locked spans (``⟦HZxxxx⟧``) are swapped for ALLCAPS placeholders before paraphrasing
and restored after; any span lost in paraphrase falls back to the input (the loop's own sentinel
check is the second net). Paraphrasing is done per sentence so a dropped span only costs one
sentence, not the whole text.
"""

from __future__ import annotations

from collections import Counter

# Matches the sentinel format lock() emits (4-or-more digits — see preserve.py).
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE
from untell.text_split import split_sentences

_MODEL_ID = "humarin/chatgpt_paraphraser_on_T5_base"


class T5ParaphraseRewriter:
    """Free CPU/GPU neural paraphraser. ``available()`` only when torch+transformers import."""

    name = "t5_paraphrase"
    deterministic = False  # sampled generation varies run to run

    # class-level model cache so the ~850MB model loads once per process
    _tok = None
    _model = None

    def __init__(
        self,
        num_beams: int = 4,
        max_length: int = 128,
        sample: bool = False,
        top_p: float = 0.95,
        temperature: float = 1.2,
    ):
        # ``sample=True`` switches from a single deterministic beam output to nucleus sampling, so
        # repeated calls yield DIVERSE paraphrases. T5-base paraphrase quality is high-variance
        # (measured: it can drive a detector 0.97->0.07 on one draw and 0.02->0.99 on another), so
        # the winning strategy is best-of-N: sample several and let the caller keep the lowest-scoring
        # one. The neural composite drives that selection.
        self.num_beams = num_beams
        self.max_length = max_length
        self.sample = sample
        self.top_p = top_p
        self.temperature = temperature

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        if T5ParaphraseRewriter._model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            T5ParaphraseRewriter._tok = AutoTokenizer.from_pretrained(_MODEL_ID)
            T5ParaphraseRewriter._model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_ID).eval()
        return T5ParaphraseRewriter._tok, T5ParaphraseRewriter._model

    def _paraphrase_one(self, sentence: str) -> str:
        import torch

        tok, model = self._load()
        enc = tok(
            f"paraphrase: {sentence}",
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        )
        gen_kwargs = dict(
            max_length=self.max_length,
            num_return_sequences=1,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
        )
        if self.sample:
            gen_kwargs.update(do_sample=True, top_p=self.top_p, temperature=self.temperature)
        else:
            gen_kwargs.update(num_beams=self.num_beams)
        with torch.no_grad():
            out = model.generate(**enc, **gen_kwargs)
        return tok.decode(out[0], skip_special_tokens=True).strip()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        if not text.strip() or not self.available():
            return text

        # Swap sentinels for ALLCAPS placeholders the model tends to copy verbatim.
        sentinels = list(dict.fromkeys(_SENTINEL_RE.findall(text)))
        placeholders = {f"ZQXMARK{i}ZQX": s for i, s in enumerate(sentinels)}
        swapped = text
        for ph, sent in placeholders.items():
            swapped = swapped.replace(sent, ph)

        out_parts: list[str] = []
        # Abbreviation-aware (untell.text_split): a naive split fed the model a bare "Dr." as a
        # sentence to paraphrase, and a neural paraphraser handed a two-character fragment returns
        # whatever it likes — the abbreviation does not survive.
        for sent in split_sentences(swapped.strip()):
            if not sent.strip():
                continue
            try:
                para = self._paraphrase_one(sent)
            except Exception:
                para = sent  # any model failure -> keep the original sentence
            # Restore this sentence's placeholders; if any locked span was lost, keep the original.
            restored = para
            for ph, real in placeholders.items():
                if ph in sent:
                    restored = restored.replace(ph, real)
            # Verify: every sentinel that was in this source sentence survived into the restored one.
            src_ph = [ph for ph in placeholders if ph in sent]
            if any(placeholders[ph] not in restored for ph in src_ph):
                # a locked span was dropped by the paraphrase -> fall back to the original sentence
                original = sent
                for ph, real in placeholders.items():
                    original = original.replace(ph, real)
                restored = original
            out_parts.append(restored.strip())

        result = " ".join(p for p in out_parts if p)
        # Final safety: every original sentinel must be present exactly once (no drop, no dup),
        # else return the input untouched.
        if Counter(_SENTINEL_RE.findall(result)) != Counter(sentinels):
            return text
        return result or text
