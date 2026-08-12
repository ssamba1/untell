"""Two of the eight meaning checks do all the vetoing, and both need an optional model.

Asked of 49 genuine rewrites from `structural`, `surgical` and `composite` over 20 HC3 and RAID
documents, evaluating every gate separately rather than as a conjunction:

    numerals 0    certainty 0    polarity 0    similarity 0
    contradiction 1    role_swap 2    entailment 0

The six zeros are not dead code — they are insurance against a rewriter the free path does not have.
`meaning_preserved` already records the same finding for polarity in its own comment: "0 of 30 HC3
and 0 of 30 RAID loop results change their negation count, because the rewriter's transforms are
substitutions, merges and splits — none of which touches polarity."

**The part worth pinning is what the two live gates cost on a lean install.** All three vetoed
candidates scored similarity 0.969, 0.981 and 0.981 against a 0.76 bar, so without NLI and spaCy the
conjunction admits **3 of 3** — and at a similarity no reader would find suspicious.

So `meaning_gate: "similarity-only"` is not a partially-degraded gate on this evidence. On measured
corpus output it is a gate that has never rejected anything.

This file does not re-run the corpus sweep; it pins the two properties that make the number
meaningful — that the fallback really is `sim >= strict_bar`, and that a candidate at 0.98
similarity passes it whatever the model-backed checks think.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import RELAXED_SIM_BAR, meaning_preserved
from untell.scripts.quality import recommended_bar

SOURCE = "The new build runs faster than the previous one on every machine we tested it on."
INVERTED = "The new build runs slower than the previous one on every machine we tested it on."


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_fallback_is_similarity_against_the_strict_bar(monkeypatch) -> None:
    """With the model gone, the whole conjunction reduces to one comparison. Pinned because the
    lean-install number depends entirely on which bar that is — the relaxed 0.30 would admit
    everything, and it is the strict bar that applies here."""
    import untell.scripts.entailment as ent

    monkeypatch.setattr(ent, "available", lambda: False)
    bar = recommended_bar()
    assert meaning_preserved(SOURCE, INVERTED, sim=bar + 0.01, strict_sim_bar=bar)
    assert not meaning_preserved(SOURCE, INVERTED, sim=bar - 0.01, strict_sim_bar=bar)


def test_a_high_similarity_inversion_passes_the_fallback(monkeypatch) -> None:
    """The measured shape of the loss: the three real vetoes sat at 0.969-0.981, which is well
    inside the range a caller reads as 'obviously fine'."""
    import untell.scripts.entailment as ent

    monkeypatch.setattr(ent, "available", lambda: False)
    for sim in (0.969, 0.981):
        assert meaning_preserved(SOURCE, INVERTED, sim=sim, strict_sim_bar=recommended_bar())


def test_the_mechanical_checks_still_run_without_the_model(monkeypatch) -> None:
    """Guards the guard, and the reason the mode is called "similarity-only" rather than "off": a
    numeral change is still caught with no NLI at all."""
    import untell.scripts.entailment as ent

    monkeypatch.setattr(ent, "available", lambda: False)
    changed_number = SOURCE.replace("every machine", "three machines")
    assert not meaning_preserved(
        "The new build runs faster on 12 machines we tested.",
        "The new build runs faster on 30 machines we tested.",
        sim=0.99,
        strict_sim_bar=recommended_bar(),
    ), changed_number


def test_the_relaxed_bar_is_only_reachable_with_the_model() -> None:
    """0.30 is a gross-topic-drift floor that only makes sense when contradiction and entailment are
    doing the fidelity work. If the fallback ever started using it, the lean install would admit
    essentially everything and this file's numbers would understate the loss."""
    assert RELAXED_SIM_BAR < recommended_bar()
