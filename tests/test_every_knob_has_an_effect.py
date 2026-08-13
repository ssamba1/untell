"""Every documented knob must be able to change a run. A knob that cannot is a defect.

This repo has had that defect repeatedly — the log records five separate guards that "declined the
job they exist to do", four style flags that could not change the output at any seed, and a fronting
budget that was permanently full. A knob is easy to leave inert because nothing fails when it is.

What makes this file worth having is that a naive version of it is WRONG. Sweeping the knobs at one
seed against one fixture reported three of them dead:

    style=casual   NO EFFECT
    margin=0.2     NO EFFECT
    scrub=False    NO EFFECT

All three were the probe, not the code. `style` sets rates, so a single seed can land where the
styled and unstyled paths coincide. `margin` only decides anything when the text would otherwise
PASS — with an unreachable threshold there is no borderline pass to withhold. `scrub` only matters
when there is something hidden to remove. Each test below therefore builds the condition its knob
responds to, and says which one.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import untell_text
from untell.scripts.score import score_text

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "In conclusion, these findings underscore the importance of a comprehensive approach here."
)
HUMAN = (
    "I went to the shop on the corner. It was closed for the day. So I walked home again, "
    "fairly annoyed about it."
)


def _run(text: str = AI, seed: int = 0, **kw):
    """`seed=` on the call, not `random.seed()` around it.

    `untell_text` seeds the global RNG from its own input, so a run depends on its text rather than
    on whatever the process rewrote beforehand. That made seeding from out here a no-op — every
    "sweep" below would have been the same draw repeated, and a knob that only shows up at some
    seeds would have looked inert. The parameter is the supported way to ask for a stream.
    """
    base = dict(tier="lite", max_iters=1, rewriter="composite", threshold=0.0, seed=seed)
    base.update(kw)
    return untell_text(text, **base)


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        ("threshold", {"threshold": 0.9}),
        ("max_iters", {"max_iters": 3}),
        # `best_of` is NOT here — see `test_best_of_changes_the_run_across_seeds`. Same reason as
        # `rewriter=structural` below: what it changes is which DRAW the selector keeps, and on
        # some seeds the draws agree.
        # `polish` is NOT here — see `test_polish_changes_the_run_across_seeds`. It needs both a
        # condition and a seed sweep, which is more than this parametrize can express.
        ("rewriter=surgical", {"rewriter": "surgical"}),
        # `rewriter=structural` is NOT here either, and for the same reason as `polish` — see
        # `test_structural_differs_from_composite_across_seeds`.
        ("rewriter=targeted", {"rewriter": "targeted"}),
    ],
    ids=lambda x: str(x)[:20],
)
def test_the_knob_changes_the_run(name: str, kwargs: dict) -> None:
    """These respond on the default fixture at a single seed, so no special condition is needed."""
    reference = _run()
    changed = _run(**kwargs)
    assert (changed["final"], changed.get("iterations")) != (
        reference["final"],
        reference.get("iterations"),
    ), f"{name} did not change the run"


def test_best_of_changes_the_run_across_seeds() -> None:
    """`best_of` decides how many candidates are drawn, not what any one of them says.

    Pinned at seed 0 this case failed: `best_of=1` and the default `best_of=3` produced identical
    output, because the extra draws lost the internal contest and the kept candidate was the same
    one either way. MEASURED through the loop on this file's AI text, best_of=1 against the
    default: they differ at **4 of 10 seeds**, and seed 0 is one of the six where they do not.

    That is not the knob failing. It is a knob whose whole effect is a SELECTION among random
    draws, asserted against a single draw — the same mistake the polish and style tests here were
    already written to avoid.
    """
    differ = 0
    for seed in range(12):
        reference = _run(seed=seed)
        single = _run(seed=seed, best_of=1)
        differ += (single["final"], single.get("iterations")) != (
            reference["final"],
            reference.get("iterations"),
        )
    assert differ > 0, "best_of=1 cannot change the run at any of 12 seeds"


def test_structural_differs_from_composite_across_seeds() -> None:
    """`composite` IS structural + surgical, and the surgical half contributes nothing here.

    Pinned at seed 0 this case FAILED, because `rewriter="structural"` and the default
    `rewriter="composite"` produced byte-identical output — same final, same iterations, same
    rewrite count — so the knob read as inert.

    It is not inert; the fixture and seed made it look that way. MEASURED through the loop on this
    file's own AI text: composite differs from structural at **5 of 10 seeds**. Seed 0 is one of
    the five where it does not.

    WHY they coincide at all is the same finding this file already records for `polish`, one layer
    up. Surgical acts on AI vocabulary, and structural has already removed it, so there is nothing
    left to substitute — not a gate rejecting a candidate. MEASURED by running surgical over
    structural's output, 12 seeds each across five texts:

        text              surgical changes RAW   changes POST-STRUCTURAL
        ai vocab heavy          12/12                    0/12
        delve tapestry          12/12                    0/12
        plain academic           0/12                    0/12
        informal                 0/12                    0/12
        technical                0/12                    0/12
        TOTAL                   24/60                    0/60

    So composite degenerates to structural-with-best-of-3 on this input, and whether the two agree
    is decided by which draw the internal selector happens to keep. Swept for exactly the reason
    the polish and style tests give: asserting a difference at one seed fails the day the
    randomness lands on the wrong one.
    """
    differ = 0
    for seed in range(12):
        reference = _run(seed=seed)  # composite, the default
        structural = _run(seed=seed, rewriter="structural")
        differ += (structural["final"], structural.get("iterations")) != (
            reference["final"],
            reference.get("iterations"),
        )
    assert differ > 0, (
        "rewriter='structural' cannot change the run at any of 12 seeds against the composite "
        "default — the two have become the same pipeline"
    )


def test_polish_changes_the_run_across_seeds() -> None:
    """`polish` re-runs `surgical_substitute` over the FINAL text, so it can only act on output a
    surgical pass has not already been over.

    The default rewriter here is `composite`, which IS structural + surgical — so polish was being
    asked to find swaps in text its own second stage had just produced. MEASURED, substitutions
    polish found on the final text under `composite`: **0 at every one of 6 seeds**. Not a gate
    rejecting a candidate; nothing left to swap. Across rewriters, polish changed the run on:

        targeted 5/6    structural 1/6    composite 0/6    surgical 0/6

    So the knob is not inert — it was measured against the one rewriter that makes it redundant by
    construction. `targeted` is the condition it responds to.

    Swept rather than pinned at one seed, for the reason the style test gives: `targeted` responds
    on 5 of 6 seeds, and asserting the difference at a single one would fail the day the rewriter's
    randomness lands on the sixth.
    """
    differ = 0
    for seed in range(12):
        reference = _run(seed=seed, rewriter="targeted")
        polished = _run(seed=seed, rewriter="targeted", polish=True)
        differ += polished["final"] != reference["final"]
    assert differ > 0, "polish=True cannot change the output at any of 12 seeds, even with a rewriter whose pipeline has no surgical stage"


def test_polish_is_redundant_after_a_surgical_stage() -> None:
    """The other half, stated so it is not mistaken for a bug later.

    `composite` ends in a surgical pass, so polish finding nothing there is CORRECT. Pinning it
    stops someone "fixing" the redundancy by making polish fire on text that does not need it.
    """
    from untell.attacks import surgical_substitute

    final = _run(rewriter="composite")["final"]
    again = surgical_substitute(final, tier="lite", threshold=0.30)
    assert again["text"] == final, "a second surgical pass should find nothing to change"


def test_style_changes_the_run_across_seeds() -> None:
    """`style` sets RATES. Asserting a difference at one seed asks for something it does not
    promise — the first version of this sweep called it dead for exactly that reason."""
    differ = 0
    for seed in range(40):
        differ += _run(seed=seed)["final"] != _run(seed=seed, style="casual")["final"]
    assert differ > 0, "style=casual cannot change the output at any of 40 seeds"


def test_margin_withholds_a_borderline_pass() -> None:
    """`margin` decides nothing unless the text would otherwise pass — with an unreachable
    threshold there is no pass to withhold, which is why a naive sweep reads it as inert.

    Built from the measured score so the band is real on whatever detectors this machine has:
    a threshold just above the score passes immediately, and the same threshold minus a margin
    that straddles it does not.
    """
    scored = score_text(HUMAN, tier="lite")["max"]
    threshold = round(scored + 0.05, 3)

    without = _run(HUMAN, threshold=threshold, max_iters=2, margin=0.0)
    withheld = _run(HUMAN, threshold=threshold, max_iters=2, margin=0.10)

    assert without["stopped"] == "passed" and without["iterations"] == 0, without
    assert withheld["iterations"] > 0, (
        f"margin did not withhold a pass at {scored:.4f} against threshold {threshold} "
        f"minus 0.10: {withheld}"
    )


def test_scrub_only_matters_when_something_is_hidden() -> None:
    """`scrub` is a no-op on clean text, which is most text — so the condition has to be built."""
    dirty = AI.replace(" the ", " the​ ")
    assert dirty.count("​") > 0, "premise: the fixture must carry hidden characters"

    assert _run(dirty, scrub=True)["final"].count("​") == 0
    assert _run(dirty, scrub=False)["final"].count("​") > 0
