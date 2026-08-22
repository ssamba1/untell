"""Issue #53: numbers_kept reachability on the loop path, degenerate inputs, and gate symmetry.

The loop calls meaning_preserved(masked, candidate, ...) where both sides carry ⟦HZ⟧ sentinels.
preserve.py locks all 2+-digit numbers, numbers with units, dates, ranges, and other multi-part
facts, but deliberately leaves bare single digits rewritable (a lone "5" should become "five").

After SENTINEL_RE.sub(" ") inside _numbers(), a locked number vanishes from both sides and cannot
be "missing". A bare single digit survives the strip and can be dropped, which is what this check
guards against.

Summary of census results:
  numbers_kept is DEAD  for preserve.py-locked numbers (sentinels stripped on both sides).
  numbers_kept is ALIVE for bare single digits that preserve.py leaves unlocked.
  numbers_kept is ALIVE on any direct API call with unmasked text.
"""
from __future__ import annotations

import pytest

from untell.scripts.numerals import _numbers, missing_numbers, numbers_kept

# The actual sentinel character sequence: ⟦ = U+27E6, ⟧ = U+27E7
_S = "⟦HZ0001⟧"   # one locked span
_S2 = "⟦HZ0002⟧"  # a second locked span


class TestReachabilityOnLoopPath:
    """Census: numbers_kept IS reachable for bare single digits, dead for locked numbers."""

    def test_single_digit_drop_is_caught_in_masked_text(self):
        """bare '7' is not locked; dropping it from the candidate is a real veto (the case the
        module docstring describes as the original motivation for this check)."""
        masked_src = f"Only 7 of the {_S} tests passed."
        masked_cand = f"Only a few of the {_S} tests passed."
        assert "7" in missing_numbers(masked_src, masked_cand)
        assert not numbers_kept(masked_src, masked_cand)

    def test_single_digit_preserved_as_word_is_not_vetoed(self):
        """7 -> seven is a legitimate style move; numbers_kept allows it."""
        masked_src = f"Only 7 of the {_S} tests passed."
        masked_cand = f"Only seven of the {_S} tests passed."
        assert missing_numbers(masked_src, masked_cand) == []
        assert numbers_kept(masked_src, masked_cand)

    def test_locked_number_is_stripped_from_both_sides(self):
        """A sentinel erases the value on both sides; nothing can be 'missing'."""
        src = f"The {_S} patients enrolled."   # ⟦HZ0001⟧ represents e.g. "240"
        cand = f"A total of {_S} patients enrolled."
        assert _numbers(src) == []   # sentinel stripped, no digits left
        assert _numbers(cand) == []
        assert numbers_kept(src, cand)

    def test_two_locked_numbers_both_invisible(self):
        """Multiple sentinels: all stripped, gate sees empty sets on both sides."""
        src = f"From {_S} to {_S2} patients were enrolled."
        cand = f"Between {_S} and {_S2} patients took part."
        assert _numbers(src) == []
        assert _numbers(cand) == []
        assert numbers_kept(src, cand)

    def test_mixed_locked_and_bare_digit_reports_bare_only(self):
        """Locked numbers disappear; bare single digits remain visible."""
        src = f"Only 3 of the {_S} sites reported."
        cand = f"Only some of the {_S} sites reported."
        assert missing_numbers(src, cand) == ["3"]
        assert not numbers_kept(src, cand)

    def test_bare_digit_spelling_survives_across_sentinel_strip(self):
        """The same text without sentinels: bare digit is seen and matched as word."""
        assert numbers_kept("7 sites joined.", "seven sites joined.")
        assert not numbers_kept("7 sites joined.", "some sites joined.")


class TestDegenerateInputs:
    """Every gate must handle empty strings, identical text, and strict-prefix candidates."""

    def test_empty_source_and_candidate(self):
        assert numbers_kept("", "")
        assert missing_numbers("", "") == []

    def test_empty_source_nonempty_candidate(self):
        """No numbers in source -> nothing can be missing, regardless of candidate."""
        assert numbers_kept("", "The study enrolled 42 patients.")

    def test_nonempty_source_empty_candidate(self):
        """Numbers in source; candidate is empty -> all are missing."""
        src = "The study enrolled 42 patients."
        assert "42" in missing_numbers(src, "")
        assert not numbers_kept(src, "")

    def test_identical_source_and_candidate(self):
        """A text cannot drop numbers from itself."""
        text = "The trial enrolled 240 patients across 5 sites."
        assert numbers_kept(text, text)
        assert missing_numbers(text, text) == []

    def test_candidate_is_strict_prefix_drops_number_in_tail(self):
        """A prefix drops numbers that appear after the cut point."""
        src = "The trial enrolled 240 patients across 5 sites."
        prefix = "The trial enrolled 240 patients"
        # 240 is present in both; bare '5' is not in the prefix
        assert "5" in missing_numbers(src, prefix)
        assert not numbers_kept(src, prefix)

    def test_candidate_is_strict_prefix_no_tail_numbers(self):
        """A prefix that drops only words, no numbers, passes the number gate."""
        src = "The trial enrolled 240 patients, who were monitored."
        prefix = "The trial enrolled 240 patients"
        assert numbers_kept(src, prefix)

    def test_single_character_source_and_candidate(self):
        """Single-character strings: no numbers, always passes."""
        assert numbers_kept("a", "b")
        assert numbers_kept("x", "x")


class TestMeaningPreservedSymmetry:
    """meaning_preserved is directional, not symmetric.

    Adding a hedge (source->candidate) is allowed; dropping one is vetoed. Verifying
    the asymmetry mechanically, on the certainty gate which is explicitly one-directional.
    """

    def test_dropping_a_hedge_is_vetoed(self):
        """Source hedges with 'may'; candidate drops it -> gate rejects."""
        from untell.scripts.entailment import meaning_preserved

        src = "The drug may cause side effects."
        cand = "The drug causes side effects."
        # similarity is high (same words); the certainty gate is what fires
        assert not meaning_preserved(src, cand, sim=0.97, strict_sim_bar=0.76)

    def test_adding_a_hedge_is_allowed(self):
        """Source makes a firm claim; candidate is more cautious -> gate accepts."""
        from untell.scripts.entailment import meaning_preserved

        src = "The drug causes side effects."
        cand = "The drug may cause side effects."
        assert meaning_preserved(src, cand, sim=0.97, strict_sim_bar=0.76)

    def test_dropping_a_hedge_vetoed_whether_or_not_nli_is_present(self):
        """The certainty check runs before the NLI path, so lite mode still rejects it."""
        from untell.scripts.hedges import certainty_kept

        src = "The results suggest a correlation."
        cand = "The results show a correlation."
        # 'suggests' is evidential; 'show' is not in the evidential class -> dropped
        assert not certainty_kept(src, cand)
        # reverse: source has no evidential hedge -> nothing dropped
        assert certainty_kept(cand, src)

    def test_polarity_flip_is_symmetric(self):
        """polarity_kept compares counts, so it fires in both directions — documented behaviour."""
        from untell.scripts.hedges import polarity_kept

        pos = "The committee approved the plan."
        neg = "The committee did not approve the plan."
        assert not polarity_kept(pos, neg)   # negation added
        assert not polarity_kept(neg, pos)   # negation removed


class TestMeaningPreservedDegenerateInputs:
    """Degenerate inputs to the full meaning gate."""

    def test_empty_source_and_candidate_is_preserved(self):
        from untell.scripts.entailment import meaning_preserved

        assert meaning_preserved("", "", sim=1.0, strict_sim_bar=0.76)

    def test_nonempty_source_empty_candidate_is_rejected(self):
        from untell.scripts.entailment import meaning_preserved

        assert not meaning_preserved("The cat sat on the mat.", "", sim=0.0, strict_sim_bar=0.76)

    def test_identical_text_is_preserved(self):
        from untell.scripts.entailment import meaning_preserved
        from untell.scripts.quality import token_overlap

        text = "The trial enrolled 240 patients across 5 sites."
        sim = token_overlap(text, text)
        assert meaning_preserved(text, text, sim=sim, strict_sim_bar=0.76)

    def test_high_similarity_does_not_override_dropped_hedge(self):
        """Certainty check is unconditional — sim cannot rescue a candidate that drops a hedge."""
        from untell.scripts.entailment import meaning_preserved

        src = "Some studies suggest a possible link."
        cand = "Studies prove a clear link."  # dropped quantifier, modality, evidential
        # Even with artificially high sim, the gate must reject
        assert not meaning_preserved(src, cand, sim=0.99, strict_sim_bar=0.76)

    def test_below_sim_bar_alone_is_rejected_in_lite_mode(self):
        """Without NLI the sim check is the fallback; below bar -> rejected."""
        from untell.scripts.entailment import available, meaning_preserved

        if available():
            pytest.skip("NLI is available; this tests the lite fallback only")
        src = "The quick brown fox jumps over the lazy dog."
        cand = "The sun rises in the east every morning."  # unrelated topic, low sim
        from untell.scripts.quality import token_overlap
        sim = token_overlap(src, cand)
        assert sim < 0.76, f"fixture sim {sim:.3f} unexpectedly high"
        assert not meaning_preserved(src, cand, sim=sim, strict_sim_bar=0.76)
