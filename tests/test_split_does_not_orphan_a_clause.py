"""The splitter checked whether the RIGHT half could open a clause, never whether the left could
close one.

`_cannot_start_a_sentence` has guarded the right half for a long time. A split at the comma that
CLOSES an if-clause passes it, because the right half is a perfectly good sentence. FOUND by reading
loop output on HC3:

    These TVs can only display SD channels, so if we only had HD channels, those people wouldn't
    be able to watch TV.
      -> These TVs can only display SD channels, so if we only had HD channels.
         Those people wouldn't be able to watch TV.

A conditional with nothing conditional on it. The existing `fragment_lead` check cannot see it
either: that check reads the first word of a sentence, and this sentence begins with "These".

MEASURED after the guard, over 60 HC3 AI paragraphs rewritten by composite: 0 orphaned subordinate
clauses introduced, with 30 net new sentence terminators — so splits still happen.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import (
    _CLAUSE_OPENERS_ANYWHERE,
    _cannot_start_a_sentence,
    _orphans_a_subordinate_clause,
    _split_long_sentences,
    _split_one,
)

# (left half of a candidate split, does ending the sentence here strand a clause)
JUDGEMENTS = [
    ("These TVs can only display SD channels, so if we only had HD channels,", True),
    ("Basically, this means that if we only had HD channels,", True),
    ("Although the method is fast,", True),
    ("The system works well, because the cache is warm,", True),
    ("HD channels take up more bandwidth than SD channels,", False),
    ("It's not possible to have as many HD channels as we have SD channels,", False),
    ("We evaluate the model before deployment,", False),
    ("Revenue rose in Q1, Q2, and Q3,", False),
    ("The study ran for two full years afterwards,", False),
    ("", False),
]


@pytest.mark.parametrize(("left", "orphaned"), JUDGEMENTS, ids=lambda x: str(x)[:30])
def test_the_guard_judges_each_half(left: str, orphaned: bool) -> None:
    assert _orphans_a_subordinate_clause(left) is orphaned


def test_the_ambiguous_words_are_deliberately_absent_from_the_anywhere_set() -> None:
    """"as", "since", "while", "before", "until", "once" are prepositions at least as often as they
    are subordinators. Testing for them anywhere in a segment would reject correct splits — "as many
    HD channels as we have" is the case that motivated the split, not a fragment."""
    for word in ("as", "since", "while", "after", "before", "until", "once"):
        assert word not in _CLAUSE_OPENERS_ANYWHERE


def test_the_reported_sentence_is_no_longer_split_into_a_fragment() -> None:
    source = (
        "These TVs can only display SD channels, so if we only had HD channels, those people "
        "would not be able to watch TV."
    )
    for seed in range(20):
        random.seed(seed)
        halves = _split_one(source)
        if halves is None:
            continue
        assert not _orphans_a_subordinate_clause(halves[0]), f"seed {seed}: {halves[0]!r}"


def test_a_clean_boundary_is_still_split() -> None:
    """Guards the guard. Refusing every split would satisfy the tests above and delete a transform
    that exists because AI sentences run long."""
    source = (
        "HD channels take up more bandwidth than SD channels, so it is not possible to have as "
        "many HD channels as we currently have SD channels on the same network."
    )
    split_somewhere = False
    for seed in range(20):
        random.seed(seed)
        if _split_one(source) is not None:
            split_somewhere = True
            break
    assert split_somewhere, "a clean comma boundary is no longer splittable"


@pytest.mark.parametrize("lead", ["", "(", '"', "“", "[", "'"])
def test_leading_punctuation_does_not_hide_the_fragment(lead: str) -> None:
    """A third defect from the same read, and an interaction rather than a rule.

    `_parenthesise_asides` runs BEFORE the split is judged, so by then the aside may already carry a
    bracket and `_cannot_start_a_sentence` was reading "(which", which matches nothing in its set:

        ...pigments in your iris. (which is the colored part of your eye) and by the way...

    The guard was working and the token had changed under it — the same fragment, one character
    wider. Quotes are covered too, since the dialogue and substitution passes can also put one in
    front of a clause this pass has to judge.
    """
    left = "The color of your eyes is determined by the amount and type of pigments in your iris"
    right = f"{lead}which is the colored part of your eye and by the way that light scatters"
    assert _cannot_start_a_sentence(right, left) is True


def test_a_bracketed_clause_that_can_stand_alone_is_still_allowed() -> None:
    """Guards the guard: stripping the bracket must not make every bracketed half a fragment."""
    left = "The color of your eyes is determined by the amount and type of pigments in the iris"
    assert _cannot_start_a_sentence("(The iris scatters light across the eye)", left) is False


def test_the_other_splitter_has_the_same_guard() -> None:
    """`_split_one` and `_split_long_sentences` have carried the identical hole before, and fixing
    one of them left the fragment count unmoved because the other kept producing them."""
    long_source = (
        "These older television sets can only display standard definition channels, so if we "
        "only had high definition channels available on the network, those people would simply "
        "not be able to watch any television at all."
    )
    for seed in range(20):
        random.seed(seed)
        for sentence in _split_long_sentences([long_source], max_words=12, rate=1.0):
            assert not _orphans_a_subordinate_clause(sentence.rstrip(".!?")), (
                f"seed {seed}: {sentence!r}"
            )
