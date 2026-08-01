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
# Reverse map for scrubbing back to ASCII. The SCRUB direction must be wider than the attack
# direction: we only emit Cyrillic confusables, but an adversary (or another humanizer) can use
# Greek ones just as easily, and the docstring already promised "Cyrillic/Greek". Measured, the
# Greek set was entirely absent — "aοc" (Greek omicron) survived scrub_hidden untouched.
_UNHOMOGLYPH = {v: k for k, v in _HOMOGLYPH.items()}
_UNHOMOGLYPH.update({
    "ο": "o", "α": "a", "ε": "e", "ρ": "p", "χ": "x", "υ": "y", "ι": "i", "κ": "k", "ν": "v",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N",
    "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
    # Cyrillic confusables we never emit ourselves but must still strip on the way in.
    "і": "i", "ѕ": "s", "ј": "j", "һ": "h", "ԁ": "d", "Ѕ": "S", "Ј": "J", "І": "I",
})

# Genuinely invisible watermark/steganography carriers with no legitimate role in prose.
# NOTE: U+200D (ZWJ) and the variation selectors (incl. U+FE0F) are deliberately NOT listed — they
# are load-bearing in emoji sequences (👨‍👩‍👧‍👦, ❤️) and several scripts, so stripping them would
# corrupt real user text. Bidi format marks are likewise preserved by the Cf-aware filter below.
_WATERMARK_CHARS = re.compile(
    "[​‌⁠﻿]"  # zero-width space / non-joiner / word-joiner / BOM (ZWNBSP)
    "|[\U000e0000-\U000e007f]"  # Unicode tag chars (used for invisible-tag watermarks)
    # Invisible math operators (U+2061 FUNCTION APPLICATION .. U+2064 INVISIBLE PLUS). These are
    # category Cf, so the "keep Cf for bidi layout" rule below was blanket-preserving them — but
    # unlike bidi marks they have NO legitimate role in prose, only in mathematical markup. They are
    # therefore ideal invisible carriers, and they were surviving scrub_hidden untouched while
    # count_hidden reported 0.
    "|[⁡-⁤]"
    # Characters that RENDER AS NOTHING (or as blank space) and have no role in English prose.
    # Every one of these is a documented steganography carrier — they are what "invisible character"
    # generators emit — and none is covered by the bidi/variation-selector rationale above, which is
    # about characters that ARE load-bearing. Measured, all of them passed through scrub_hidden
    # untouched while count_hidden reported 0.
    "|­"              # SOFT HYPHEN — invisible unless the renderer breaks the line
    "|͏"              # COMBINING GRAPHEME JOINER — no visible effect anywhere
    "|؜"              # ARABIC LETTER MARK — bidi-adjacent but invisible in Latin prose
    "|᠎"              # MONGOLIAN VOWEL SEPARATOR — deprecated, zero width
    "|⠀"              # BRAILLE PATTERN BLANK — renders as blank, not a space
    "|[ᅟᅠㅤﾠ]"  # Hangul fillers — render as blank
    "|[឴឵]"      # Khmer inherent vowels — invisible
    "|[￹-￻]"     # interlinear annotation anchors
)

# Whitespace variants that render like a space but are distinct codepoints. Width-encoded
# steganography uses exactly these, so they are NORMALISED to U+0020 rather than deleted: the text
# still reads identically and no content is lost, but the carrier channel closes.
#
# The trade-off is deliberate and narrow — U+00A0 loses its non-breaking behaviour. For prose being
# fed to a detector that is the right call: unusual whitespace is itself something detectors flag.
_EXOTIC_SPACE = re.compile("[   -   　]")


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


# Bidirectional format controls. Load-bearing ONLY in text that actually contains a right-to-left
# script; in an all-Latin passage they are pure invisible payload (and the Trojan-Source vector).
_BIDI_CONTROLS = re.compile("[‎‏‪-‮⁦-⁩]")
# Ranges whose presence means bidi controls may be doing real layout work: Hebrew, Arabic, Syriac,
# Thaana, N'Ko, Samaritan, Mandaic, Arabic Supplement/Extended, and the presentation forms.
_RTL_CHARS = re.compile(
    "[֐-׿؀-ۿ܀-ݏހ-޿߀-߿"
    "ࠀ-࠿ࡀ-࡟ࢠ-ࣿיִ-﷿ﹰ-﻿]"
)
# Variation selectors. VS16 after an emoji base is load-bearing; the same codepoint between two
# Latin letters is a carrier — the "variation-selector smuggling" trick. Treated exactly like ZWJ:
# kept when it sits next to something emoji-ish, dropped when it does not.
_VARIATION_SELECTORS = re.compile("[︀-️\U000e0100-\U000e01ef]")


def _strip_orphan_variation_selectors(text: str) -> str:
    """Drop variation selectors that are not attached to an emoji base."""
    if not _VARIATION_SELECTORS.search(text):
        return text
    out = []
    for i, ch in enumerate(text):
        if _VARIATION_SELECTORS.fullmatch(ch) and not _is_emoji_adjacent(text[i - 1] if i else ""):
            continue
        out.append(ch)
    return "".join(out)


def _strip_orphan_bidi(text: str) -> str:
    """Drop bidi format controls unless the text actually contains a right-to-left script."""
    if _RTL_CHARS.search(text):
        return text  # real RTL content — the controls may be doing layout work, leave them alone
    return _BIDI_CONTROLS.sub("", text)


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
    text = _EXOTIC_SPACE.sub(" ", text)
    text = _strip_orphan_zwj(text)
    text = _strip_orphan_variation_selectors(text)
    text = _strip_orphan_bidi(text)
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
    """How many invisible/homoglyph chars are present — a quick 'is this watermarked?' check.

    MUST stay in sync with what ``scrub_hidden`` actually removes. Any carrier this misses but the
    scrubber strips produces the worst possible report: the caller is told the text is clean while a
    watermark is silently discarded (or, if they only counted, left in place). The MCP ``scrub`` tool
    returns this as ``hidden_chars_removed``, so a mismatch is user-visible and wrong.

    Orphan ZWJ is the subtle case: U+200D is deliberately absent from ``_WATERMARK_CHARS`` because it
    is structural inside emoji sequences, so it can only be counted the same way it is scrubbed — by
    diffing against ``_strip_orphan_zwj``.
    """
    invisible = len(_WATERMARK_CHARS.findall(text))
    # Exotic spaces are SUBSTITUTED, not deleted, so they change nothing about the length — the same
    # shape as a homoglyph. Counting them by length diff would report zero.
    exotic_spaces = len(_EXOTIC_SPACE.findall(text))
    homoglyphs = sum(1 for ch in text if ch in _UNHOMOGLYPH)
    orphan_zwj = len(text) - len(_strip_orphan_zwj(text))
    # Same treatment for the two other context-dependent classes: they can only be counted the way
    # they are scrubbed, by diffing against the function that does the scrubbing.
    orphan_vs = len(text) - len(_strip_orphan_variation_selectors(text))
    orphan_bidi = len(text) - len(_strip_orphan_bidi(text))
    # C0/C1 controls are stripped by scrub_hidden too (everything in category Cc except tab, newline
    # and carriage return), so they must be counted here or the same under-report recurs — this is
    # the third carrier class to go missing from this function.
    controls = sum(1 for ch in text if ch not in "\t\n\r" and unicodedata.category(ch) == "Cc")
    return invisible + exotic_spaces + homoglyphs + orphan_zwj + orphan_vs + orphan_bidi + controls
