"""Tests for Unicode-level operations — scrub_hidden, homoglyph_substitute, count_hidden."""
from __future__ import annotations

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


def test_scrub_preserves_bidi_format_marks():
    """Bidi format marks (U+200E, U+200F, U+202A-U+202E) are Cf chars that carry layout meaning."""
    text = "English\u200EARabic"
    # They are Cf (format) category, not removed by the Cc filter, but not in WATERMARK_CHARS either
    assert "\u200E" in scrub_hidden(text)
