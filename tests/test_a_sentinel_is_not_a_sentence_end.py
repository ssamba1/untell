"""Masking an abbreviation blinds every guard that depends on seeing it.

`lock()`'s two-component dotted rule exists for `np.float64` and `model.01`, and its `\\d*` matches
ZERO digits — so it also claimed any `word.word`, including 13 of the 47 abbreviations the sentence
splitter knows about: e.g, i.e, a.m, p.m, u.s, u.k, ph.d, m.d, b.a, m.a, d.c.

Locking one is not harmless. `⟦HZ0000⟧.` looks exactly like the end of a sentence, so every
downstream pass that asks "is this dot a terminator?" gets the wrong answer — and the abbreviation
list that would have answered it is sitting one module away, consulted by `split_sentences` and by
nothing that runs on masked text.

MEASURED over 100 corpus halves through the shipped loop, counted against the source:

    RAID   2 new sentence-boundary defects   ->  0
    HC3    0                                 ->  0

    "(e.g. small branches or blurred edges)"  ->  "(e.g. Small branches or blurred edges)"
    "(e.g. mean or median)"                   ->  "(e.g. Mean or median)"

**0 of 50 on HC3.** Forum prose does not write "e.g.", so the corpus every bracket measurement in
the preceding results used could not show this defect at all. It took the register that uses
abbreviations to make it visible.

Two changes, and both are load-bearing: the abbreviation stays visible (preserve), and the capital
pass consults the list (structural). The pattern's own `(?<!\\.)` guard catches an ellipsis only —
in "e.g." the final dot follows a letter and sails straight through it.
"""

from __future__ import annotations

import logging

import pytest

from untell.rewriter.structural import structural_rewrite
from untell.scripts.preserve import lock, restore
from untell.scripts.run import untell_text
from untell.text_split import _ABBREVIATIONS, split_sentences

DOTTED_ABBREVIATIONS = sorted(a for a in _ABBREVIATIONS if "." in a)
# Not `model.01`: the rule's own comment named it and it never matched, because the second component
# must contain a letter. Verified against unmodified `main` before this file was written — it locks
# "01" alone there too, so it is a pre-existing partial lock and not a casualty of the exclusion.
IDENTIFIERS = ["np.float64", "untell.score", "tensorflow.keras", "os.path", "numpy.linalg"]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("abbr", DOTTED_ABBREVIATIONS)
def test_masking_never_leaves_a_sentinel_before_a_bare_dot(abbr: str) -> None:
    """The property the rest depends on, stated as the defect's shape rather than as "the
    abbreviation is visible".

    That stricter version fails on four of these for a reason that is not a defect: `u.s.`, `u.k.`,
    `d.c.` and `m.d.` are locked by the acronym rule INCLUDING their final dot, so the sentinel
    leaves no bare terminator behind and nothing downstream can misread it. What has to hold is
    that a guard is never asked about a dot whose owner has been masked away.
    """
    text = f"The team used {abbr}. small samples were taken from the site last week."
    masked, _ = lock(text)
    assert "⟧." not in masked, masked


@pytest.mark.parametrize("identifier", IDENTIFIERS)
def test_a_dotted_identifier_is_still_locked(identifier: str) -> None:
    """Guards the guard. The exclusion must not take the rule down with it — locking `np.float64`
    whole is why the rule exists, and a partial lock is what its own module calls the worst
    possible outcome."""
    text = f"The call to {identifier} returns before the buffer is flushed to disk."
    _, spans = lock(text)
    assert identifier in spans.values(), spans


@pytest.mark.parametrize("abbr", ["e.g", "i.e", "a.m", "p.m"])
def test_the_capital_pass_does_not_fire_after_an_abbreviation(abbr: str) -> None:
    """The damage itself, at the transform rather than through the loop."""
    text = (
        f"The method removes fine detail ({abbr}. small branches or blurred edges) from the mask "
        "before the comparison is made, which keeps the score stable across the whole test set."
    )
    out = structural_rewrite(text, intensity=1.0, seed=3)
    assert f"{abbr}. S" not in out and f"{abbr}. M" not in out, out[:160]


def test_the_loop_leaves_the_abbreviation_alone() -> None:
    """End to end, on the shape actually found in RAID."""
    doc = (
        "The method removes fine detail (e.g. small branches or blurred edges) from the mask. "
        "Moreover, it is important to note that this underscores the robustness of the approach. "
        "Furthermore, the same pattern was found in every cohort that the team examined."
    )
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert "(e.g. small branches or blurred edges)" in final, final[:200]


@pytest.mark.parametrize("abbr", ["e.g", "i.e", "a.m", "p.m"])
def test_masked_text_splits_into_the_same_sentences(abbr: str) -> None:
    """The blindness was never confined to the capital pass. Sentence splitting feeds burstiness,
    per-sentence scoring and the targeted rewriter's unit of work — and all of them run on masked
    text, so a sentinel that reads as a terminator miscounts every one of them."""
    text = f"The team used {abbr}. small samples from the site. The results were clear enough."
    masked, _ = lock(text)
    assert len(split_sentences(masked)) == len(split_sentences(text))


def test_the_round_trip_is_unaffected() -> None:
    text = "The call to np.float64 happened at 3 p.m. small samples were taken (e.g. two of them)."
    masked, spans = lock(text)
    assert restore(masked, spans) == text


def test_ordinary_prose_still_capitalises() -> None:
    """The pass this file constrains exists to fix real lowercase sentence starts, and a guard that
    disabled it would satisfy every assertion above."""
    text = "The result was clear. it was also cheap. the team published it in the spring."
    out = structural_rewrite(text, intensity=1.0, seed=1)
    assert ". it " not in out, out
