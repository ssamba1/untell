"""A fronted adverbial with no main clause after it is a fragment, and one word decides which.

FOUND at `best_of=3` over five iterations — the settings a real user runs, and enough transforms
firing for it to appear at all:

    ...condone the assassination of any individual, regardless of their actions or beliefs.
      ->  ...condone the assassination of any individual.
          Regardless of their actions or beliefs.

`_CANNOT_OPEN_A_CLAUSE` already holds seventeen prepositions, `regarding` among them. `regardless`
was missed, and the whole family with it.

It cannot simply be added to that set, because that set is unconditional and these leads are the one
family where the same word opens a fragment AND a sentence:

    Regardless of their actions or beliefs.        fragment
    Regardless of the cost, we proceed.            sentence

What separates them is whether a main clause follows, and a fronted adverbial that has one is
separated from it by a comma. Checked on ten pairs — a fragment and a sentence for each of five
leads — the comma rule splits all ten correctly.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import (
    _CANNOT_OPEN_A_CLAUSE,
    _NEEDS_A_MAIN_CLAUSE,
    _cannot_start_a_sentence,
    _split_one,
)

LEFT = "The committee met on Tuesday and reviewed the whole proposal in detail"

FRAGMENTS = [
    "Regardless of their actions or beliefs.",
    "Despite these potential downsides.",
    "Notwithstanding the delay.",
    "Unlike the previous version.",
    "Throughout the whole period.",
]
SENTENCES = [
    "Regardless of the cost, we proceed with the plan.",
    "Despite the rain, we walked to the shop anyway.",
    "Notwithstanding the delay, the team shipped on time.",
    "Unlike the previous version, this one is fast.",
    "Throughout the period, costs rose steadily each quarter.",
]


@pytest.mark.parametrize("right", FRAGMENTS, ids=lambda s: s.split()[0])
def test_a_fronted_adverbial_alone_is_blocked(right: str) -> None:
    assert _cannot_start_a_sentence(right, LEFT) is True


@pytest.mark.parametrize("right", SENTENCES, ids=lambda s: s.split()[0])
def test_the_same_lead_with_a_main_clause_is_allowed(right: str) -> None:
    """Guards the guard, and it is the whole reason this is a separate set. Adding these leads to
    `_CANNOT_OPEN_A_CLAUSE` would block a legitimate split on every one of them."""
    assert _cannot_start_a_sentence(right, LEFT) is False


def test_the_two_sets_do_not_overlap() -> None:
    """An entry in both would be unconditionally blocked, which silently undoes the comma rule and
    would look like it still worked — every fragment test above would still pass."""
    assert not (_NEEDS_A_MAIN_CLAUSE & _CANNOT_OPEN_A_CLAUSE), (
        _NEEDS_A_MAIN_CLAUSE & _CANNOT_OPEN_A_CLAUSE
    )


def test_the_reported_sentence_no_longer_splits_into_a_fragment() -> None:
    """End to end on the sentence that produced it.

    This asserted the fragment shape behind `if halves is None: continue`, and `_split_one`
    declines this source on every seed — so the assertion never ran and the test could not fail.
    Proven vacuous by mutation: replacing the assert with `assert False` still passed.

    Declining IS the protection. The guard exists so a comma-boundary split that would strand
    "regardless of their actions or beliefs" as its own sentence is refused, and refusing is what
    that looks like from outside. So the refusal is what gets asserted, and the fragment shape is
    kept as a second assertion for the day the splitter starts accepting this source again.
    """
    source = (
        "It is generally not acceptable or ethical to advocate for or condone the assassination "
        "of any individual, regardless of their actions or beliefs."
    )
    accepted = 0
    for seed in range(20):
        random.seed(seed)
        halves = _split_one(source)
        if halves is None:
            continue
        accepted += 1
        right = halves[1].strip()
        assert not (right.lower().startswith("regardless") and "," not in right), (
            f"seed {seed}: {right!r}"
        )
    assert accepted == 0, (
        "the splitter now accepts this source; the assertion above became live, which is fine — "
        "but this line documents that the behaviour changed and should be re-read"
    )


def test_a_clean_boundary_still_splits() -> None:
    """The transform has to keep working — the guard is a refusal, and refusals accumulate."""
    source = (
        "Crews worked through the night to clear the main roads across the county, the side "
        "streets were left untreated until the following afternoon."
    )
    assert any(_split_one(source) is not None for _ in [random.seed(s) for s in range(20)])
