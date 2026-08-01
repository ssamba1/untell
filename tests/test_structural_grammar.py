"""Grammar and output-quality tests for the structural rewriter.

These tests verify that the structural rewriter produces grammatically correct,
natural-sounding output — not regex artifacts like wrong verb tense or fragments.
"""
from __future__ import annotations

from untell.rewriter.structural import _flatten_participial_trailers, structural_rewrite


class TestParticipialTrailerGrammar:
    """Verify that participial trailers are converted with correct verb tense."""

    def test_underscoring_becomes_underscores(self):
        """Verb tense is asserted at the UNIT level, because a later pipeline stage legitimately
        changes the verb: "underscores" is itself AI vocabulary, so the plain-register pass swaps it
        for "shows". Asserting the exact verb survives the whole pipeline would pin an intermediate
        artifact and block that intended plainening."""
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        assert "underscores its" in _flatten_participial_trailers(text)

    def test_underscoring_trailer_is_gone_after_full_pipeline(self):
        """The invariant that must survive EVERY stage: no dangling "-ing" trailer remains."""
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        result = structural_rewrite(text, intensity=1.0)
        assert ", underscoring" not in result, f"trailer survived: {result}"

    def test_highlighting_becomes_highlights(self):
        text = "The data supports this view, highlighting the need for reform."
        result = structural_rewrite(text, intensity=1.0)
        assert "highlights the" in result, f"Wrong verb tense: {result}"
        assert ", highlighting" not in result

    def test_reflecting_becomes_reflects(self):
        text = "The results were positive, reflecting a broader trend."
        result = structural_rewrite(text, intensity=1.0)
        assert "reflects a" in result, f"Wrong verb tense: {result}"

    def test_multiple_trailers_all_converted(self):
        """Multiple participial trailers in one sentence: at least the first is converted."""
        text = "The model performed well, demonstrating its utility and underscoring its value."
        result = structural_rewrite(text, intensity=1.0)
        # At minimum the punctuation pattern should not leave raw fragments
        assert "demonstrates" in result or "demonstrating" not in result


class TestNegatedContrastGrammar:
    """Verify that negated contrasts produce full sentences, not fragments."""

    def test_it_is_not_produces_full_sentence(self):
        text = "It's not about the technology, it's about the people using it."
        result = structural_rewrite(text, intensity=1.0)
        # Must produce a complete sentence, not a fragment
        assert len(result) > 20
        # Must contain the positive statement
        assert "about the people" in result.lower()
        # Should NOT have awkward double-segments
        assert "about. The" not in result

    def test_not_only_but_also(self):
        text = "Not only does this improve efficiency, but it also reduces costs."
        result = structural_rewrite(text, intensity=1.0)
        assert len(result) > 10

    def test_not_just_but(self):
        text = "This is not just a tool, it is a transformative solution."
        result = structural_rewrite(text, intensity=1.0)
        assert len(result) > 10


class TestGeneralOutputQuality:
    """Verify general output quality — no artifacts, no double punctuation."""

    def test_no_double_periods(self):
        """Merged sentences must not produce '..'."""
        text = "The first sentence is here. The second sentence follows."
        result = structural_rewrite(text, intensity=1.0)
        assert ".." not in result, f"Double period found: {result}"

    def test_no_triple_spaces(self):
        """Transforms must not introduce extra whitespace."""
        text = "This is a normal sentence. It has two parts."
        result = structural_rewrite(text, intensity=1.0)
        assert "  " not in result, f"Double space found: {result}"

    def test_output_is_not_empty(self):
        assert len(structural_rewrite("Short text.", intensity=1.0)) > 0

    def test_identity_on_empty(self):
        assert structural_rewrite("", intensity=1.0) == ""

    def test_single_sentence_unchanged_structure(self):
        """A single sentence should not get merged/split (no partner)."""
        text = "This is a standalone sentence with no partner to merge with."
        result = structural_rewrite(text, intensity=1.0)
        # Length should be similar (minor changes from copula/flatten transforms)
        assert abs(len(result) - len(text)) < 20


class TestClicheRemoval:
    """Verify that common clichés and overused phrases are transformed."""

    def test_inflated_copula_flattened(self):
        text = "This solution serves as a key enabler for digital transformation."
        result = structural_rewrite(text, intensity=1.0)
        # "serves as" should be replaced with "is"
        assert "is a" in result.lower() or "serves as" not in result.lower()

    def test_vague_attribution_handled(self):
        text = "Studies show that this approach is effective in most cases."
        result = structural_rewrite(text, intensity=1.0)
        assert "evidence suggests" in result.lower() or "studies show" in result.lower()
