"""No meaning gate may depend on WHERE in the document a change happens.

Two of the five gates did. Both are transformer-backed, both truncate their input, and both were
therefore scoring only the front of a long document while reporting a verdict about all of it:

    entailment   a negation 143 words in scored 0.0179 — the value for two IDENTICAL strings
    similarity   a whole sentence replaced 280 words in scored 1.0000 — likewise identical

Neither was a threshold being slightly wrong. The changed text was never fed to the model, so no
bar could have caught it, and the gates were most confident exactly where they were most blind.

The other three (roles, hedges, numerals) were probed the same way and are position-independent to
552 words, which is why they are here too: this file is not a regression test for two bugs, it is
the invariant. A gate added later that reads a fixed-size prefix fails here on its first run.

The shape of every test is the same and it is the shape that matters — identical edit, identical
document length, only the position differs. That isolates truncation from every other reason a
score might move, which a single long-document assertion would not.
"""

from __future__ import annotations

import pytest

from untell.scripts import entailment, quality
from untell.scripts.hedges import certainty_kept
from untell.scripts.numerals import numbers_kept
from untell.scripts.roles import role_swap
from untell.text_split import CHUNK_WORDS, aligned_chunks

# Five sentences, ~35 words. Repeated to push the edit past any plausible truncation point.
FILLER = (
    "The study was conducted at three sites over eighteen months. Recruitment followed the "
    "published protocol. Data collection used the standard instrument. Analysts were blinded "
    "to allocation throughout. The statistical plan was registered in advance. "
)

# reps -> roughly 8, 76, 144, 280, 552 words
REPETITIONS = [0, 2, 4, 8, 16]


def _at_start(pad: str, sentence: str) -> str:
    return sentence + " " + pad if pad else sentence


def _at_end(pad: str, sentence: str) -> str:
    return pad + sentence


class TestPositionDoesNotDecideTheVerdict:
    """A boolean gate must return the same answer wherever the edit sits."""

    @pytest.mark.parametrize("reps", REPETITIONS)
    def test_roles_catches_a_swap_anywhere(self, reps):
        pad = FILLER * reps
        a = "The company sued the regulator over the ruling."
        b = "The regulator sued the company over the ruling."
        assert role_swap(_at_start(pad, a), _at_start(pad, b)) is True
        assert role_swap(_at_end(pad, a), _at_end(pad, b)) is True

    @pytest.mark.parametrize("reps", REPETITIONS)
    def test_hedges_catches_a_dropped_hedge_anywhere(self, reps):
        pad = FILLER * reps
        a = "The results may indicate a possible link between the two variables."
        b = "The results indicate a link between the two variables."
        assert certainty_kept(_at_start(pad, a), _at_start(pad, b)) is False
        assert certainty_kept(_at_end(pad, a), _at_end(pad, b)) is False

    @pytest.mark.parametrize("reps", REPETITIONS)
    def test_numerals_catches_a_changed_number_anywhere(self, reps):
        pad = FILLER * reps
        a = "The study enrolled 240 participants over three years."
        b = "The study enrolled 420 participants over three years."
        assert numbers_kept(_at_start(pad, a), _at_start(pad, b)) is False
        assert numbers_kept(_at_end(pad, a), _at_end(pad, b)) is False


class TestScoringGatesDoNotDependOnPosition:
    """The two model-backed gates return a float, so the invariant is a bounded difference rather
    than equality — the same edit genuinely does score a little differently in different contexts.
    The tolerance is set well below the failures it exists to catch: entailment differed by 0.96
    and similarity by 0.14 (against a 0.24-wide margin to the bar)."""

    TOLERANCE = 0.35

    @pytest.mark.parametrize("reps", REPETITIONS)
    def test_entailment_contradiction_is_position_independent(self, reps):
        if not entailment.available():
            pytest.skip("NLI stack unavailable")
        pad = FILLER * reps
        a = "The treatment improved outcomes in the trial."
        b = "The treatment did not improve outcomes in the trial."
        at_start = entailment.contradiction_score(_at_start(pad, a), _at_start(pad, b))
        at_end = entailment.contradiction_score(_at_end(pad, a), _at_end(pad, b))
        assert abs(at_start - at_end) < self.TOLERANCE, (
            f"{len((pad + a).split())} words: {at_start:.4f} at the start, {at_end:.4f} at the end"
        )
        assert at_end >= entailment.DEFAULT_CONTRADICTION_BAR, (
            f"inversion at the end of a {len((pad + a).split())}-word document scored "
            f"{at_end:.4f}, under the {entailment.DEFAULT_CONTRADICTION_BAR} bar"
        )

    @pytest.mark.parametrize("reps", REPETITIONS)
    def test_similarity_is_position_independent(self, reps):
        pad = FILLER * reps
        a = "The intervention halved mortality among the treated cohort."
        b = "Cats are pleasant animals and many people enjoy their company."
        at_start = quality.similarity(_at_start(pad, a), _at_start(pad, b))
        at_end = quality.similarity(_at_end(pad, a), _at_end(pad, b))
        assert abs(at_start - at_end) < self.TOLERANCE, (
            f"{len((pad + a).split())} words: {at_start:.4f} at the start, {at_end:.4f} at the end"
        )

    def test_a_replaced_sentence_is_never_scored_as_identical(self):
        """The single sharpest symptom: 1.0000 means the text was not read, not that it matched."""
        pad = FILLER * 16
        a, b = (
            "The intervention halved mortality among the treated cohort.",
            "Cats are pleasant animals and many people enjoy their company.",
        )
        assert quality.similarity(pad + a, pad + b) < 0.99


class TestTheChunkingItself:
    def test_short_input_is_a_single_chunk(self):
        """Chunking must be a no-op below the threshold, or every short-input measurement in this
        repo silently changed meaning when the fix landed."""
        a, b = "The cat sat on the mat.", "A cat was sitting on the mat."
        assert aligned_chunks(a, b) == [(a, b)]

    def test_long_input_is_split(self):
        long_a = FILLER * 8
        assert len(aligned_chunks(long_a, long_a)) > 1

    def test_no_chunk_greatly_exceeds_the_budget(self):
        """A chunk far over the budget would be truncated again, reintroducing the bug inside the
        fix."""
        long_a = FILLER * 16
        for ca, cb in aligned_chunks(long_a, long_a):
            assert len(ca.split()) <= CHUNK_WORDS * 2, f"chunk of {len(ca.split())} words"
            assert len(cb.split()) <= CHUNK_WORDS * 2

    def test_alignment_survives_an_inserted_sentence(self):
        """Proportional splitting drifted once the rewriter changed sentence lengths, and the gate
        then compared text that never corresponded — which produced false vetoes on faithful
        rewrites. Cut points come from difflib for this reason."""
        source = " ".join(f"Sentence number {n} states a fact about the system." for n in range(30))
        shifted = "An extra opening sentence appears here first. " + source
        chunks = aligned_chunks(source, shifted)
        assert len(chunks) > 1
        for src_chunk, out_chunk in chunks[1:]:
            opening = " ".join(src_chunk.split()[:6])
            assert opening in out_chunk, (
                f"chunk drifted: source starts {opening!r}, rewrite chunk is {out_chunk[:80]!r}"
            )

    def test_both_model_gates_use_the_same_helper(self):
        """Two copies of an alignment rule is how they drift apart. The similarity fix only worked
        because the entailment one had already been measured."""
        import inspect

        for module in (entailment, quality):
            assert "aligned_chunks" in inspect.getsource(module), (
                f"{module.__name__} does not use the shared chunking helper"
            )
