"""Unicode-tricks branches the main tables miss: the empty-char guard, orphan variation
selectors, scripted format marks, homoglyph folding of mixed words, combining-mark
composition, and the scrubber's per-move character accounting.
"""

from __future__ import annotations

from untell.attacks import unicode_tricks as u


class TestVariationSelectors:
    def test_empty_char_is_not_emoji_adjacent(self):
        # `_is_emoji_adjacent` is called with a possibly-empty predecessor; the guard must
        # answer False rather than index into nothing.
        assert u._is_emoji_adjacent("") is False

    def test_orphan_variation_selector_is_dropped(self):
        # A VS16 after a plain letter is not joined to an emoji and not part of a keycap, so
        # it is hidden text with nothing to decorate: removed.
        assert u._strip_orphan_variation_selectors("a\uFE0F b") == "a b"

    def test_variation_selector_after_an_emoji_is_kept(self):
        assert u._strip_orphan_variation_selectors("\U0001F600\uFE0F") == "\U0001F600\uFE0F"

    def test_variation_selector_before_a_keycap_is_kept(self):
        # "1\uFE0F\u20E3" is the keycap emoji sequence; the selector here is part of it.
        assert u._strip_orphan_variation_selectors("1\uFE0F\u20E3") == "1\uFE0F\u20E3"


class TestScriptedMarks:
    def test_orphan_scripted_format_mark_is_removed(self):
        # U+0600 (ARABIC NUMBER SIGN) with no Arabic text around it is invisible punctuation;
        # it must be scrubbed rather than left in the output.
        assert u._strip_orphan_scripted_marks("\u0600\u0601 plain") == " plain"


class TestHomoglyphs:
    def test_mixed_word_folds_the_homoglyphs_to_ascii(self):
        # A word that is mostly ASCII with a Cyrillic lookalike is a homoglyph attack on an
        # otherwise-clean word: fold the impostor to its ASCII twin.
        assert u._unhomoglyph("hello\u0430") == "helloa"

    def test_pure_native_word_is_left_alone(self):
        # All-Cyrillic text is not an attack; folding it would corrupt real content.
        assert u._unhomoglyph("\u0430\u0431\u0446") == "\u0430\u0431\u0446"


class TestCombiningMarks:
    def test_mark_after_a_base_composes(self):
        assert u._compose_legitimate("e\u0301x") == "éx"

    def test_mark_that_cannot_compose_is_kept_verbatim(self):
        # 'x' + U+0301 has no precomposed form; NFC leaves them as two characters.
        assert u._compose_legitimate("x\u0301") == "x\u0301"


class TestMarkStacks:
    def test_a_run_of_combining_marks_is_capped(self):
        # A dozen stacked combining marks is a hidden-text attack (or a paste artifact);
        # the default cap (_MAX_MARK_STACK = 4) applies.
        assert u._strip_mark_stacks("a" + "\u0301" * 12) == "a" + "\u0301" * 4

    def test_a_lower_keep_cap_is_honoured(self):
        assert u._strip_mark_stacks("a" + "\u0301" * 12, keep=1) == "a" + "\u0301"


class TestAffectedCharsAccounting:
    """The scrubber's source-vs-output walk must count deletions/substitutions but treat an
    insertion as the scrubber ADDING a character (no source char was touched)."""

    def test_inserted_character_touches_no_source_character(self):
        assert u._affected_chars("a", "ab") == 0
        assert u._affected_chars("ab", "xab") == 0  # insertion at the front

    def test_deleted_trailing_character_is_counted(self):
        assert u._affected_chars("abc", "ab") == 1

    def test_a_deletion_mid_string_is_counted(self):
        assert u._affected_chars("ax", "x") == 1
        assert u._affected_chars("ab", "x") == 2

    def test_substituted_characters_are_counted(self):
        assert u._affected_chars("ab", "xb") == 1
        assert u._affected_chars("abcd", "xbc") == 2

    def test_the_resync_fallback_still_counts(self):
        # 'xabb' vs 'xbxbx' forces the walk's fallback move (substitution tied with the other
        # resync options); the affected count must stay a real number, not a crash or a guess.
        assert u._affected_chars("xabb", "xbxbx") == 2
