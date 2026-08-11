"""The parenthesiser closed its bracket on a comma inside the aside, not at the end of it.

`_ASIDE_RE` excludes commas from the aside body, so when the real aside contains one the pattern
matches a PREFIX and brackets that. FOUND by reading loop output on HC3:

    one called melanin, which gives your skin, hair, and eyes their color, and another called...
      -> one called melanin (which gives your skin) hair, and eyes their color, and another...

"gives your skin", then a dangling "hair, and eyes their color". The transform is documented to
change punctuation and nothing else, and the meaning gates agree with that documentation — no word
is added, removed or reordered, so cosine, NLI and semantic roles all pass a sentence that has been
cut in half. Nothing in the repo could see this but a reader.

The tell is what follows the closing comma: a serial list continues with more items and a
coordinator, where a real aside end is followed by the sentence resuming.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import _ASIDE_RE, _LIST_CONTINUES_RE, _parenthesise_asides

DRAWS = 40

# Real HC3 sentences, and the shapes that separate the bug from the transform.
CUTS_A_LIST = [
    "The iris contains two types of pigment: one called melanin, which gives your skin, hair, "
    "and eyes their color, and another called lipochrome.",
    "They stock produce, such as apples, oranges, and pears, so the shelves stay full.",
    "We tested several models, including BERT, RoBERTa, and T5, before choosing one.",
]

GENUINE_ASIDE = [
    "The color of your eyes is determined by the amount of pigments in your iris, which is the "
    "colored part of your eye, and by the way that the iris scatters light.",
    "We evaluate the model, which is trained on public data, before deployment.",
]


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_parenthesise_asides(text))
    return out


@pytest.mark.parametrize("text", CUTS_A_LIST, ids=lambda t: t[:30])
def test_a_truncated_list_is_never_bracketed(text: str) -> None:
    assert _outputs(text) == {text}, "the bracket closed inside the aside"


@pytest.mark.parametrize("text", GENUINE_ASIDE, ids=lambda t: t[:30])
def test_a_real_aside_still_converts(text: str) -> None:
    """Guards the guard. Rejecting everything passes the test above and deletes the transform —
    and this one is load-bearing: humans use parentheses 2-4x as often as AI in both corpora, which
    is the entire reason it exists."""
    match = _ASIDE_RE.search(text)
    assert match, "premise: this fixture must still match the aside pattern"
    assert not _LIST_CONTINUES_RE.match(text, match.end()), "the guard rejects a genuine aside"


def test_the_guard_reads_what_follows_not_the_body() -> None:
    """The distinction the fix rests on, checked directly rather than through the budget draw.

    Both fixtures match `_ASIDE_RE` with a short body. What separates them is entirely in the text
    after the closing comma: more list items and a coordinator, versus the sentence resuming.
    """
    bug = CUTS_A_LIST[0]
    good = GENUINE_ASIDE[0]
    for text, expected in ((bug, True), (good, False)):
        match = _ASIDE_RE.search(text)
        assert match, text
        assert bool(_LIST_CONTINUES_RE.match(text, match.end())) is expected, (
            f"{text[match.end():match.end() + 30]!r} judged wrongly"
        )


def test_a_bracketed_output_keeps_every_word() -> None:
    """What the transform promises: punctuation changes, nothing else. The bug broke this promise
    without removing a word, which is why the meaning gates missed it — so check the sequence, not
    the multiset."""
    text = GENUINE_ASIDE[0]
    for out in _outputs(text) - {text}:
        stripped = out.replace("(", "").replace(")", "").replace(",", "").split()
        assert stripped == text.replace(",", "").split(), out
