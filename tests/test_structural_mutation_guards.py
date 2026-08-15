"""Killing tests for structural.py mutation survivors (2026-08-14 sweep, wave 1).

  line 1335 constant: 2 -> 3       "not just X but Y" split producing exactly 2 parts.
  line 1549 logic: != -> ==        register-pass substitution no-op detection.

Killed here. The other survivors (480/755/1043/1654/1678/2298/2513/2623/2789/
2853/2866/2875) are covered in wave 2 or annotated — see survivors.md.
"""

from __future__ import annotations

from untell.rewriter import structural as S


class TestFlattenNegatedContrast:
    """Survivor structural.py:1335 — `len(parts) == 2` mutated to `== 3`.

    "not just X but Y" splits on "but" into exactly 2 parts and returns the Y
    side. The mutation (== 3) never matches and returns the whole text unchanged."""

    def test_not_just_but_returns_second_side(self) -> None:
        text = "This is not just efficient but also elegant."
        out = S._flatten_negated_contrast(text)
        # the "but" split keeps the pre-"but" text; the pass returns the Y side
        assert "elegant" in out
        assert "not just" not in out

    def test_plain_text_unchanged(self) -> None:
        text = "The system is reliable."
        assert S._flatten_negated_contrast(text) == text


class TestRegisterNoOpDetection:
    """Survivor structural.py:1549 — `replaced != masked` mutated to `==`.

    When a substitution changes nothing (no grammatical form fits), the loop must
    stop — the mutated comparison treats every replacement as "unchanged" and
    breaks on the FIRST candidate, so text with a substitutable word never changes.
    Observable: a sentence containing a known AI-vocab word (e.g. "pivotal")
    must have the register pass change it."""

    def test_substitutable_word_gets_replaced(self) -> None:
        # quant-frame word: the substitution adoption loop (line 1549) must fire.
        # Original (synonym is random): "countless/scores of/many options available."
        # Mutated (==): the adoption break never fires, article agreement is lost:
        #              "There are a scores of / a many of / a countless of options."
        import re

        text = "There are a myriad of options available."
        out = S._plain_register(text)
        assert "myriad" not in out, out
        # the quant frame must not leave a stray article before its replacement
        assert not re.search(r"\ba (?:scores|many|countless) of\b", out), (
            f"broken quant frame leaked: {out!r}"
        )

    def test_no_vocab_word_unchanged(self) -> None:
        text = "The system reads the file and writes the result."
        assert S._plain_register(text) == text
