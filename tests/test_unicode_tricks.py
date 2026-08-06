"""Tests for Unicode-level operations — scrub_hidden, homoglyph_substitute, count_hidden."""
from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import count_hidden, homoglyph_substitute, scrub_hidden


def test_scrub_removes_zero_width_chars():
    original = "before\u200Bafter"
    assert scrub_hidden(original) == "beforeafter"


def test_scrub_removes_tag_chars():
    """Unicode tag characters U+E0000..U+E007F must be stripped."""
    tag_char = chr(0xE0000)  # Start of Unicode Tag Characters block
    original = f"Hello{tag_char}World"
    cleaned = scrub_hidden(original)
    assert tag_char not in cleaned


def test_scrub_preserves_emoji_zwj():
    """Family emoji uses ZWJ (U+200D) between emoji. Must survive scrub."""
    family = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"  # 👨‍👩‍👧‍👦
    assert scrub_hidden(family) == family


def test_scrub_removes_orphan_zwj():
    """A ZWJ between plain letters is a steganographic watermark, must be removed."""
    text = "wa\u200Dter"
    assert scrub_hidden(text) == "water"


def test_scrub_normalizes_homoglyphs():
    """Cyrillic 'а' (U+0430) looks like ASCII 'a' (U+0061) — must map back."""
    text = "c\u0430t"  # Cyrillic 'а' instead of Latin 'a'
    assert scrub_hidden(text) == "cat"


def test_scrub_preserves_ascii_plaintext():
    plain = "The quick brown fox jumps over the lazy dog."
    assert scrub_hidden(plain) == plain


def test_scrub_handles_empty():
    assert scrub_hidden("") == ""


def test_homoglyph_substitute_rate_zero():
    assert homoglyph_substitute("hello", rate=0) == "hello"


def test_homoglyph_substitute_rate_one():
    """At rate=1.0, every eligible letter becomes a homoglyph."""
    result = homoglyph_substitute("ace", rate=1.0)
    assert result != "ace"
    assert len(result) == 3
    # All three chars should be homoglyphs
    for ch in result:
        assert ord(ch) > 127


def test_homoglyph_substitute_preserves_non_ascii():
    result = homoglyph_substitute("hello world 123!", rate=0.5)
    assert "123!" in result  # digits and punctuation unchanged
    assert " " in result


def test_homoglyph_substitute_empty():
    assert homoglyph_substitute("", rate=0.5) == ""


def test_count_hidden_zero_on_clean():
    assert count_hidden("clean text") == 0


def test_count_hidden_counts_invisible():
    text = "a\u200Bb\u200Cc"
    assert count_hidden(text) == 2


def test_count_hidden_counts_homoglyphs():
    text = "c\u0430t"  # Cyrillic 'а'
    assert count_hidden(text) == 1


def test_scrub_removes_control_chars_except_newlines():
    """C0/C1 control chars except \t \n \r should be stripped."""
    text = "before\x00middle\x1Fafter\nnewline"
    cleaned = scrub_hidden(text)
    assert "\x00" not in cleaned
    assert "\x1F" not in cleaned
    assert "\n" in cleaned  # newline preserved


def test_scrub_preserves_bidi_format_marks_in_rtl_text():
    """Bidi format marks carry layout meaning \u2014 but only where there is RTL text to lay out.

    This test previously asserted that U+200E survives in "English\u200EARabic", a string with no
    right-to-left character anywhere in it. That is precisely the case where the mark carries no
    layout meaning at all and is pure invisible payload, so the assertion pinned the gap rather
    than the guarantee: all eleven bidi controls passed straight through scrub_hidden while
    count_hidden reported the text clean.
    """
    rtl = "\u0645\u0631\u062D\u0628\u0627 \u200FEnglish"  # real Arabic content
    assert "\u200F" in scrub_hidden(rtl)


@pytest.mark.parametrize(
    "name,char",
    [
        ("LRM", "\u200E"), ("RLM", "\u200F"), ("LRE", "\u202A"), ("RLE", "\u202B"),
        ("PDF", "\u202C"), ("LRO", "\u202D"), ("RLO", "\u202E"), ("LRI", "\u2066"),
        ("RLI", "\u2067"), ("FSI", "\u2068"), ("PDI", "\u2069"), ("ALM", "\u061C"),
    ],
)
def test_bidi_control_in_latin_only_text_is_stripped(name, char):
    """With no RTL script present a bidi control is invisible payload (and the Trojan-Source vector)."""
    text = f"The build{char} succeeded on the first try."
    assert char not in scrub_hidden(text), f"{name} survived scrub_hidden in all-Latin text"
    assert count_hidden(text) == 1, f"{name} was not counted"


# Every carrier class that renders as nothing (or as a plain space) and has no role in English
# prose. Measured before this list existed: 40 of 51 probed carriers passed straight through
# scrub_hidden while count_hidden reported 0 \u2014 the worst possible report, because the caller is
# told the text is clean while the watermark is still in it.
CARRIERS = [
    ("ZWSP", "\u200B"), ("ZWNJ", "\u200C"), ("WORD JOINER", "\u2060"), ("BOM", "\uFEFF"),
    ("SOFT HYPHEN", "\u00AD"), ("COMBINING GRAPHEME JOINER", "\u034F"),
    ("MONGOLIAN VOWEL SEP", "\u180E"), ("BRAILLE BLANK", "\u2800"),
    ("HANGUL FILLER", "\u3164"), ("HALFWIDTH HANGUL FILLER", "\uFFA0"),
    ("KHMER INHERENT VOWEL", "\u17B4"), ("INTERLINEAR ANNOTATION", "\uFFF9"),
    ("FUNCTION APPLICATION", "\u2061"), ("INVISIBLE TIMES", "\u2062"),
    ("INVISIBLE SEPARATOR", "\u2063"), ("INVISIBLE PLUS", "\u2064"),
    ("TAG SPACE", "\U000e0020"), ("TAG LETTER", "\U000e0061"),
    ("NBSP", "\u00A0"), ("NARROW NBSP", "\u202F"), ("FIGURE SPACE", "\u2007"),
    ("HAIR SPACE", "\u200A"), ("THIN SPACE", "\u2009"), ("EN SPACE", "\u2002"),
    ("EM SPACE", "\u2003"), ("IDEOGRAPHIC SPACE", "\u3000"), ("OGHAM SPACE", "\u1680"),
    ("VARIATION SELECTOR 1", "\uFE00"), ("VARIATION SELECTOR 16", "\uFE0F"),
    ("VARIATION SELECTOR SUPPLEMENT", "\U000e0100"),
]


@pytest.mark.parametrize("name,char", CARRIERS, ids=[c[0] for c in CARRIERS])
def test_every_invisible_carrier_is_scrubbed_and_counted(name, char):
    text = f"The build{char} succeeded on the first try."
    assert scrub_hidden(text) != text, f"{name} survived scrub_hidden"
    assert count_hidden(text) == 1, f"{name} scrubbed but counted as {count_hidden(text)}"


@pytest.mark.parametrize(
    "label,text",
    [
        ("plain ascii", "Nothing hidden in this sentence at all."),
        ("emoji ZWJ family", "Family: \U0001f468\u200D\U0001f469\u200D\U0001f467"),
        ("emoji variation selector", "Heart: \u2764\uFE0F done"),
        ("arabic with bidi mark", "\u0645\u0631\u062D\u0628\u0627 \u200F\u0639\u0627\u0644\u0645"),
        ("accented latin", "Caf\u00E9 na\u00EFve r\u00E9sum\u00E9 co\u00F6perate."),
        ("curly quotes and dashes", "\u201CQuoted\u201D \u2014 and an en\u2013dash."),
    ],
)
def test_legitimate_text_survives_untouched(label, text):
    """Over-scrubbing corrupts real content, which is worse than leaving a watermark in place."""
    assert scrub_hidden(text) == text, f"{label} was modified by scrub_hidden"
    assert count_hidden(text) == 0, f"{label} reported {count_hidden(text)} hidden chars"


@pytest.mark.parametrize(
    "label,char",
    [("ZWSP", "\u200B"), ("bidi RLO", "\u202E"), ("em space", "\u2003"),
     ("hangul filler", "\u3164"), ("cyrillic homoglyph", "\u0430"), ("none", "")],
)
def test_count_is_zero_exactly_when_scrub_is_a_no_op(label, char):
    """The invariant that matters, stated directly.

    "How many hidden characters are there" and "what does the scrubber remove" are two answers to
    the same question, and they have drifted apart repeatedly \u2014 three separate carrier classes went
    missing from count_hidden one at a time. Pinning each class individually did not stop the next
    one; pinning the equivalence does.
    """
    text = f"The build{char} succeeded on the first try."
    assert (count_hidden(text) == 0) == (scrub_hidden(text) == text), (
        f"{label}: count_hidden says {count_hidden(text)} but scrub_hidden "
        f"{'changed' if scrub_hidden(text) != text else 'did not change'} the text"
    )


class TestScrubDoesNotDestroyNonLatinProse:
    """`scrub_hidden` folds confusables to ASCII. Unscoped, that ate whole languages.

    MEASURED before the fix — the defensive path, run on text the user cares about:

        "Это очень простой текст про кота."  ->  "Этo oчeнь пpocтoй тeкcт пpo кoтa."
        "Αυτό είναι ένα απλό κείμενο."       ->  "Ayτό eίvai έva aπλό keίμevo."

    Mixed-script garbage, from a function documented as leaving visible text alone.
    """

    def test_russian_prose_is_untouched(self):
        text = "Это очень простой текст про кота."
        assert scrub_hidden(text) == text

    def test_greek_prose_is_untouched(self):
        text = "Αυτό είναι ένα απλό κείμενο."
        assert scrub_hidden(text) == text

    def test_serbian_prose_is_untouched(self):
        """Includes "је" — a whole word made only of confusables. Its own letters cannot tell you
        what it is; the surrounding document can, and that document is Cyrillic."""
        text = "Ово је обичан текст."
        assert scrub_hidden(text) == text

    def test_a_greek_word_quoted_inside_english_survives(self):
        text = "The word περί means about."
        assert scrub_hidden(text) == text

    def test_an_intruder_inside_a_latin_word_is_still_folded(self):
        assert scrub_hidden("This pаper is about wοrds.") == "This paper is about words."

    def test_an_all_confusable_word_inside_english_is_still_folded(self):
        """The costume covers a whole word: every letter of "cocoa" has a Cyrillic lookalike."""
        assert scrub_hidden("I like сосоа in winter.") == "I like cocoa in winter."

    def test_the_documented_hole_is_the_documented_hole(self):
        """An all-confusable word with no Latin context around it is indistinguishable from the
        real Cyrillic word, and is left alone. Asserted so the limit is a decision, not a surprise."""
        assert scrub_hidden("сосоа") == "сосоа"
