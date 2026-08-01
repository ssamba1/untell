"""Back-translation perturbation (round-trip machine translation).

Translating English -> pivot language -> English rephrases text while largely preserving meaning —
a classic, training-free detector-evasion / augmentation technique (it raises perplexity and shifts
phrasing without an LLM). Uses Helsinki-NLP MarianMT models on CPU. Optional: needs
``transformers`` + ``torch`` + ``sentencepiece``; degrades to a safe **no-op** (returns the input
unchanged) when unavailable, so callers never have to guard.

Note: round-trip MT does NOT understand sentinels, so run this on raw text *before* preserve-lock,
or not at all on already-masked text — it is offered as a research augmentation, not a step inside
the sentinel-protected loop.
"""

from __future__ import annotations

import re

_MODEL = "Helsinki-NLP/opus-mt-{src}-{tgt}"


class BackTranslator:
    """Round-trip translator with per-direction model caching."""

    # cache: (src, tgt) -> (tokenizer, model)
    _cache: dict = {}

    def available(self) -> bool:
        try:
            import sentencepiece  # noqa: F401
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _pipe(self, src: str, tgt: str):
        key = (src, tgt)
        if key not in BackTranslator._cache:
            from transformers import MarianMTModel, MarianTokenizer

            name = _MODEL.format(src=src, tgt=tgt)
            tok = MarianTokenizer.from_pretrained(name)
            model = MarianMTModel.from_pretrained(name).eval()
            BackTranslator._cache[key] = (tok, model)
        return BackTranslator._cache[key]

    # MarianMT's positional limit. Anything past this is DISCARDED by the tokenizer, silently.
    _MAX_TOKENS = 512

    def _chunk(self, text: str, tok) -> list[str]:
        """Split into sentence-aligned pieces that each fit the model's token budget.

        ``truncation=True`` silently drops everything past the cap and returns the partial
        translation as if it were complete — no exception, no warning. MarianMT's SentencePiece
        vocabulary averages well over one token per English word, so the 512-token cap starts
        discarding text somewhere around 350-400 words: an ordinary two-paragraph document would
        come back ~30% shorter with no indication anything was lost. Chained pivots compound it,
        since each hop re-applies the cap to the previous hop's output.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            # Measure with the real tokenizer rather than guessing a word ratio.
            if current and len(tok(candidate)["input_ids"]) > self._MAX_TOKENS - 16:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [text]

    def _translate(self, text: str, src: str, tgt: str) -> str:
        import torch

        tok, model = self._pipe(src, tgt)
        out: list[str] = []
        for chunk in self._chunk(text, tok):
            batch = tok([chunk], return_tensors="pt", truncation=True,
                        max_length=self._MAX_TOKENS, padding=True)
            with torch.no_grad():
                gen = model.generate(**batch, max_length=self._MAX_TOKENS, num_beams=4)
            out.append(tok.batch_decode(gen, skip_special_tokens=True)[0])
        return " ".join(p for p in out if p)

    def back_translate(self, text: str, pivots: tuple[str, ...] = ("fr",)) -> str:
        """English -> each pivot -> English, chained. Returns the input unchanged if unavailable."""
        if not text.strip() or not self.available():
            return text
        out = text
        try:
            for pivot in pivots:
                mid = self._translate(out, "en", pivot)
                out = self._translate(mid, pivot, "en")
        except Exception:
            return text  # any model/translation failure -> safe no-op
        return out


_DEFAULT = BackTranslator()


def back_translate(text: str, pivots: tuple[str, ...] = ("fr",)) -> str:
    """Module-level convenience wrapper around a shared :class:`BackTranslator`."""
    return _DEFAULT.back_translate(text, pivots=pivots)
