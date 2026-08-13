"""Unicode-level tricks: homoglyph substitution (attack) + hidden-watermark scrubbing (defense).

Two sub-semantic operations several competitor repos have and we didn't:

- ``scrub_hidden`` (defense, recommended): strip invisible LLM watermarks / steganography — zero-width
  carriers, Unicode tag chars, C0/C1 controls, and every other character that renders as nothing or as
  blank space (soft hyphen, combining grapheme joiner, Hangul fillers, braille blank, Mongolian vowel
  separator, interlinear annotation anchors) — normalize the exotic space variants to U+0020, then map
  a conservative set of confusable homoglyphs back to ASCII. Uses NFC (not NFKC) so
  superscripts/ligatures/full-width forms survive.

  Three classes are **context-dependent**, kept where they are load-bearing and stripped where they
  are payload: structural ZWJ inside emoji sequences, variation selectors following an emoji base,
  and bidirectional format marks in text that actually contains a right-to-left script. Outside
  those contexts all three are invisible carriers (bidi controls are also the Trojan-Source vector),
  and a blanket "preserve" left 11 + 16 codepoints of channel open. Cleans embedded watermarks
  without mangling real content.
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
# U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR are categories Zl and Zp, not Zs, so they
# fall through the class above and through score.py's `_INVISIBLE_RE` -- which made them the one
# whitespace family that survived a scrub AND raised no caveat.
#
# MEASURED, inserted after every "e" in a two-sentence paragraph, lite/stdlib path:
#
#     baseline                  0.6735
#     with U+2028 or U+2029     0.5545     removed by scrub: NO     warned: NO
#
# A drop of 0.119 in the direction that reports AI text as human, from a character no surface
# mentioned. Mapped to a newline rather than deleted: they ARE line breaks, and deleting one welds
# two lines together, which is the damage the layout work elsewhere in this repo exists to stop.
_LINE_SEPARATORS = re.compile("[  ]")


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


_KEYCAP = "⃣"  # COMBINING ENCLOSING KEYCAP


def _strip_orphan_variation_selectors(text: str) -> str:
    """Drop variation selectors that are not attached to an emoji base.

    Attachment is judged on BOTH neighbours. Looking only backwards mangles the one emoji whose
    base is ASCII: a keycap is `[0-9#*]` + U+FE0F + U+20E3, so the selector sits after a plain
    digit, fails an emoji test applied to the preceding character, and is dropped —

        "press 1️⃣ to continue"  ->  "press 1⃣ to continue"

    which is a rendering change to legitimate content, from a function whose docstring promises
    variation selectors and emoji survive. Found by testing that promise rather than reading it.
    """
    if not _VARIATION_SELECTORS.search(text):
        return text
    out = []
    for i, ch in enumerate(text):
        if _VARIATION_SELECTORS.fullmatch(ch):
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if not _is_emoji_adjacent(prev) and nxt != _KEYCAP:
                continue
        out.append(ch)
    return "".join(out)


# Deprecated by Unicode itself (see UAX #9 and the Core Spec's deprecation table). They have no
# legitimate modern use in any script, render as nothing, and survive copy-paste — which is the
# whole specification of a steganographic carrier. Always stripped; there is no context in which
# keeping one is correct.
_DEPRECATED_FORMAT = re.compile("[⁪-⁯]")

# Script-specific format marks: load-bearing inside their own script and pure carriers outside it.
# Exactly the situation the bidi rule below already handles, applied to the classes it does not
# cover. Each entry is (the marks, a pattern matching the script that makes them meaningful).
_SCRIPTED_FORMAT_MARKS: tuple[tuple[re.Pattern, re.Pattern], ...] = (
    # Arabic and Syriac number/ayah/abbreviation signs
    (re.compile("[؀-؅۝܏࢐࢑࣢]"),
     re.compile("[؀-ۿ܀-ݏݐ-ݿࢠ-ࣿ"
                "ﭐ-﷿ﹰ-﻿]")),
    # Kaithi number signs
    (re.compile("[𑂽𑃍]"), re.compile("[𑂀-𑃏]")),
    # Egyptian hieroglyph joiners and segment controls
    (re.compile("[𓐰-𓐿]"), re.compile("[𓀀-𓐯]")),
    # Duployan shorthand overlap/step controls
    (re.compile("[𛲠-𛲣]"), re.compile("[𛰀-𛲟]")),
    # Musical notation beam/tie/slur/phrase controls
    (re.compile("[𝅳-𝅺]"), re.compile("[𝄀-𝅲]")),
)


def _strip_orphan_scripted_marks(text: str) -> str:
    """Drop a script's format marks when that script is absent from the text.

    MEASURED by sweeping every invisible codepoint in Unicode through ``scrub_hidden`` and
    ``count_hidden``: 49 survived the scrub AND were reported clean. Six were the deprecated
    U+206A-206F block; the rest were these — Arabic ayah and number signs, the Syriac abbreviation
    mark, Kaithi number signs, Egyptian hieroglyph joiners, Duployan shorthand controls, musical
    beam and slur controls. All render as nothing in Latin prose, all survive a copy-paste, and
    none can be doing layout work in a document containing none of their script.

    Same shape as ``_strip_orphan_bidi`` and for the same reason: the character is not the problem,
    the absence of anything for it to act on is.

    The marks are removed from the text BEFORE testing for their script, and that detail is the
    whole rule. Several of these blocks contain their own marks — U+0600 sits inside the Arabic
    range U+0600-06FF — so testing the raw text finds the carrier itself, concludes the script is
    present, and keeps it. Measured: that left all nine Arabic and Syriac marks passing through a
    pure-ASCII sentence.
    """
    for marks, script in _SCRIPTED_FORMAT_MARKS:
        if marks.search(text) and not script.search(marks.sub("", text)):
            text = marks.sub("", text)
    return text


# Deepest legitimate combining-mark stack, measured after NFC on real text in the scripts that use
# them most heavily:
#
#     hebrew (niqqud)  3      devanagari  2      thai  2      arabic (full diacritics)  2
#     vietnamese       0      greek       0      korean 0     latin                     0
#
# Vietnamese and Latin come out at 0 because NFC composes their accents into precomposed
# codepoints. 4 leaves headroom above every observed case.
_MAX_MARK_STACK = 4


def _strip_mark_stacks(text: str, keep: int = _MAX_MARK_STACK) -> str:
    """Drop combining marks stacked deeper than any script actually stacks them.

    Combining marks are the one invisible-carrier class this module cannot filter by identity: the
    exact codepoints that encode a payload are the ones that write Hebrew, Thai and Devanagari, so
    a blocklist would corrupt those languages the way the blanket homoglyph map corrupted Russian.

    Same rule as ``_strip_orphan_bidi`` and ``_strip_orphan_scripted_marks``, one level up: the
    character is not the problem, the ABSENCE OF ANYTHING FOR IT TO ACT ON is. A mark composing a
    base character is doing work; the twentieth mark on the same base is not composing anything.

    MEASURED before this existed — a 24-mark payload on one base character survived ``scrub_hidden``
    intact (24 of 24 marks) and ``count_hidden`` reported **0**, so the tool said the text was clean
    while the payload rode through. That is the same failure this module already recorded twice, in
    a codepoint class it had not swept.

    Mn AND Me. Enclosing marks are the same construct with a different category, and testing only
    "Mn" left all 13 of them (U+0488 COMBINING CYRILLIC HUNDRED THOUSANDS SIGN and friends) stacking
    without limit. Depth 4 keeps the one legitimate use — an emoji keycap is base + VS16 + U+20E3,
    a stack of one.

    KNOWN RESIDUAL, stated rather than papered over: an attacker who spreads marks at or below the
    cutoff across many base characters is, at that point, writing something a diacritic-bearing
    script would also write. Distinguishing those needs language context this function does not
    have. This closes stacking, which is the form that is unambiguous.

    OUT OF SCOPE, deliberately, and measured: unassigned codepoints (category Cn, 825314 of them)
    and private-use codepoints (Co, 137468) also survive this module untouched. Neither is stripped
    and neither should be. Both render as tofu rather than as nothing, so they are visible carriers
    rather than invisible ones; private use is load-bearing for icon fonts; and `unicodedata` is
    pinned to one Unicode version, so today's "unassigned" is tomorrow's ordinary letter and
    stripping it would corrupt text this library never saw. The rule this module follows — remove
    what cannot be doing work — does not reach them.
    """
    out: list[str] = []
    run = 0
    for ch in text:
        if unicodedata.category(ch) in ("Mn", "Me"):
            run += 1
            if run > keep:
                continue
        else:
            run = 0
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

    Two transformations this ALSO performs, stated here because a caller reading only this docstring
    would not expect either and both change the output text:

    - **Exotic spaces are normalised to U+0020**, including NBSP and the ideographic space U+3000.
      Width-encoded steganography uses exactly those codepoints, so the channel is closed by
      rewriting rather than deleting — the text still reads the same, but U+00A0 loses its
      non-breaking behaviour and CJK U+3000 becomes a plain space. See ``_EXOTIC_SPACE``.
    - **Soft hyphens (U+00AD) are removed** as invisible carriers, so a typographic line-break hint
      does not survive.

    "Bidirectional format marks intact" means marks doing real layout work. An ORPHAN bidi mark —
    one with no RTL text to act on — is stripped as a carrier. Verified: RLM/LRM adjacent to Arabic,
    and RLE/PDF and FSI/PDI pairs, all survive unchanged; an RLM between two ASCII words does not.
    """
    text = _WATERMARK_CHARS.sub("", text)
    text = _EXOTIC_SPACE.sub(" ", text)
    # After the space class, so a Zl/Zp separator becomes a real line break rather than
    # being collapsed into a space by the line above.
    text = _LINE_SEPARATORS.sub(chr(10), text)
    text = _strip_orphan_zwj(text)
    text = _strip_orphan_variation_selectors(text)
    text = _strip_orphan_bidi(text)
    text = _DEPRECATED_FORMAT.sub("", text)
    text = _strip_orphan_scripted_marks(text)
    text = _strip_mark_stacks(text)
    # Drop C0/C1 control characters (category Cc) except common whitespace; KEEP format characters
    # (category Cf) such as bidi marks, which carry layout meaning.
    text = "".join(ch for ch in text if ch in "\t\n\r" or unicodedata.category(ch) != "Cc")
    text = _unhomoglyph(text)
    return unicodedata.normalize("NFC", text)


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _unhomoglyph(text: str) -> str:
    """Fold confusables to ASCII where they are INTRUDERS, not where they are the language.

    A blanket per-character map destroys any text actually written in Cyrillic or Greek, which is
    most of the alphabet's high-frequency letters. MEASURED, before this was scoped:

        "Это очень простой текст про кота."  ->  "Этo oчeнь пpocтoй тeкcт пpo кoтa."
        "Αυτό είναι ένα απλό κείμενο."       ->  "Ayτό eίvai έva aπλό keίμevo."

    Unreadable mixed-script garbage, from a function whose whole promise is that it "leaves visible
    text byte-identical". Scrubbing is the DEFENSIVE path — the one a user runs on text they care
    about — so silently corrupting their Russian was the worst available failure.

    The distinction is per word, following the mixed-script logic of UTS #39:

    - A word holding at least one ASCII letter is Latin text with intruders in it — "pаper" with a
      Cyrillic а. Fold every confusable in it.
    - A word made ENTIRELY of confusables is folded too, but only inside a document that is
      otherwise mostly ASCII: "оре" among English words is an attack, while the same three letters
      inside Russian prose are a word. Real Cyrillic and Greek words almost always carry at least
      one letter with no ASCII lookalike (ч, б, я, λ, μ, π), which is what keeps them out of this
      branch.
    - Everything else is left alone. That leaves one hole open by construction: an all-confusable
      word inside genuinely non-Latin text. Nothing in the string distinguishes it from the real
      word, and mangling every Russian document is too high a price for closing it.
    """
    # "Is this a Latin document?" — judged on letters that are EVIDENCE either way, which means
    # ignoring the confusables themselves. Counting them as non-Latin lets the attack vote on
    # whether it is an attack: `homoglyph_substitute("america cocoa")` renders cocoa entirely in
    # Cyrillic, and a raw ratio then reads 7/12 ASCII and declares the document mixed-script.
    # Native letters — the ones with no ASCII lookalike — are what actually distinguishes Russian
    # prose from Latin prose wearing a costume.
    evidence = [ch for ch in text if ch.isalpha() and (ch.isascii() or ch not in _UNHOMOGLYPH)]
    mostly_ascii = bool(evidence) and sum(ch.isascii() for ch in evidence) / len(evidence) >= 0.8

    def fold(match: re.Match) -> str:
        word = match.group(0)
        alpha = [ch for ch in word if ch.isalpha()]
        if not any(ch in _UNHOMOGLYPH for ch in word):
            return word
        native = any(ch.isalpha() and not ch.isascii() and ch not in _UNHOMOGLYPH for ch in word)
        if any(ch.isascii() and ch.isalpha() for ch in word) and not native:
            return "".join(_UNHOMOGLYPH.get(ch, ch) for ch in word)
        if mostly_ascii and alpha and all(ch in _UNHOMOGLYPH for ch in alpha):
            return "".join(_UNHOMOGLYPH.get(ch, ch) for ch in word)
        return word

    return _WORD_RE.sub(fold, text)


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
    # Fifth carrier class, counted the way it is scrubbed. A 24-mark stack on one base character
    # survived the scrub AND was reported as 0 hidden characters before `_strip_mark_stacks`.
    mark_stacks = len(text) - len(_strip_mark_stacks(text))
    # C0/C1 controls are stripped by scrub_hidden too (everything in category Cc except tab, newline
    # and carriage return), so they must be counted here or the same under-report recurs — this is
    # the third carrier class to go missing from this function.
    controls = sum(1 for ch in text if ch not in "\t\n\r" and unicodedata.category(ch) == "Cc")
    # scrub_hidden ends with an NFC pass, and NFC itself rewrites a handful of SINGLETON codepoints
    # that are confusables in their own right: U+037E GREEK QUESTION MARK -> ';', U+1FEF GREEK
    # VARIA -> '`', U+212A KELVIN SIGN -> 'K'. Measured, each was scrubbed while this function
    # reported 0, so the report said the text was clean and the text had changed. That is the
    # fourth carrier class to go missing here, so it is counted the way it is applied — by asking
    # NFC — rather than by listing the three codepoints and waiting for a fifth.
    #
    # Per CHARACTER, deliberately: composing "e" + combining acute is legitimate Unicode and
    # normalising the pair changes it, but neither character changes alone, so this counts only the
    # singletons and leaves real composition alone.
    nfc_singletons = sum(1 for ch in text if unicodedata.normalize("NFC", ch) != ch)
    return (
        invisible + exotic_spaces + homoglyphs + orphan_zwj + orphan_vs + orphan_bidi
        + controls + nfc_singletons + mark_stacks
    )
