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
# Clause boundaries, used only to break a sentence that is itself over the token budget.
_CLAUSE = re.compile(r"(?<=[,;:])\s+")


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
        # Abbreviation-aware (untell.text_split): splitting "Dr. Smith" apart here sends "Dr." into
        # the translator as a standalone sentence, and a round trip through another language does
        # not reliably bring an abbreviation back.
        from untell.text_split import split_sentences

        budget = self._MAX_TOKENS - 16
        sentences = split_sentences(text.strip())
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            # A sentence that exceeds the budget on its own cannot be rescued by starting a new
            # chunk, and the `current and` guard below skips the size test for exactly that case —
            # so one long sentence (roughly 350+ words) passed through whole and _translate
            # truncated it. Break it up before it gets there.
            for piece in self._fit(sentence, tok, budget):
                candidate = f"{current} {piece}".strip() if current else piece
                # Measure with the real tokenizer rather than guessing a word ratio.
                if current and len(tok(candidate)["input_ids"]) > budget:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
        if current:
            chunks.append(current)
        return chunks or [text]

    def _fit(self, sentence: str, tok, budget: int) -> list[str]:
        """One sentence as pieces that each fit ``budget``. Usually returns it unchanged.

        Clause boundaries first, so the translator still receives grammatical units; a greedy
        word-level fill only for a clause that is itself over budget. Both measure with the real
        tokenizer — MarianMT's SentencePiece vocabulary runs well over one token per English word,
        so any word-count estimate would be wrong in the unsafe direction.
        """
        if len(tok(sentence)["input_ids"]) <= budget:
            return [sentence]

        def _greedy(units: list[str]) -> list[str]:
            out: list[str] = []
            cur = ""
            for u in units:
                candidate = f"{cur} {u}".strip() if cur else u
                if cur and len(tok(candidate)["input_ids"]) > budget:
                    out.append(cur)
                    cur = u
                else:
                    cur = candidate
            if cur:
                out.append(cur)
            return out

        pieces: list[str] = []
        for clause in _greedy(_CLAUSE.split(sentence)):
            if len(tok(clause)["input_ids"]) <= budget:
                pieces.append(clause)
            else:
                pieces.extend(_greedy(clause.split()))
        return pieces or [sentence]

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
