"""MT-pivot rewriter — round-trip machine translation as a loop rewriter.

Wraps :class:`~untell.attacks.back_translation.BackTranslator` so back-translation can run *inside*
the sentinel-protected loop. MarianMT does not understand ``⟦HZxxxx⟧`` sentinels, so each is swapped
for an ALLCAPS placeholder (which MT models copy verbatim), translated, then swapped back. If any
sentinel is lost in translation the input is returned unchanged — the loop's own sentinel check
(``run.py``: ``find_sentinels(candidate) != set(mapping)``) is the second net.

Most useful on watermarked / repetitively-phrased input, where round-trip MT breaks the n-gram
patterns statistical detectors key on. Needs ``.[full]`` (torch + transformers + sentencepiece);
degrades to a safe no-op when unavailable, exactly like the other optional rewriters.
"""

from __future__ import annotations

from collections import Counter

from untell.attacks.back_translation import BackTranslator
from untell.layout import apply_per_block

# Matches the sentinel format lock() emits (4-or-more digits — see preserve.py).
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE


class MTPivotRewriter:
    """Round-trip-MT rewriter that is safe inside the sentinel-locked loop."""

    name = "mt_pivot"
    deterministic = False  # beam search output is stable per model but not guaranteed no-op

    def __init__(self, pivots: tuple[str, ...] = ("fr",)):
        self.pivots = pivots
        self._bt = BackTranslator()

    def available(self) -> bool:
        return self._bt.available()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        if not text.strip() or not self.available():
            return text
        # Round-trip MT reflows whatever it is given, so a document came back with its blank lines,
        # list markers and fenced code collapsed into one paragraph. Translating a block at a time
        # keeps the layout, and single-paragraph input takes the same path as before.
        return apply_per_block(text, self._rewrite_block)

    def _rewrite_block(self, text: str) -> str:
        if not text.strip():
            return text

        # Swap each sentinel for an ALLCAPS placeholder MarianMT copies verbatim.
        # `wanted` keeps the per-sentinel OCCURRENCE COUNT of the source; the survival check below
        # compares against it. Comparing against the deduplicated list instead meant any entity
        # mentioned twice made the counts differ even when MT preserved both, so every such text
        # took the fallback path and the rewriter was a silent no-op on it.
        wanted = Counter(_SENTINEL_RE.findall(text))
        sentinels = list(wanted)  # unique, in first-appearance order
        placeholders: dict[str, str] = {}
        swapped = text
        for i, sent in enumerate(sentinels):
            ph = f"ZQXMARK{i}ZQX"
            placeholders[ph] = sent
            swapped = swapped.replace(sent, ph)

        try:
            translated = self._bt.back_translate(swapped, pivots=self.pivots)
        except Exception:
            return text  # any MT failure -> safe no-op

        # Restore sentinels from placeholders.
        for ph, sent in placeholders.items():
            translated = translated.replace(ph, sent)

        # Verify every sentinel survived; otherwise fall back to the original (the loop's own
        # sentinel check would reject a lossy candidate anyway, but returning the input keeps the
        # loop moving instead of wasting the draw).
        if Counter(_SENTINEL_RE.findall(translated)) != wanted:
            return text  # a sentinel was dropped OR duplicated by MT -> safe no-op
        return translated
