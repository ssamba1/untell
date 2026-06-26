"""Unicode-level tricks: homoglyph substitution (attack) + hidden-watermark scrubbing (defense).

Two sub-semantic operations several competitor repos have and we didn't:

- ``scrub_hidden`` (defense, recommended): strip invisible LLM watermarks / steganography — zero-width
  steganography carriers, Unicode tag chars, and C0/C1 control chars — then map a conservative set of
  confusable homoglyphs back to ASCII. It deliberately PRESERVES emoji ZWJ sequences, variation
  selectors, and bidirectional format marks (stripping those corrupts legitimate text), and uses NFC
  (not NFKC) so superscripts/ligatures/full-width forms survive. Cleans embedded watermarks without
  mangling real content.
- ``homoglyph_substitute`` (attack, OPT-IN, caveated): replace a fraction of ASCII letters with
  visually identical Cyrillic/Greek homoglyphs to disrupt detector tokenization (silverspeak,
  arXiv 2406.11239). **Caveats:** invisible to humans but breaks copy-paste/search, is removed by any
  detector that NFKC-normalizes first, and detectors like Winston flag unusual Unicode as an attack.
  Last resort only — ``scrub_hidden`` is the opposite of robust evasion, use deliberately.
"""

from __future__ import annotations

import re
import unicodedata

# ASCII -> visually-identical homoglyph (Cyrillic/Greek). Conservative set that renders identically.
_HOMOGLYPH = {
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х",
    "y": "у", "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н",
    "K": "К", "M": "М", "O": "О", "P": "Р", "T": "Т", "X": "Х",
}
# Reverse map (+ a few extra confusables) for scrubbing back to ASCII.
_UNHOMOGLYPH = {v: k for k, v in _HOMOGLYPH.items()}

# Genuinely invisible watermark/steganography carriers with no legitimate role in prose.
# NOTE: U+200D (ZWJ) and the variation selectors (incl. U+FE0F) are deliberately NOT listed — they
# are load-bearing in emoji sequences (👨‍👩‍👧‍👦, ❤️) and several scripts, so stripping them would
# corrupt real user text. Bidi format marks are likewise preserved by the Cf-aware filter below.
_WATERMARK_CHARS = re.compile(
    "[​‌⁠﻿]"  # zero-width space / non-joiner / word-joiner / BOM (ZWNBSP)
    "|[\U000e0000-\U000e007f]"  # Unicode tag chars (used for invisible-tag watermarks)
)


def _is_emoji_adjacent(ch: str) -> bool:
    """Heuristic: is ``ch`` an emoji (or emoji modifier/selector) that a ZWJ legitimately joins?"""
    if not ch:
        return False
    o = ord(ch)
    return (
        0x1F000 <= o <= 0x1FAFF        # pictographic emoji blocks
        or 0x1F1E6 <= o <= 0x1F1FF     # regional indicators (flags)
        or 0x2600 <= o <= 0x27BF       # misc symbols + dingbats
        or 0x2300 <= o <= 0x23FF       # misc technical (⌚ ⏰ …)
        or 0xFE00 <= o <= 0xFE0F       # variation selectors (sit between an emoji base and the ZWJ)
        or o in (0x2640, 0x2642, 0x2695, 0x2696, 0x2708, 0x2764, 0x2122, 0x00A9, 0x00AE, 0x203C, 0x2049)
    )


def _strip_orphan_zwj(text: str) -> str:
    """Strip ZWJ (U+200D) only when it is NOT joining two emoji — i.e. an orphan/watermark ZWJ.

    Structural ZWJ inside emoji sequences (👨‍👩‍👧‍👦, 🏳️‍🌈, 👨‍⚕️) is preserved; a ZWJ sitting between
    ordinary characters (a steganographic watermark carrier) is removed.
    """
    if "‍" not in text:
        return text
    out = []
    for i, ch in enumerate(text):
        if ch == "‍" and not (
            _is_emoji_adjacent(text[i - 1] if i else "")
            and _is_emoji_adjacent(text[i + 1] if i + 1 < len(text) else "")
        ):
            continue  # orphan ZWJ between non-emoji -> watermark, drop it
        out.append(ch)
    return "".join(out)


def scrub_hidden(text: str) -> str:
    """Remove invisible watermark/steganography characters and normalize confusables to ASCII.

    Strips zero-width steganography carriers, orphan ZWJ, Unicode tag chars, and C0/C1 control
    characters, then maps a conservative Cyrillic/Greek homoglyph set back to ASCII. Uses NFC (not
    NFKC) and keeps emoji ZWJ sequences, variation selectors, and bidirectional format marks intact,
    so legitimate Unicode (emoji, superscripts, ligatures, RTL layout) is preserved.
    """
    text = _WATERMARK_CHARS.sub("", text)
    text = _strip_orphan_zwj(text)
    # Drop C0/C1 control characters (category Cc) except common whitespace; KEEP format characters
    # (category Cf) such as bidi marks, which carry layout meaning.
    text = "".join(ch for ch in text if ch in "\t\n\r" or unicodedata.category(ch) != "Cc")
    text = "".join(_UNHOMOGLYPH.get(ch, ch) for ch in text)
    return unicodedata.normalize("NFC", text)


def homoglyph_substitute(text: str, rate: float = 0.15) -> str:
    """Replace a fraction (``rate``) of eligible ASCII letters with homoglyphs. OPT-IN attack.

    Deterministic (every Nth eligible letter) so it is reproducible and testable. See module caveats.
    """
    if rate <= 0:
        return text
    period = max(1, round(1 / rate))
    out = []
    n = 0
    for ch in text:
        if ch in _HOMOGLYPH:
            n += 1
            out.append(_HOMOGLYPH[ch] if n % period == 0 else ch)
        else:
            out.append(ch)
    return "".join(out)


def count_hidden(text: str) -> int:
    """How many invisible/homoglyph chars are present — a quick 'is this watermarked?' check."""
    invisible = len(_WATERMARK_CHARS.findall(text))
    homoglyphs = sum(1 for ch in text if ch in _UNHOMOGLYPH)
    return invisible + homoglyphs
