"""Deleting a sentence was the one defect class the zero-dependency path could not see.

The complementary-gates table pins a rejecting case for numbers, polarity, certainty, roles,
contradiction and similarity. It has no column for the entailment floor, and that turned out to be
the interesting one: **deletion is the only defect the floor catches alone.**

MEASURED, dropping sentences from a three-sentence paragraph:

    candidate         sim     entailment   contradiction   NLI verdict   similarity-only
    drop 1 of 3     0.949        0.0015         0.007        rejected       ADMITTED
    drop 2 of 3     0.897        0.0014         0.009        rejected       ADMITTED
    half a clause   0.761        0.0012         0.021        rejected       ADMITTED

A third of the document removed scores **0.949** against a 0.76 bar and contradicts nothing, because
a truncation asserts nothing to contradict. Every gate but entailment passes it, and the entailment
floor needs the NLI stack — so on the advertised zero-dependency default it was admitted.

This is not hypothetical: the pipeline now contains a transform that removes whole sentences.

Word count separates the cases where similarity does not — counted in WORDS, not as a ratio, and
that correction is the design. A ratio floor of 0.80 looked clean against 445 corpus-length rewrites
(min 0.902) and BROKE THE LOOP on a 24-word input, where removing "Moreover," and "it is important
to note that" — the actual job — costs 25% of the document. Filler is roughly constant in words and
documents are not.

Re-measured as words lost, over 223 genuine rewrites from all three free rewriters:

    source length     n     max lost   median lost
        0-40 words    18        5           1
      120-400 words  205        9           0

against 12, 26 and 36 for the three deletions. A rewrite may lose the larger of 10 words and 10% of
the document.

**The margin is one word.** Largest legitimate loss 9, smallest caught deletion 12. A dropped
sentence of ten words or fewer is not separable from aggressive filler removal by length alone; no
constants fix that, because the populations genuinely touch. This buys sentence-scale deletion on
the path with no model to catch it.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import (
    deletion_allowance,
    meaning_preserved,
    words_lost,
)
from untell.scripts.quality import similarity

SOURCE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed. "
    "Most councils mix it with grit so the surface also gains traction."
)

DROP_ONE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed."
)
DROP_TWO = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter."
)
FAITHFUL = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to around minus nine degrees, past which other chemicals are needed. "
    "Most councils mix it with grit so the road also grips better."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _preserved(candidate: str) -> bool:
    return meaning_preserved(SOURCE, candidate, similarity(SOURCE, candidate), 0.76)


def test_the_similarity_gate_would_admit_a_dropped_sentence() -> None:
    """The premise, and the reason this file exists. If similarity ever started catching this, the
    guard below would be untested rather than unnecessary — so the number is asserted, not assumed."""
    assert similarity(SOURCE, DROP_ONE) >= 0.76, "premise: similarity must find this faithful"


@pytest.mark.parametrize("candidate", [DROP_ONE, DROP_TWO], ids=["drop one", "drop two"])
def test_a_dropped_sentence_is_rejected(candidate: str) -> None:
    assert not _preserved(candidate)


def test_a_faithful_paraphrase_of_the_same_length_survives() -> None:
    """Guards the guard, and this is not theoretical: the first version of this check used a ratio
    and made `test_the_rewrite_actually_did_something` fail — every candidate rejected, so the loop
    returned the source unchanged. A guard that rejects real work is worse than the hole it fills."""
    assert words_lost(SOURCE, FAITHFUL) <= deletion_allowance(SOURCE)
    assert _preserved(FAITHFUL)

def test_short_input_may_lose_its_filler() -> None:
    """The case the ratio version broke. Removing "Moreover," and "it is important to note that"
    from a 24-word paragraph is the job, and it costs a quarter of the document."""
    short = (
        "Moreover, the framework leverages a robust approach to deliver outcomes at scale. "
        "Furthermore, it is important to note that this significantly enhances efficiency overall."
    )
    trimmed = (
        "The setup leans on a strong approach to deliver outcomes at scale. "
        "This sharply improves efficiency."
    )
    assert words_lost(short, trimmed) <= deletion_allowance(short)


def test_an_unchanged_candidate_loses_nothing() -> None:
    assert words_lost(SOURCE, SOURCE) == 0


def test_growth_is_never_penalised() -> None:
    """The floor is one-sided on purpose: expanding a contraction or unpacking a nominalisation adds
    words and loses nothing.

    Scoped to the ratio rather than to `meaning_preserved`, because a longer candidate is not
    automatically faithful — appending a new claim is fabrication, and the entailment and certainty
    gates are right to reject it. A first version asserted the whole conjunction and failed for that
    reason, which is the correct behaviour of a different gate."""
    grown = SOURCE + " It is also cheap, which is why it stays in use."
    assert words_lost(SOURCE, grown) < 0
    assert words_lost(SOURCE, grown) <= deletion_allowance(SOURCE)


def test_the_allowance_sits_between_the_two_measured_populations() -> None:
    """223 real rewrites lose at most 9 words; the mildest deletion loses 12. An allowance outside
    that one-word gap either stops catching deletions or starts rejecting real work."""
    assert 9 <= deletion_allowance(SOURCE) < 12


def test_the_check_runs_without_nli(monkeypatch) -> None:
    """The whole point. With the NLI stack unavailable the entailment floor cannot run, and this
    was the path that admitted every row of the table above."""
    import untell.scripts.entailment as entailment

    monkeypatch.setattr(entailment, "available", lambda: False)
    assert not _preserved(DROP_ONE)
    assert _preserved(FAITHFUL), "and it must still admit faithful work on that path"
