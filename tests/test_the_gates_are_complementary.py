"""Why there are five gates and not one, as a table rather than as an argument.

Each gate is tested on its own elsewhere. What nothing pinned is the claim those tests add up to:
that each defect class is caught by the gate built for it, and that **similarity alone would let
four of six through**. MEASURED:

    pair             sim    passes numbers  polarity certainty roles  contradicts
    faithful         0.877  True   True     True     True      False  False
    number changed   0.848  True   False    True     True      False  True
    negated          0.726  False  True     False    True      True*  True
    hedge dropped    0.989  True   True     True     False     False  False
    role swapped     0.988  True   True     True     True      True   False
    unrelated        0.000  False  True     True     True      False  False

A changed number scores 0.848, a dropped hedge 0.989, a swapped role 0.988. All three read as
faithful to a similarity gate, and each is a different kind of lie about the source.

The converse holds too and is the reason similarity stays: an unrelated paragraph contradicts
nothing — NLI is right to say so, rainfall does not contradict frameworks — and every other gate
passes it. Only similarity catches that one.

* `roles` on the negated pair is incidental; polarity and contradiction are what that row is for.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import contradicts
from untell.scripts.hedges import certainty_kept, polarity_kept
from untell.scripts.numerals import numbers_kept
from untell.scripts.quality import passes, similarity
from untell.scripts.roles import role_swap


@pytest.fixture(autouse=True)
def _torch_path(monkeypatch):
    """These assertions exercise model-backed paths (NER entities, the full ensemble,
    the NLI gate, the spaCy role veto). Under UNTELL_LITE_NO_TORCH=1 those paths are
    gated away (no entities, reduced ensemble, similarity-only naming, role_swap=None),
    so the file fails without meaning anything. Pin the env unset for the file.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)

FAITHFUL = (
    "The framework improves efficiency by 47% across the corpus.",
    "The setup improves efficiency by 47% across the corpus.",
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_faithful_rewrite_passes_every_gate() -> None:
    a, b = FAITHFUL
    assert passes(a, b)
    assert numbers_kept(a, b)
    assert polarity_kept(a, b)
    assert certainty_kept(a, b)
    assert not role_swap(a, b)
    assert not contradicts(a, b)


@pytest.mark.parametrize(
    ("name", "a", "b", "gate"),
    [
        (
            "a changed number",
            "The framework improves efficiency by 47% across the corpus.",
            "The setup improves efficiency by 74% across the corpus.",
            lambda a, b: not numbers_kept(a, b),
        ),
        (
            "a dropped hedge",
            "The framework may improve efficiency across the whole corpus.",
            "The framework improves efficiency across the whole corpus.",
            lambda a, b: not certainty_kept(a, b),
        ),
        (
            "a swapped role",
            "The compiler optimises the parser during every build cycle.",
            "The parser optimises the compiler during every build cycle.",
            lambda a, b: role_swap(a, b),
        ),
    ],
    ids=lambda x: str(x)[:18],
)
def test_similarity_alone_would_let_it_through(name: str, a: str, b: str, gate) -> None:
    """The argument for the conjunction. Each of these is a different lie about the source, and each
    scores high enough on similarity to look faithful."""
    assert similarity(a, b) >= 0.76, f"{name}: premise — this must LOOK faithful to similarity"
    assert passes(a, b), f"{name}: premise — the similarity gate must accept it"
    assert gate(a, b), f"{name}: the gate built for this defect did not catch it"


def test_polarity_and_contradiction_both_catch_a_negation() -> None:
    """The one class two gates cover. Recorded rather than trimmed: an inversion is the most
    damaging edit a rewriter can make, and redundancy there is the intended design."""
    a = "The framework improves efficiency across the whole corpus."
    b = "The framework does not improve efficiency across the whole corpus."
    assert not polarity_kept(a, b)
    assert contradicts(a, b)


def test_only_similarity_catches_an_unrelated_paragraph() -> None:
    """Why similarity stays. An unrelated text contradicts nothing — NLI is right that rainfall does
    not contradict frameworks — and every lexical gate passes it, because nothing was dropped or
    negated. Removing similarity for being the weakest gate would open exactly this hole.
    """
    a = "The framework improves efficiency across the whole corpus."
    b = "Rainfall in the valley was heavier than usual last September."

    assert not passes(a, b), "similarity must reject it"
    assert numbers_kept(a, b)
    assert polarity_kept(a, b)
    assert certainty_kept(a, b)
    assert not role_swap(a, b)
    assert not contradicts(a, b)
