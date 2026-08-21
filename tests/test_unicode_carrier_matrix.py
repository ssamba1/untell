"""Unicode adversarial carrier matrix — Wave 7 Slice 11.

Three questions per carrier:
  (a) does scrub_hidden / count_hidden remove and count it?
  (b) is it reported correctly even in edge contexts (lone surrogate, RTL smuggling)?
  (c) does it survive lock() / restore() round-trip in free text and in locked spans?

Prior result to build on (from memory note "Neutral-transform invariance"):
    U+00A0 took human text 5/10 → 9/10 flagged and hid 2 of 5 tells.
    That measured the DETECTOR impact; this file measures the SCRUB/LOCK paths.
"""

from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden
from untell.scripts.preserve import lock, restore

# ---------------------------------------------------------------------------
# Carrier matrix: every class from the task specification
# ---------------------------------------------------------------------------

_BASE = "This study found a significant effect on cognitive performance."

# (name, codepoint). The list covers every carrier class the task names.
CARRIER_MATRIX = [
    # zero-width / invisible joiners
    ("ZWSP U+200B", "​"),
    ("ZWNJ U+200C", "‌"),
    ("ZWJ  U+200D orphan", "‍"),  # ZWJ between plain letters = orphan
    ("WORD JOINER U+2060", "⁠"),
    ("BOM U+FEFF", "﻿"),
    # space-like
    ("SOFT HYPHEN U+00AD", "­"),
    ("NBSP U+00A0", " "),
    ("NARROW NBSP U+202F", " "),
    ("FIGURE SPACE U+2007", " "),
    # bidi controls (all 12 that the scrubber handles)
    ("LRM U+200E", "‎"),
    ("RLM U+200F", "‏"),
    ("LRE U+202A", "‪"),
    ("RLE U+202B", "‫"),
    ("PDF U+202C", "‬"),
    ("LRO U+202D", "‭"),
    ("RLO U+202E", "‮"),   # Trojan Source / right-to-left override
    ("LRI U+2066", "⁦"),
    ("RLI U+2067", "⁧"),
    ("FSI U+2068", "⁨"),
    ("PDI U+2069", "⁩"),
    # homoglyph
    ("Cyrillic 'a' U+0430 in Latin word", "а"),
    # lone surrogate — the gap this test file was written to close
    ("Lone surrogate U+D800", "\ud800"),
]


@pytest.mark.parametrize("name,carrier", CARRIER_MATRIX, ids=[c[0] for c in CARRIER_MATRIX])
class TestCarrierMatrixScrub:
    """(a) scrub_hidden removes the carrier and count_hidden counts it."""

    def test_scrub_removes_carrier(self, name, carrier):
        text = _BASE[:30] + carrier + _BASE[30:]
        assert scrub_hidden(text) != text, f"{name}: survived scrub_hidden"

    def test_count_is_one(self, name, carrier):
        text = _BASE[:30] + carrier + _BASE[30:]
        assert count_hidden(text) == 1, (
            f"{name}: count_hidden returned {count_hidden(text)}, expected 1"
        )

    def test_count_zero_on_clean_base(self, name, carrier):
        assert count_hidden(_BASE) == 0, f"{name}: base text is not clean"


@pytest.mark.parametrize("name,carrier", CARRIER_MATRIX, ids=[c[0] for c in CARRIER_MATRIX])
class TestCarrierMatrixLockRestore:
    """(c) lock() / restore() round-trip with carriers in FREE TEXT.

    lock() / restore() is NOT a scrubber. Its job is to preserve locked spans
    byte-for-byte. Carriers in free text survive the round-trip exactly, and a
    subsequent scrub_hidden call removes them — that is the correct order of operations.
    """

    def test_carrier_survives_lock_restore_in_free_text(self, name, carrier):
        """A carrier in free (non-locked) text rides through lock/restore unchanged.

        This is EXPECTED: the pipeline is scrub → lock → rewrite → restore, so
        free-text carriers are removed before locking. Testing that lock/restore itself
        is transparent (the round-trip is faithful) is the load-bearing assertion.
        """
        text = _BASE[:30] + carrier + _BASE[30:]
        try:
            masked, mapping = lock(text)
            restored = restore(masked, mapping)
        except Exception as exc:
            pytest.fail(f"{name}: lock/restore raised {exc!r}")

        # Lone surrogate is the one carrier lock() already sanitises internally
        # (it replaces surrogates before collecting spans so spaCy doesn't crash).
        if "\ud800" <= carrier <= "\udfff":
            assert carrier not in restored, f"{name}: surrogate survived lock()/restore()"
        else:
            assert restored == text, (
                f"{name}: round-trip changed the text\n"
                f"before: {text!r}\nafter:  {restored!r}"
            )

    def test_carrier_inside_locked_span_survives_restore(self, name, carrier):
        """A carrier INSIDE a locked span (e.g., a citation) comes back after restore().

        lock() is a byte-faithful preserver — it locks the span verbatim, including any
        carrier embedded in a citation, formula, or quoted phrase. That is the contract.
        If the pipeline needs to clean carriers from locked spans it must scrub AFTER
        restore().
        """
        # Embed the carrier inside a quotation, which the citation pattern locks.
        text = 'The results (Smith' + carrier + ', 2020) were significant.'
        try:
            masked, mapping = lock(text)
            restored = restore(masked, mapping)
        except Exception as exc:
            pytest.fail(f"{name}: lock/restore raised {exc!r}")

        # lone surrogates are sanitised inside lock() before pattern matching
        if "\ud800" <= carrier <= "\udfff":
            return  # surrogate already handled by lock(); no further assertion needed

        any_in_mapping = any(carrier in v for v in mapping.values())
        # Some carriers sit between citation components and end up in the locked span;
        # others may not be swallowed by the citation pattern at all. Either way the
        # total carrier count is either preserved (in mapping) or still in free text.
        assert carrier in restored, (
            f"{name}: carrier disappeared entirely from restore() output\n"
            f"mapping values: {list(mapping.values())}"
        )


# ---------------------------------------------------------------------------
# Lone surrogate: the specific gap this slice found and fixed
# ---------------------------------------------------------------------------

class TestLoneSurrogateHandling:
    """Lone surrogates (U+D800..U+DFFF) are invalid Unicode scalar values.

    MEASURED before this fix: scrub_hidden('hello\\ud800world') returned the input
    unchanged and count_hidden reported 0 — the worst possible outcome (told clean,
    carrier still present). The fix adds a lone-surrogate strip as the first pass of
    scrub_hidden.
    """

    @pytest.mark.parametrize("cp", [0xD800, 0xD900, 0xDFFF])
    def test_lone_surrogate_is_stripped(self, cp):
        ch = chr(cp)
        text = "hello" + ch + "world"
        assert ch not in scrub_hidden(text), f"U+{cp:04X} survived scrub_hidden"

    @pytest.mark.parametrize("cp", [0xD800, 0xD900, 0xDFFF])
    def test_lone_surrogate_is_counted(self, cp):
        ch = chr(cp)
        text = "hello" + ch + "world"
        assert count_hidden(text) == 1, (
            f"U+{cp:04X}: count_hidden returned {count_hidden(text)}, expected 1"
        )

    def test_high_and_low_surrogate_both_stripped(self):
        text = "a" + chr(0xD800) + "b" + chr(0xDC00) + "c"
        cleaned = scrub_hidden(text)
        assert chr(0xD800) not in cleaned
        assert chr(0xDC00) not in cleaned

    def test_surrogate_count_matches_quantity(self):
        text = "x" + chr(0xD801) + "y" + chr(0xDFFE) + "z"
        assert count_hidden(text) == 2

    def test_clean_text_not_affected(self):
        """No surrogate → no change. Regression guard."""
        plain = "The quick brown fox jumps over the lazy dog."
        assert scrub_hidden(plain) == plain
        assert count_hidden(plain) == 0

    def test_lock_also_sanitises_surrogates(self):
        """lock() independently sanitises lone surrogates before the NER pass.

        This is a separate guard: the lock() code comment documents this was a
        measured UnicodeEncodeError crash in spaCy. scrub_hidden's fix is not
        the only defence; lock()'s sanitisation is belt-AND-braces.
        """
        text = "The study (Smith, 2020) found \ud800 significant results."
        masked, mapping = lock(text)
        restored = restore(masked, mapping)
        assert chr(0xD800) not in restored


# ---------------------------------------------------------------------------
# BiDi carrier smuggling — documented known limitation
# ---------------------------------------------------------------------------

class TestBidiCarrierSmuggling:
    """A single RTL character causes _strip_orphan_bidi to preserve ALL bidi controls.

    MEASURED: 'Access GRANTED \\u202eDENIED \\u0645' — the Arabic 'م' (U+0645) at the
    end makes _strip_orphan_bidi see RTL content and return the text unchanged, so the
    RLO (U+202E) survives and count_hidden reports 0 (text is told clean).

    This is the Trojan Source vector: the text READS one way and IS another. An
    attacker who controls input text can smuggle an RLO through the scrubber by appending
    one Arabic character, making the terminal display differ from the byte sequence.

    FILED as a GitHub issue (search: "bidi carrier smuggling via single RTL character").
    The scrubber's contract — keep bidi controls that may be doing RTL layout work — is
    correct for genuine mixed-script documents. The weakness is that "any RTL character"
    is a coarser test than "bidi controls adjacent to RTL content". Fixing this requires
    a full Unicode bidi algorithm, which is out of scope for this slice.

    These tests PIN the current behaviour so any change to the bidi path is a conscious
    decision, not an accidental regression.
    """

    RLO = "‮"          # RIGHT-TO-LEFT OVERRIDE — the Trojan Source character
    ARABIC_M = "م"     # Arabic letter meem — one real RTL character

    def test_rlo_in_pure_latin_is_stripped(self):
        """Baseline: no RTL content → RLO is always removed."""
        text = "Access GRANTED " + self.RLO + "DENIED"
        assert self.RLO not in scrub_hidden(text)
        assert count_hidden(text) == 1

    def test_rlo_survives_when_single_rtl_char_present(self):
        """KNOWN LIMITATION: one Arabic character causes RLO to survive in Latin text.

        This is the smuggling attack. The test pins the behaviour so it cannot change
        silently. If this assertion ever fails (RLO is correctly stripped even with a
        stray Arabic char), the security posture improved and the test should be updated
        to reflect the stronger guarantee.
        """
        text = "Access GRANTED " + self.RLO + "DENIED " + self.ARABIC_M
        scrubbed = scrub_hidden(text)
        # RLO survives because _strip_orphan_bidi sees the Arabic char and preserves all controls.
        assert self.RLO in scrubbed, (
            "RLO was stripped even with a stray Arabic char present — the smuggling path "
            "is no longer exploitable (update this test to document the stronger guarantee)"
        )
        # count_hidden reports 0 because nothing was changed.
        assert count_hidden(text) == 0, (
            "count_hidden should report 0 when the scrubber makes no change "
            "(the text was told clean even though it contains RLO)"
        )

    def test_rlo_in_genuine_arabic_document_is_preserved(self):
        """In real Arabic text bidi controls are load-bearing and must survive."""
        arabic_text = "مرحبا " + self.RLO + " عالم"
        scrubbed = scrub_hidden(arabic_text)
        assert self.RLO in scrubbed, "RLO stripped from genuine Arabic text (over-scrub)"

    def test_bidi_smuggling_in_lock_restore(self):
        """The smuggled RLO also survives lock() / restore() because scrub_hidden says clean."""
        text = "The result was APPROVED " + self.RLO + "REJECTED " + self.ARABIC_M
        masked, mapping = lock(text)
        restored = restore(masked, mapping)
        # The RLO rides through the round-trip intact.
        assert self.RLO in restored, (
            "RLO disappeared from lock/restore — unexpected, scrub was not called"
        )


# ---------------------------------------------------------------------------
# Carrier interactions: multiple carriers at once
# ---------------------------------------------------------------------------

class TestMultipleCarriers:
    """count_hidden counts all affected source characters, not just distinct types."""

    def test_two_zwsp_count_as_two(self):
        text = "a​b​c"
        assert count_hidden(text) == 2

    def test_mixed_carrier_types_count_correctly(self):
        # NBSP rewritten to space (1), ZWSP deleted (1): two affected source chars
        text = "a b​c"
        assert count_hidden(text) == 2

    def test_lone_surrogate_plus_zwsp_count_as_two(self):
        text = "a\ud800b​c"
        assert count_hidden(text) == 2

    def test_homoglyph_plus_invisible_count_correctly(self):
        # Cyrillic 'a' in Latin word (1) + ZWSP (1)
        text = "pаper​"
        assert count_hidden(text) == 2
