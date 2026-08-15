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
from untell.layout import apply_per_block
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE
from untell.text_split import split_sentences

_MODEL_ID = "humarin/chatgpt_paraphraser_on_T5_base"


class T5ParaphraseRewriter:
    """Free CPU/GPU neural paraphraser. ``available()`` only when torch+transformers import."""

    name = "t5_paraphrase"

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

    @property
    def deterministic(self) -> bool:
        """Whether repeated calls return byte-identical output — which depends on ``sample``.

        This was a class attribute pinned to ``False`` with the note "sampled generation varies run
        to run". Sampled generation does; the DEFAULT construction does not sample. ``sample=False``
        takes the beam-search branch below, and three consecutive draws on the same input were
        measured byte-identical.

        The loop reads this to decide how many candidates to draw::

            draws = 1 if getattr(rw, "deterministic", False) else max(1, best_of)

        so at the default ``best_of=3`` it took three draws of one answer, paying a full detector
        pass for each — and run.py's own comment calls that out: "extra draws are pure waste, and
        the waste is the EXPENSIVE part". At ``--tier full`` that is two redundant five-detector
        passes per iteration on the slowest rewriter in the repo.

        The second reader, the stalled-iteration early exit, was disabled by the same mistake: a
        rewriter that cannot produce anything new kept iterating to ``max_iters``.

        A property rather than an attribute because the answer is per-instance. Both readers use
        ``getattr(rw, ...)`` on an instance, so this resolves; reading it off the CLASS would get
        the property object, which is truthy — checked, and nothing does that.
        """
        return not self.sample

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
        return tok.decode(out[0], skip_special_tokens=False).strip()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        if not text.strip() or not self.available():
            return text
        # Paraphrasing ends in `" ".join(out_parts)`, which discards every newline: a document came
        # back with its blank lines, list markers and fenced code flattened into one paragraph.
        # Rewriting a block at a time keeps the layout and changes nothing for single-paragraph
        # input, which is the common case.
        return apply_per_block(text, self._rewrite_block)

    def _rewrite_block(self, text: str) -> str:
        if not text.strip():
            return text

        # Swap sentinels for ALLCAPS placeholders the model tends to copy verbatim.
        # `wanted` holds the source's per-sentinel occurrence counts, which is what the final check
        # must compare against — measuring the output against the *deduplicated* set made any
        # entity mentioned twice look duplicated and silently disabled the rewriter on that text.
        wanted = Counter(_SENTINEL_RE.findall(text))
        placeholders = {f"ZQXMARK{i}ZQX": s for i, s in enumerate(wanted)}
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
        # Final safety: every original sentinel must survive with its original multiplicity
        # (no drop, no dup), else return the input untouched.
        if Counter(_SENTINEL_RE.findall(result)) != wanted:
            return text
        return result or text
