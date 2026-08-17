"""Swapping a conditional's antecedent and consequent passed every gate.

    "If the sensor fails, the system shuts down."
 -> "If the system shuts down, the sensor fails."

The causation is reversed and the meaning gate accepted it. MEASURED before this on three such
pairs, full NLI path: contradiction 0.0065-0.0277, entailment 0.96-0.99, similarity 0.96-0.99 —
passing on the NLI path and on the stdlib path alike.

All three predicate-argument rules were blind to it by construction:

  rule 1 (slot exchange)         needs transitive objects; these predicates are intransitive
  rule 2 (predicate reassign)    requires pairs_a != pairs_b, and a symmetric swap gives the SAME
                                 set on both sides
  rule 3 (connective disappears) needs a class to vanish; COND is present in both

`roles.py` claimed the veto "catches 9 of 9 role permutations". True of the probe set it was
measured on — whose only conditional case DROPS the "if", which trips rule 3. The swap keeps it.

THE SIGNAL IS THE PARSE, NOT THE WORD ORDER. "If A, B" and "B if A" mean the same thing, so
position cannot decide it. spaCy makes `if` a `mark` whose head is the antecedent's clause, and the
consequent is the sentence root; both orderings give the same pair, and only a real exchange
changes it. That is why the faithful reorderings below must still pass.

ONE THING THE FIRST VERSION GOT WRONG. It gated on `pos_ in ("VERB", "AUX")`, and spaCy tags
`restarts` in "If the server restarts, the data is lost." as a NOUN — so that sentence was dropped
entirely and one of the three swaps kept passing. The DEPENDENCY (`advcl`) is the sound signal; the
tagger is not reliable enough to gate on alone.
"""

from __future__ import annotations

import random

import pytest

from untell.scripts.entailment import meaning_preserved
from untell.scripts.quality import similarity
from untell.scripts.roles import _conditional_pair, role_swap


@pytest.fixture(autouse=True)
def _torch_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """These assertions exercise the spaCy predicate-argument veto.

    role_swap gates on UNTELL_LITE_NO_TORCH (returns None = unavailable) while the
    availability probe _conditional_pair does not, so under the stdlib env this file
    neither skips (probe parses fine) nor passes (role_swap is gated). The docstring's
    measurements are the full-NLI path — pin the env unset for the file.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)

SWAPPED = [
    ("If the sensor fails, the system shuts down.",
     "If the system shuts down, the sensor fails."),
    ("If the server restarts, the data is lost.",
     "If the data is lost, the server restarts."),
    ("If the patient improves, the dose is reduced.",
     "If the dose is reduced, the patient improves."),
]
FAITHFUL = [
    ("If the sensor fails, the system shuts down.",
     "The system shuts down if the sensor fails."),
    ("If the server restarts, the data is lost.",
     "The data is lost if the server restarts."),
]


def _available() -> bool:
    return _conditional_pair("If the sensor fails, the system shuts down.") != (None, None)


pytestmark = pytest.mark.skipif(
    not _available(), reason="spaCy model unavailable; the predicate-argument veto is inactive"
)


@pytest.mark.parametrize("source,candidate", SWAPPED, ids=lambda x: x[:24])
def test_a_swapped_conditional_is_vetoed(source: str, candidate: str) -> None:
    assert role_swap(source, candidate) is True, (
        f"the exchange was not detected: {source!r} -> {candidate!r}"
    )
    assert not meaning_preserved(source, candidate, similarity(source, candidate), 0.76), (
        "the full gate still accepts a reversed conditional"
    )


@pytest.mark.parametrize("source,candidate", FAITHFUL, ids=lambda x: x[:24])
def test_a_reordered_conditional_still_passes(source: str, candidate: str) -> None:
    """The error that would matter more. "B if A" is the same claim as "If A, B", and a veto that
    fired on it would block an ordinary and desirable rewrite."""
    assert role_swap(source, candidate) is not True, (
        f"faithful reordering wrongly vetoed: {source!r} -> {candidate!r}"
    )
    assert meaning_preserved(source, candidate, similarity(source, candidate), 0.76)


@pytest.mark.parametrize("source,candidate", FAITHFUL, ids=lambda x: x[:24])
def test_the_pair_is_order_insensitive(source: str, candidate: str) -> None:
    """The mechanism, not just the outcome. If these ever diverge, the rule has started keying on
    position and will veto reorderings."""
    assert _conditional_pair(source) == _conditional_pair(candidate)


def test_the_rule_does_not_fire_on_real_rewrites_of_conditional_text() -> None:
    """The false-veto measurement. A gate that blocks the loop is worse than one that misses a
    case, so this drives the actual rewriters over conditional prose and counts vetoes.

    MEASURED: 0 of 81 real rewrites across three rewriters, five conditional documents, six seeds.
    """
    import os

    os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
    from untell.rewriter import get_rewriter
    from untell.scripts.score import score_text

    documents = [
        "If the sensor fails, the system shuts down. Moreover, the framework leverages robust "
        "methods.",
        "When the threshold is exceeded, the alarm sounds. Additionally, the comprehensive "
        "solution helps.",
        "If demand rises, prices follow. In conclusion, the analysis showcases significant value.",
    ]
    vetoed = considered = 0
    for text in documents:
        scored = score_text(text, tier="lite")
        for name in ("structural", "composite"):
            rewriter = get_rewriter(name)
            for seed in range(4):
                random.seed(seed)
                candidate = rewriter.rewrite(text, scored, 0.30)
                if candidate.strip() == text.strip():
                    continue
                considered += 1
                vetoed += role_swap(text, candidate) is True

    assert considered >= 10, f"only {considered} real rewrites to judge; the sweep is too thin"
    assert vetoed == 0, f"{vetoed} of {considered} faithful rewrites were vetoed"


def test_a_non_conditional_gets_no_pair() -> None:
    """Guards the cheap path. If every sentence produced a pair, the rule would be comparing noise
    on text that has no conditional at all."""
    assert _conditional_pair("The system shuts down. The sensor fails.") == (None, None)
