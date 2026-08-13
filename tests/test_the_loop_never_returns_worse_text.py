"""The rewriter can produce a worse draft. The loop must never ship one.

`structural` raises the detector score on clean text at some seeds — measured on 3 of 5 clean
fixtures, worst +0.1010. That is allowed: a draw is a proposal. The loop is the net, adopting a
candidate only if it does not worsen the running best, and what a user cares about is not whether a
bad draft can exist but whether one can come back to them.

MEASURED through `untell_text` itself — 4 texts x 3 rewriters x 12 seeds, 144 runs:

    score worse than the input   0 / 144
    tells worse than the input   0 / 144

Including the cases where the underlying rewriter demonstrably produced a worse draft at that same
seed. The guard holds.

The file asserts the same thing at 5 seeds rather than 12, which is a cost decision and not a
weaker claim: every run is a full rewrite loop, and 12 seeds x two separate tests took 5m20s for
one file. Checking both properties in one pass over 5 seeds is 142s for the same coverage of
rewriters and texts. The 144-run figure above is what was measured, not what is re-run on every
`pytest`.

The existing `post <= pre` assertions in the suite are on the eval harness, on one text and one
configuration. This is the same property asked of the real entry point, across backends and seeds,
on the inputs where the risk actually lives — clean text, where there is little to gain and a
change can only cost.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.run import untell_text
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

TEXTS = {
    "clean informal":
        "My grandmother kept every birthday card anyone ever sent her, in a shoebox, in date "
        "order. When she died we found forty years of them. Half were from people none of us could "
        "place.",
    "clean one sentence": "An unsupervised segmentation approach was used throughout the study.",
    "clean recollection":
        "The oven has been dead since March. I keep meaning to call someone about it and then I "
        "do not. The toaster oven does most of what I need, so roast chicken is off the menu.",
    "ai heavy":
        "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
        "It significantly improves overall efficiency and accuracy across the evaluated corpus.",
}
REWRITERS = ["structural", "surgical", "composite"]
SEEDS = range(5)
_EPS = 0.001


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.mark.parametrize("name", sorted(TEXTS))
@pytest.mark.parametrize("rewriter", REWRITERS)
def test_the_loop_never_returns_worse_text(name: str, rewriter: str) -> None:
    """Score and tells in ONE pass over the seeds.

    Written first as two tests, which doubled the loop runs and took 5m20s for the file. Every run
    here is a full rewrite loop, so the cost is in the runs, not the assertions — checking both
    properties per run halves it for free.
    """
    text = TEXTS[name]
    score_before = score_text(text, tier="lite")["max"]
    tells_before = score_tells(text)["tells"]

    for seed in SEEDS:
        result = untell_text(text, tier="lite", rewriter=rewriter, threshold=0.001, seed=seed)

        score_after = result["post"]["max"]
        assert score_after <= score_before + _EPS, (
            f"{rewriter} on {name} at seed {seed} returned text scoring {score_after:.4f} against "
            f"the input's {score_before:.4f} — the adoption guard shipped a worsening candidate"
        )

        tells_after = score_tells(result["final"])["tells"]
        assert tells_after <= tells_before, (
            f"{rewriter} on {name} at seed {seed} returned {tells_after} tells against the "
            f"input's {tells_before}"
        )


def test_a_worse_draft_really_is_reachable() -> None:
    """Guards every case above, and is the reason they mean anything.

    If no rewriter could produce a worse draft on these fixtures, "the loop never returns one"
    would hold for an implementation that does nothing at all. Asserted at the REWRITER level,
    where the bad draws live, not through the loop that is supposed to filter them.
    """
    found = []
    for name, text in TEXTS.items():
        baseline = score_text(text, tier="lite")["max"]
        rw = get_rewriter("structural")
        scored = score_text(text, tier="lite")
        for seed in range(24):
            random.seed(seed)
            candidate = rw.rewrite(text, scored, 0.30)
            if candidate.strip() == text.strip():
                continue
            if score_text(candidate, tier="lite")["max"] > baseline + 0.01:
                found.append((name, seed))
                break

    assert found, (
        "no rewriter draw made any fixture worse, so the loop-level assertions above are vacuous — "
        "they would pass for a loop that never adopted anything"
    )


def test_the_loop_does_change_these_texts() -> None:
    """Second guard. A loop that returned its input verbatim could never return worse text."""
    changed = 0
    for text in TEXTS.values():
        for seed in SEEDS:
            result = untell_text(
                text, tier="lite", rewriter="composite", threshold=0.001, seed=seed
            )
            changed += result["final"].strip() != text.strip()
    assert changed > 0, "the loop never changed any fixture; the guarantees above are trivial"
