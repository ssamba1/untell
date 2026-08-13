"""The anti-repetition guard was scoped to a paragraph, so splitting a document defeated it.

FOUND by continuing to read rewriter output on line-structured input. Two transforms keep a `spent`
set to stop a many-to-one map landing on the same replacement twice — six source words offer "key",
six offer "boost", five offer "so" — and both sets were local to one call. `structural_rewrite` runs
the pipeline through `apply_per_block`, so every paragraph got a fresh set and the guard only ever
saw the block in front of it.

MEASURED on six sentences drawn from one cluster ('pivotal', 'crucial', 'vital', 'paramount',
'essential', 'salient'), 60 seeds, layout the only variable:

    one paragraph (control)   mean max-dup 1.00    0 / 60 documents repeat a replacement
    six paragraphs            mean max-dup 2.37   53 / 60
    six lines                 mean max-dup 2.37   53 / 60
    six bullets               mean max-dup 2.37   53 / 60

Same sentences, same seeds. At seed 4 the single paragraph read

    key / critical / essential / top / needed / standout

and the split one read

    key / key / key / key / needed / key

**The tell catalogue scores `repeated_phrasing` 0 for both**, so nothing downstream could see it —
the same shape as the lower-case sentence starts found in the same output: invisible to every metric
the loop has, obvious on sight.

At component level, four blocks through `_plain_register` over 200 seeds:

    four separate sets   140 / 200 documents repeat a replacement
    one shared set         0 / 200

`_vary_openers` carries the same guard and the same defect, on a much smaller denominator: 18
sentences in 3 paragraphs over 60 seeds gave 9 documents with two or more openers, of which 3 reused
one ("Put simply", "Actually", "Basically"). It inserts about one opener per document, so the
opportunities to collide are rare — the risk is not small, the denominator is. Both are now owned by
the document.
"""

from __future__ import annotations

import logging
import random
import re
from collections import Counter

import pytest

from untell.rewriter.structural import _plain_register, _vary_openers, structural_rewrite

CLUSTER = [
    "The pivotal step was agreed by the committee before the deadline last week.",
    "A crucial factor was the funding that arrived from the regional office then.",
    "The vital element is training, which the team scheduled for the autumn term.",
    "One paramount concern was safety on the site during the winter months there.",
    "An essential detail was the timing of the handover between the two groups.",
    "The salient point was cost, which the report set out across three chapters.",
]
LAYOUTS = {
    "one paragraph": " ".join(CLUSTER),
    "six paragraphs": "\n\n".join(CLUSTER),
    "six lines": "\n".join(CLUSTER),
    "six bullets": "\n".join("- " + s for s in CLUSTER),
}
SEEDS = range(24)
_WORD = re.compile(r"[A-Za-z]+")


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _max_duplicate(source: str, out: str) -> int:
    """How many times the rewriter introduced its single most-repeated new word."""
    before = Counter(w.lower() for w in _WORD.findall(source))
    after = Counter(w.lower() for w in _WORD.findall(out))
    added = [after[w] - before.get(w, 0) for w in after if after[w] > before.get(w, 0)]
    return max(added) if added else 0


def _run(source: str) -> list[int]:
    out = []
    for seed in SEEDS:
        random.seed(seed)
        rewritten = structural_rewrite(source)
        if rewritten != source:
            out.append(_max_duplicate(source, rewritten))
    return out


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_the_rewriter_actually_rewrote(layout: str) -> None:
    """The denominator. A layout the rewriter declines to touch introduces no words at all and
    would pass every assertion below without the guard existing."""
    assert _run(LAYOUTS[layout]), "no rewrite; the duplication check means nothing here"


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_no_layout_repeats_a_replacement(layout: str) -> None:
    """The fix. Splitting a document must not cost it its variety."""
    dups = [d for d in _run(LAYOUTS[layout]) if d >= 2]
    assert not dups, f"{layout}: {len(dups)} documents repeat a replacement"


def test_the_single_block_control_was_never_broken() -> None:
    """Guards the guard, and it is what made the measurement readable: the same sentences in one
    paragraph were always clean, so the difference is layout and nothing else. If this ever fails,
    the assertion above is measuring the corpus rather than the scope of the guard."""
    assert all(d < 2 for d in _run(LAYOUTS["one paragraph"]))


def test_a_shared_set_is_what_prevents_it() -> None:
    """The mechanism, asserted directly rather than inferred from the output.

    MEASURED at 200 seeds: 140/200 with a set per call, 0/200 with one shared. Trimmed here for
    runtime; a green run at this width is not a claim about the exact rate.
    """
    blocks = CLUSTER[:4]

    def repeats(*, shared: bool) -> int:
        hits = 0
        for seed in SEEDS:
            random.seed(seed)
            spent: set[str] | None = set() if shared else None
            outs = [_plain_register(b, intensity=1.0, spent=spent) for b in blocks]
            if _max_duplicate(" ".join(blocks), " ".join(outs)) >= 2:
                hits += 1
        return hits

    assert repeats(shared=True) == 0
    assert repeats(shared=False) > 0, (
        "a set per call must be able to collide, or this test proves nothing about sharing"
    )


def test_the_transforms_still_work_without_a_set() -> None:
    """Both keep their standalone behaviour: called directly, each owns its own guard. Existing
    callers and every other test path pass no set at all."""
    random.seed(1)
    assert _plain_register(CLUSTER[0], intensity=1.0) != ""
    random.seed(1)
    assert len(_vary_openers(list(CLUSTER), rate=1.0)) == len(CLUSTER)


def _openers_of(before: list[str], after: list[str]) -> set[str]:
    """Whatever the transform prepended, read off the front of each sentence it changed."""
    out = set()
    for src, got in zip(before, after):
        if got != src and got.endswith(src[0].lower() + src[1:]):
            out.add(got[: -len(src)].strip())
    return out


def test_the_opener_guard_is_shared_too() -> None:
    """Smaller denominator, same defect. Asserted at component level because a document-level
    assertion needs an opener collision, and the transform inserts about one per document.

    Two blocks of three, so the six picks stay inside the nine-item pool. Beyond it `_vary_openers`
    deliberately clears `spent` and cycles — the first version of this test asked for six sentences
    twice, exhausted the pool, and failed against correct behaviour.
    """
    blocks = [CLUSTER[:3], CLUSTER[3:]]

    def overlaps(*, shared: bool) -> int:
        hits = 0
        for seed in SEEDS:
            spent: set[str] | None = set() if shared else None
            used = []
            for block in blocks:
                random.seed(seed)  # same seed per block: the worst case for a per-call guard
                used.append(_openers_of(block, _vary_openers(list(block), rate=1.0, spent=spent)))
            if used[0] & used[1]:
                hits += 1
        return hits

    assert overlaps(shared=False) > 0, (
        "a set per call must be able to repeat an opener, or sharing proves nothing"
    )
    assert overlaps(shared=True) == 0


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_seeding_is_still_deterministic(layout: str) -> None:
    """Shared mutable state across blocks is exactly the kind of change that breaks reproducibility.
    The seed contract is the one every measurement in this repository rests on."""
    assert structural_rewrite(LAYOUTS[layout], seed=7) == structural_rewrite(
        LAYOUTS[layout], seed=7
    )
