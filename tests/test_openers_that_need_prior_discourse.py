"""Three openers in the pool assert a relation to text that has not been written yet.

FOUND by running the loop on human prose at default settings — the case a user is in when a
detector has accused their own writing and they reach for this tool. The output began:

    In short, my grandmother kept every birthday card anyone ever sent her, in a shoebox, in
    date order, and when she died we found forty years of them.

"In short," announces a compression of what came before. It is the first sentence of the document;
nothing precedes it. The passage reads as though a paragraph went missing above it, and the tell
catalogue scores the opening 0, so nothing downstream sees it.

MEASURED over 100 rewrites of 4 documents at 25 seeds each: 4 opened a document with a marker of
this kind. After the guard, 0 do for the three screened, and the two that remain are "Actually,",
which is attested document-initially in ordinary speech and writing and is deliberately kept.

The pool was already screened twice — every member is frequency-attested in human text and none is
a catalogued tell — and openers that assert RECENCY or SEQUENCE ("recently", "then", "so") were
declined outright for exactly this reason, that the meaning gates do not check discourse relations.
These three are fine everywhere except one position, so they are screened by position rather than
removed.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import _NEEDS_PRIOR_DISCOURSE, _OPENERS, StructuralRewriter
from untell.scripts.score import score_text

DOCS = [
    "My grandmother kept every birthday card anyone ever sent her, in a shoebox, in date order. "
    "When she died we found forty years of them. Half were from people none of us could place.",
    "The oven has been dead since March. I keep meaning to call someone about it and then I do not. "
    "The toaster oven does most of what I need, so roast chicken is off the menu for now.",
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes. "
    "Furthermore, it underscores the pivotal integration of modern methodologies at scale.",
    "The study examined soil carbon across eleven sites over four years. Results varied by depth. "
    "The deepest cores held the most, which nobody involved had expected at the outset.",
]
SEEDS = range(25)


def _rewrites(doc: str) -> list[str]:
    rw = StructuralRewriter()
    scored = score_text(doc, tier="lite")
    out = []
    for seed in SEEDS:
        random.seed(seed)
        out.append(rw.rewrite(doc, scored, 0.30))
    return out


def test_the_screened_openers_are_still_in_the_pool() -> None:
    """They are screened by POSITION, not removed. A pool that lost them would pass every test
    below while giving up three frequency-attested openers the transform needs for variety."""
    assert _NEEDS_PRIOR_DISCOURSE
    for opener in _NEEDS_PRIOR_DISCOURSE:
        assert opener in _OPENERS, f"{opener} was removed from the pool rather than positioned"


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d.split()[0] + "-" + d.split()[1])
def test_no_block_opens_with_a_marker_that_needs_prior_discourse(doc: str) -> None:
    offenders = [
        (seed, out[:80])
        for seed, out in zip(SEEDS, _rewrites(doc))
        if any(out.lstrip().startswith(o) for o in _NEEDS_PRIOR_DISCOURSE)
    ]
    assert not offenders, f"opened with a marker that presupposes prior text: {offenders}"


def test_the_transform_still_reaches_the_first_sentence() -> None:
    """Guards the guard. Declining three of nine openers must steer the choice, not block it — a
    transform that stopped touching first sentences entirely would pass the test above.
    """
    seen = set()
    for doc in DOCS:
        for out in _rewrites(doc):
            head = out.lstrip()
            for opener in _OPENERS:
                if head.startswith(opener):
                    seen.add(opener)
    allowed = set(_OPENERS) - set(_NEEDS_PRIOR_DISCOURSE)
    assert seen & allowed, (
        "no permitted opener ever reached a block's first sentence across 100 rewrites; the guard "
        "is blocking the transform rather than steering it"
    )


def test_the_screened_openers_can_still_appear_later_in_a_document() -> None:
    """The cost of the guard, asserted rather than assumed. `apply_per_block` hands the transform a
    bare string with no block index, so the finest available distinction is first-of-block — but
    within a block, a later sentence must still be able to take one.
    """
    doc = (
        "The study examined soil carbon across eleven sites over four years. "
        "Results varied by depth across every site measured in the survey. "
        "The deepest cores held the most, which nobody involved had expected. "
        "The team repeated the measurement twice before publishing anything at all. "
        "The finding held on both repeats and across all eleven of the sites."
    )
    rw = StructuralRewriter()
    scored = score_text(doc, tier="lite")
    later = 0
    for seed in range(60):
        random.seed(seed)
        out = rw.rewrite(doc, scored, 0.30)
        body = out.lstrip()
        for opener in _NEEDS_PRIOR_DISCOURSE:
            # anywhere but position 0
            if opener in body and not body.startswith(opener):
                later += 1
                break
    assert later > 0, (
        "the screened openers never appear anywhere in 60 rewrites, so they have been removed in "
        "effect rather than positioned"
    )
