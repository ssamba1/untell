"""Killing tests for mutation survivors in `untell/attacks/unicode_tricks.py`.

Each test here pins a behaviour that a mutation sweep found unpinned: the sweep breaks one
line at a time (comparison flipped, boolean swapped, constant nudged) and watches the suite;
every test below is written so that it FAILS against the named mutation and PASSES against
the original. They are deliberately narrow — one mutation per test where possible — so a
failure localises the broken line.

Fixtures follow the sibling module's convention: every invisible character is built with
``chr()``, never pasted and never a ``\\u`` escape, so the source itself carries nothing a
transport can silently strip.

The mutation each test kills is named in its docstring as ``module:line``, matching the
harvested candidate list (``python .claude/mutate.py untell/attacks/unicode_tricks.py --list``).
"""

from __future__ import annotations

from untell.attacks.unicode_tricks import (
    _affected_chars,
    _compose_legitimate,
    _strip_mark_stacks,
    _strip_orphan_scripted_marks,
    _strip_orphan_variation_selectors,
    _strip_orphan_zwj,
    _unhomoglyph,
    count_hidden,
    homoglyph_substitute,
    scrub_hidden,
)

ZWJ = chr(0x200D)  # zero-width joiner
VS16 = chr(0xFE0F)  # variation selector 16
KEYCAP = chr(0x20E3)  # combining enclosing keycap
ACUTE = chr(0x0301)  # combining acute accent


class TestEmojiAdjacency:
    """`_is_emoji_adjacent` (lines 104-112): each range boundary and each `or` arm.

    The adjacency heuristic decides whether a ZWJ/variation selector is structural (kept)
    or an orphan carrier (dropped). Every mutation in the predicate flips exactly one
    boundary or one arm; each test holds a character at the mutated boundary between two
    ZWJs and asserts the ZWJ survives.
    """

    def test_leading_zwj_before_an_emoji_is_an_orphan(self):
        # unicode_tricks.py:104  constant: False -> True  (empty-string guard)
        # A leading ZWJ has no left neighbour, so it joins nothing even when the right
        # neighbour is an emoji. The mutated guard would call it "adjacent" and keep it.
        assert scrub_hidden(ZWJ + chr(0x1F600)) == chr(0x1F600)

    def test_zwj_joins_two_pictographs_at_the_lower_bound(self):
        # unicode_tricks.py:107  boundary: <= -> <   (0x1F000)
        # unicode_tricks.py:108  logic: or -> and    (0x1F1E6 arm)
        # o = 0x1F000 is the first pictographic codepoint; the mutated `<=` excludes it
        # and the mutated `or` chains the next arm onto it, so both make the pair
        # "not emoji" and the ZWJ between them becomes an orphan.
        text = chr(0x1F000) + ZWJ + chr(0x1F000)
        assert _strip_orphan_zwj(text) == text

    def test_zwj_joins_two_regional_indicators_at_the_lower_bound(self):
        # unicode_tricks.py:108  boundary: <= -> <   (0x1F1E6, flag indicators)
        text = chr(0x1F1E6) + ZWJ + chr(0x1F1E6)
        assert _strip_orphan_zwj(text) == text

    def test_zwj_joins_two_misc_symbols_at_the_lower_bound(self):
        # unicode_tricks.py:109  boundary: <= -> <   (0x2600)
        # unicode_tricks.py:109  logic: or -> and    (0x2600 arm)
        # unicode_tricks.py:110  logic: or -> and    (0x2300 arm, via the chained `and`)
        text = chr(0x2600) + ZWJ + chr(0x2600)
        assert _strip_orphan_zwj(text) == text

    def test_zwj_joins_two_misc_technical_chars_at_the_lower_bound(self):
        # unicode_tricks.py:110  boundary: <= -> <   (0x2300)
        text = chr(0x2300) + ZWJ + chr(0x2300)
        assert _strip_orphan_zwj(text) == text

    def test_zwj_joins_two_variation_selectors_at_the_lower_bound(self):
        # unicode_tricks.py:111  boundary: <= -> <   (0xFE00)
        # unicode_tricks.py:111  logic: or -> and    (0xFE00 arm)
        text = chr(0xFE00) + ZWJ + chr(0xFE00)
        assert _strip_orphan_zwj(text) == text

    def test_zwj_joins_two_emoji_modifier_symbols(self):
        # unicode_tricks.py:112  logic: or -> and    (final `or o in (...)` arm)
        text = chr(0x2640) + ZWJ + chr(0x2640)
        assert _strip_orphan_zwj(text) == text


class TestVariationSelectors:
    """`_strip_orphan_variation_selectors` (lines 144-154)."""

    def test_trailing_variation_selector_is_dropped_without_crashing(self):
        # unicode_tricks.py:152  boundary: < -> <=   (`i + 1 < len(text)`)
        # A VS as the last character is an orphan. The mutated bound reads `text[i + 1]`
        # at the end of the string, which is out of range — the scrubber must not crash.
        assert _strip_orphan_variation_selectors("a" + VS16) == "a"

    def test_variation_selector_before_a_keycap_is_kept(self):
        # unicode_tricks.py:153  logic: != -> ==   (`nxt != _KEYCAP`)
        # Keycap emoji are [0-9#*] + VS16 + U+20E3: the selector sits after a plain digit
        # but is structural. The mutated equality treats it as an orphan and strips it.
        text = "1" + VS16 + KEYCAP
        assert _strip_orphan_variation_selectors(text) == text

    def test_variation_selector_after_an_emoji_base_is_kept(self):
        # unicode_tricks.py:153  logic: and -> or   (`not _is_emoji_adjacent(prev) and ...`)
        # prev is emoji, so the first conjunct is False and only the `and` keeps the VS.
        text = chr(0x2600) + VS16 + "b"
        assert _strip_orphan_variation_selectors(text) == text


class TestScriptedFormatMarks:
    """`_strip_orphan_scripted_marks` (line 204)."""

    def test_arabic_text_keeps_its_own_format_marks(self):
        # unicode_tricks.py:204  logic: and -> or
        # The mark is stripped only when its script is ABSENT after removal. In real
        # Arabic the script survives, so the `and` is what protects the mark; the mutated
        # `or` strips it out of genuine Arabic prose.
        text = "\u0628\u0633\u0645 \u0627\u0644\u0644\u0647 \u0627\u0644\u0631\u062d\u0645\u0646 \u0627\u0644\u0631\u062d\u064a\u0645 " + chr(0x06DD)
        assert _strip_orphan_scripted_marks(text) == text

    def test_arabic_format_mark_is_stripped_from_pure_ascii(self):
        # Baseline for the guard above: in a Latin-only sentence the same mark is a carrier.
        assert _strip_orphan_scripted_marks("hello " + chr(0x06DD)) == "hello "


class TestMarkStacks:
    """`_strip_mark_stacks` (lines 217, 259)."""

    def test_mark_stack_is_capped_at_four(self):
        # unicode_tricks.py:217  constant: 4 -> 5   (_MAX_MARK_STACK)
        # A five-mark payload on one base is a carrier; the bumped cap would keep it.
        assert _strip_mark_stacks("a" + ACUTE * 5) == "a" + ACUTE * 4

    def test_a_stack_of_exactly_four_marks_is_kept(self):
        # unicode_tricks.py:259  boundary: > -> >=   (`run > keep`)
        # Four is the documented legitimate depth; the mutated `>=` drops the fourth mark.
        assert _strip_mark_stacks("a" + ACUTE * 4) == "a" + ACUTE * 4


class TestOrphanZwj:
    """`_strip_orphan_zwj` (lines 278-288)."""

    def test_zwj_between_letters_is_an_orphan(self):
        # unicode_tricks.py:280  membership: not in -> in   (early return guard)
        text = "ab" + ZWJ + "cd"
        assert _strip_orphan_zwj(text) == "abcd"

    def test_plain_letters_are_never_dropped_as_zwj(self):
        # unicode_tricks.py:284  logic: == -> !=   (`ch == ZWJ`)
        # The mutated equality matches every character and drops every non-emoji neighbour.
        assert _strip_orphan_zwj("abc") == "abc"

    def test_zwj_between_two_emoji_is_structural(self):
        # unicode_tricks.py:284  logic: and -> or   (`not (adj(prev) and adj(nxt))`)
        text = chr(0x1F600) + ZWJ + chr(0x1F600)
        assert _strip_orphan_zwj(text) == text

    def test_lone_zwj_is_dropped_without_crashing(self):
        # unicode_tricks.py:286  boundary: < -> <=   (`i + 1 < len(text)`)
        # Reads `text[i + 1]` past the end under the mutation.
        assert _strip_orphan_zwj(ZWJ) == ""

    def test_zwj_between_emoji_and_letter_is_an_orphan(self):
        # unicode_tricks.py:286  logic: and -> or   (`adj(prev) and adj(nxt)`)
        text = chr(0x1F600) + ZWJ + "a"
        assert _strip_orphan_zwj(text) == chr(0x1F600) + "a"


class TestScrubPasses:
    """The scrub_hidden pipeline (lines 319, 328)."""

    def test_line_separator_is_mapped_to_a_real_newline(self):
        # unicode_tricks.py:319  constant: 10 -> 11   (chr(10) -> chr(11))
        text = "a" + chr(0x2028) + "b"
        assert scrub_hidden(text) == "a\nb"

    def test_tab_survives_the_control_character_pass(self):
        # unicode_tricks.py:328  logic: or -> and   (`ch in "\\t\\n\\r" or category != "Cc"`)
        # Tab is whitespace that must survive; the mutated `and` drops it because its
        # category is Cc.
        assert scrub_hidden("a\tb") == "a\tb"

    def test_c0_control_characters_are_stripped(self):
        # unicode_tricks.py:328  logic: != -> ==   (`category(ch) != "Cc"`)
        # The mutated equality keeps C0 controls as if they were layout characters.
        assert scrub_hidden("a" + chr(0x01) + "b") == "ab"


class TestUnhomoglyph:
    """`_unhomoglyph` (lines 366-379): the Latin-vs-native evidence and word folding."""

    def test_non_letters_do_not_join_the_latinness_evidence(self):
        # unicode_tricks.py:368  logic: and -> or   (`ch.isalpha() and ...`)
        # The mutated `or` lets a non-letter (an Arabic-Indic digit) into the evidence,
        # dragging the ASCII ratio below 0.8 and leaving an all-confusable word unfolded.
        assert _unhomoglyph("x" + chr(0x0661) + "y \u043e\u0440\u0435") == (
            "x" + chr(0x0661) + "y ope"
        )

    def test_native_letters_keep_russian_out_of_the_latin_branch(self):
        # unicode_tricks.py:368  logic: or -> and   (`ch.isascii() or ch not in _UNHOMOGLYPH`)
        # The mutated `and` excludes native Cyrillic letters from the evidence, so one
        # stray ASCII 'x' makes the document "mostly ASCII" and folds real Cyrillic words.
        assert _unhomoglyph("\u042d\u0442\u043e\u0442 x \u043e\u0440\u0435 \u0442\u0435\u043a\u0441\u0442.") == (
            "\u042d\u0442\u043e\u0442 x \u043e\u0440\u0435 \u0442\u0435\u043a\u0441\u0442."
        )

    def test_confusables_do_not_vote_on_latinness(self):
        # unicode_tricks.py:368  membership: not in -> in
        # The mutated membership counts every confusable in the evidence, so a document
        # of ten Cyrillic 'a's plus ASCII dips below 0.8 and the all-confusable word
        # stays Cyrillic instead of folding.
        assert _unhomoglyph(chr(0x0430) * 10 + " abcdef \u0430\u0430\u0430") == (
            "aaaaaaaaaa abcdef aaa"
        )

    def test_exactly_eighty_percent_is_still_latin(self):
        # unicode_tricks.py:369  boundary: >= -> >   (0.8 threshold)
        # 4 ASCII of 5 evidence letters is exactly 0.8; the mutated `>` rejects it.
        assert _unhomoglyph("abcd\u0444 \u043e\u0440\u0435") == "abcd\u0444 ope"

    def test_no_letters_does_not_divide_by_zero(self):
        # unicode_tricks.py:369  logic: and -> or   (`bool(evidence) and ratio >= 0.8`)
        # With no letters the evidence list is empty and the mutated `or` evaluates the
        # ratio anyway — a division by zero crash on ordinary punctuation.
        assert _unhomoglyph("12345") == "12345"

    def test_punctuation_inside_a_word_is_not_a_native_letter(self):
        # unicode_tricks.py:376  logic: and -> or   (`ch.isalpha() and not ch.isascii() ...`)
        # The mutated `or` makes any non-letter count as "native", so a word with a
        # confusable plus punctuation is never folded.
        assert _unhomoglyph("p\u0430per!") == "paper!"

    def test_a_confusable_letter_is_not_native(self):
        # unicode_tricks.py:376  membership: not in -> in
        # The mutated membership declares a confusable to be a native letter, which
        # blocks the fold of an otherwise all-ASCII word.
        assert _unhomoglyph("p\u0430per") == "paper"

    def test_ascii_plus_native_letter_is_not_folded(self):
        # unicode_tricks.py:377  logic: and -> or   (`any(ascii) and not native`)
        # A word with both an ASCII letter and a native Cyrillic letter is real text;
        # the mutated `or` folds its confusables anyway.
        assert _unhomoglyph("p\u0430\u043f\u0435\u0440") == "p\u0430\u043f\u0435\u0440"

    def test_all_confusable_word_is_kept_in_a_non_latin_document(self):
        # unicode_tricks.py:379  logic: and -> or   (`mostly_ascii and alpha and all(...)`)
        # Inside Russian prose an all-confusable word is a real word; the mutated `or`
        # folds it because the later conjuncts hold.
        assert _unhomoglyph("\u042d\u0442\u043e \u043e\u0447\u0435\u043d\u044c \u043e\u0440\u0435 \u0442\u0435\u043a\u0441\u0442.") == (
            "\u042d\u0442\u043e \u043e\u0447\u0435\u043d\u044c \u043e\u0440\u0435 \u0442\u0435\u043a\u0441\u0442."
        )


class TestHomoglyphSubstitute:
    """`homoglyph_substitute` (lines 389-400)."""

    def test_zero_rate_returns_text_unchanged(self):
        # unicode_tricks.py:391  boundary: <= -> <   (`rate <= 0`)
        # rate == 0 must short-circuit; the mutated `<` falls through into round(1/0).
        assert homoglyph_substitute("abc", 0.0) == "abc"

    def test_full_rate_substitutes_every_eligible_letter(self):
        # unicode_tricks.py:399  logic: == -> !=   (`n % period == 0`)
        # At rate 1.0 every eligible letter is on the substitution grid; the mutated
        # equality substitutes none of them.
        assert homoglyph_substitute("aaaa", 1.0) == chr(0x0430) * 4


class TestCountHidden:
    """`count_hidden` and its diff walk (lines 454, 531-558)."""

    def test_count_hidden_is_derived_from_the_scrub_diff(self):
        # unicode_tricks.py:454  logic: == -> !=   (`cleaned == base`)
        # The mutated equality returns 0 on every dirty text — the exact "told it was
        # clean while a carrier was removed" failure the function exists to prevent.
        assert count_hidden("a" + chr(0x200B) + "b") == 1

    def test_an_nbsp_rewrite_counts_as_one_affected_char(self):
        # unicode_tricks.py:531  boundary: < -> <=   (agreement loop, reads past the end)
        # unicode_tricks.py:531  logic: == -> !=    (agreement loop, counts mismatches)
        # unicode_tricks.py:531  logic: and -> or    (agreement loop, reads past the end)
        assert count_hidden("a" + chr(0x00A0) + "b") == 1

    def test_count_hidden_with_a_trailing_carrier(self):
        # unicode_tricks.py:537  logic: and -> or   (`while i < n and j < m`)
        # With the source exhausted first the mutated `or` keeps the walk alive and
        # indexes past the end of the cleaned string.
        assert count_hidden("a" + chr(0x200B)) == 1

    def test_a_mid_document_carrier_counts_one(self):
        # unicode_tricks.py:538  logic: == -> !=   (`if source[i] == cleaned[j]`)
        # The mutated inequality treats every equal pair as an edit and over-counts.
        assert count_hidden("ab" + chr(0x200B) + "c") == 1

    def test_count_hidden_with_a_mid_document_zwj(self):
        # unicode_tricks.py:555  logic: == -> !=   (`elif best == deletion`)
        # The mutated inequality skips the deletion branch and crashes into the else
        # path, indexing past the end of the cleaned string.
        assert count_hidden("a" + chr(0x200B) + "b") == 1


class TestAffectedChars:
    """Direct pins on `_affected_chars` where the diff walk's branches live.

    These pairs are reachable from `count_hidden` only in the cases the scrubber can
    actually produce (deletions and substitutions); insertion-shaped and cap-shaped
    inputs cannot come out of `scrub_hidden` at all, so the branch that handles them is
    pinned directly. Each pair is minimal: exhaustive search over a 3-letter alphabet
    found no shorter pair with a different count.
    """

    def test_affected_chars_with_a_trailing_insertion(self):
        # unicode_tricks.py:537  boundary: < -> <=   (`while i < n and j < m`)
        # i reaches n while j has not; the mutated bound indexes source[n].
        assert _affected_chars("a", "ab") == 0

    def test_affected_chars_with_a_trailing_deletion(self):
        # Baseline: source characters that are dropped off the end all count.
        assert _affected_chars("ab", "a") == 1

    def test_affected_chars_insertion_counts_no_source_chars(self):
        # unicode_tricks.py:558  logic: == -> !=   (`elif best == insertion`)
        # An insertion touches no source character; the mutated equality charges one.
        assert _affected_chars("ab", "axb") == 0

    def test_affected_chars_tie_breaks_on_remaining_length(self):
        # unicode_tricks.py:551  boundary: > -> >=   (`best > max(deletion, insertion)`)
        # unicode_tricks.py:551  logic: or -> and    (`A or B` in the tie-break)
        # unicode_tricks.py:555  logic: and -> or    (`elif best == deletion and ...`)
        # All three mutations change what a full three-way tie does: the walk must
        # resynchronise by treating it as one substitution, not charge twice.
        assert _affected_chars("a", "bba") == 0

    def test_affected_chars_substitution_when_lengths_match(self):
        # unicode_tricks.py:551  logic: == -> !=   (`best == substitution`)
        # The mutated inequality drops the length-tie clause and misaligns the walk.
        assert _affected_chars("ab", "ba") == 1

    def test_affected_chars_deletion_when_remaining_lengths_tie(self):
        # unicode_tricks.py:555  boundary: >= -> >   (`(n - i) >= (m - j)`)
        # The deletion branch needs the inclusive bound; the mutated `>` falls through
        # to the else and double-charges.
        assert _affected_chars("ab", "bx") == 1

    def test_affected_chars_or_branch_on_the_substitution_clause(self):
        # unicode_tricks.py:551  logic: and -> or   (`best == substitution and (n - i) == (m - j)`)
        # The mutated `or` makes the length clause an independent trigger and charges a
        # mismatch the walk should have consumed as an insertion.
        assert _affected_chars("aab", "bxa") == 2


class TestComposeLegitimate:
    """`_compose_legitimate` (lines 470-475)."""

    def test_leading_combining_mark_is_appended(self):
        # unicode_tricks.py:472  logic: and -> or   (`if out and category(ch) in ("Mn", "Me")`)
        # A mark at position 0 has nothing to compose with; the mutated `or` indexes
        # out[-1] on an empty buffer.
        assert _compose_legitimate(ACUTE + "a") == ACUTE + "a"

    def test_base_and_mark_compose_to_one_codepoint(self):
        # unicode_tricks.py:474  logic: == -> !=   (`len(composed) == 1`)
        # The mutated inequality leaves the pair decomposed and reports the wrong
        # baseline to count_hidden.
        assert _compose_legitimate("a" + ACUTE) == chr(0x00E1)  # á


class TestResyncWindow:
    """`_RESYNC_WINDOW` (line 485): the agreement cap that bounds the diff walk.

    The cap only changes a count when an agreement run hits it exactly AND the three-way
    max is decided by the cap rather than by the text. This pair is the minimal
    construction found: the substitution and deletion agree for exactly 64 and 65
    characters respectively, so the two window sizes resolve the tie differently.
    """

    def test_the_resync_window_resolves_a_cap_tie_exactly(self):
        # unicode_tricks.py:485  constant: 64 -> 65   (_RESYNC_WINDOW)
        source = "A" + "q" * 67 + "r" + "qqqqq" + "END"
        cleaned = "q" * 65 + "r" + "qqqt" + "qqqt" + "END"
        assert _affected_chars(source, cleaned) == 4
