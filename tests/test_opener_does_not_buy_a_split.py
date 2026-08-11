"""A discourse marker is not content, and the minimum-side rule was counting it.

`_MIN_SPLIT_SIDE` exists to stop a fronted adverbial becoming its own sentence. A marker that
`_vary_openers` prepended inflates the word count by exactly enough to get past it. FOUND in a
corpus sweep, as the one `stub_sentence` on RAID that was not the known truncated-source artefact:

    In this paper, we present a new method...            -> refused, "In this paper" is 3 words
    Put simply, in this paper, we present a new method   -> "Put simply, in this paper."

Three content words either way. One pass fragmenting the output of the pass before it — the same
shape the `"Of course."` comment beside `_split_one` already records, one marker further along.

The battery strips these before judging a fragment (`_strip_our_opener`). The splitter that produces
them was counting them.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import (
    _MIN_SPLIT_SIDE,
    _content_word_count,
    _split_long_sentences,
    _split_one,
)

WITH_MARKER = (
    "Put simply, in this paper, we present a new method for interactive segmentation of images."
)
WITHOUT_MARKER = (
    "In this paper, we present a new method for interactive segmentation of complex images."
)
REAL_BOUNDARY = (
    "Crews worked through the night to clear the main roads across the county, the side streets "
    "were left untreated until the following afternoon."
)


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        (["Put", "simply,", "in", "this", "paper"], 3),
        (["In", "this", "paper"], 3),
        (["Of", "course,", "the", "model"], 2),
        (["Crews", "worked", "through", "the", "night"], 5),
        ([], 0),
    ],
    ids=lambda x: str(x)[:30],
)
def test_the_marker_does_not_count(words: list[str], expected: int) -> None:
    assert _content_word_count(words) == expected


def test_the_marker_cannot_buy_a_split() -> None:
    """The two sentences differ only by a prepended marker, so they must split the same way."""
    for seed in range(20):
        random.seed(seed)
        with_marker = _split_one(WITH_MARKER)
        random.seed(seed)
        without = _split_one(WITHOUT_MARKER)
        assert (with_marker is None) == (without is None), (
            f"seed {seed}: the marker changed the decision — {with_marker!r} vs {without!r}"
        )


def test_no_half_is_a_stranded_opener() -> None:
    for seed in range(20):
        random.seed(seed)
        halves = _split_one(WITH_MARKER)
        if halves is None:
            continue
        assert _content_word_count(halves[0].split()) >= _MIN_SPLIT_SIDE, halves


def test_a_real_boundary_still_splits() -> None:
    """Guards the guard. Counting content words must not make every left half too short — the
    minimum is about the sentence, and a marker is the only thing discounted."""
    split_somewhere = False
    for seed in range(20):
        random.seed(seed)
        if _split_one(REAL_BOUNDARY) is not None:
            split_somewhere = True
            break
    assert split_somewhere, "a clean comma boundary is no longer splittable"


def test_the_other_splitter_counts_the_same_way() -> None:
    """These two functions have now been found with the same hole three times over; the fourth
    would be this one."""
    for seed in range(20):
        random.seed(seed)
        for part in _split_long_sentences([WITH_MARKER], max_words=8, rate=1.0):
            for sentence in part.split(". "):
                if sentence.strip():
                    assert _content_word_count(sentence.split()) >= 2, part


def test_the_name_does_not_collide() -> None:
    """`structural` already had a `_content_words` returning a SET of words. Defining a second
    function with that name returning an int shadowed it, and `_drop_restatements` began raising
    `TypeError: object of type 'int' has no len()` — caught by a corpus sweep crashing, not by any
    test. Both names now exist and mean different things, which is only safe while they differ.
    """
    from untell.rewriter import structural

    assert structural._content_words("the model works well") == {"model", "works", "well"} or (
        isinstance(structural._content_words("the model works well"), set)
    )
    assert isinstance(structural._content_word_count(["the", "model"]), int)
