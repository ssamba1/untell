"""A rewriter that claims to vary, and does not, costs a detector pass per claim.

`T5ParaphraseRewriter.deterministic` was the class attribute `False`, annotated "sampled
generation varies run to run". Sampled generation does — but `sample` defaults to False, and that
branch is beam search. Three consecutive draws on one input were measured byte-identical.

Two places in run.py read the flag:

    draws = 1 if getattr(rw, "deterministic", False) else max(1, best_of)      # how many candidates
    if getattr(rw, "deterministic", False) and best_masked == prev_masked:     # stalled-run exit

So the default construction drew three identical candidates and paid a full detector pass for
each — at `--tier full`, two redundant five-detector passes per iteration on the slowest rewriter
in the repo — and could never take the early exit when it had nothing new to offer.

MEASURED on `--rewriter t5_paraphrase`, best_of=3, one paragraph:

    before   rewrites=3   post 0.6848
    after    rewrites=1   post 0.6848

Same answer, a third of the work. `neural` is unaffected: composite.py builds the T5 with
`sample=True` precisely to get diverse draws, and that construction still reports non-deterministic.
"""
from __future__ import annotations

import pytest

from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus."
)


def test_the_default_construction_is_deterministic():
    """Beam search. This is what `--rewriter t5_paraphrase` gets."""
    assert T5ParaphraseRewriter().deterministic is True


def test_the_sampling_construction_is_not():
    """Nucleus sampling, which is what the neural composite asks for to feed best-of-N."""
    assert T5ParaphraseRewriter(sample=True).deterministic is False


def test_the_neural_composite_still_gets_diverse_draws():
    """The regression this fix could plausibly cause: collapsing best-of-N for `neural`.

    composite.py constructs the T5 with sample=True for exactly that reason, so the flag must
    stay False there or the loop would take one draw where it wants several.
    """
    import inspect

    from untell.rewriter import composite

    source = inspect.getsource(composite)
    assert "T5ParaphraseRewriter(sample=True)" in source, (
        "the neural composite no longer asks for sampling; if that moved, this test needs to "
        "follow it rather than be deleted"
    )


def test_the_flag_is_per_instance_not_shared():
    """A class attribute would make the two constructions answer identically."""
    assert T5ParaphraseRewriter().deterministic != T5ParaphraseRewriter(sample=True).deterministic


def test_the_loop_reads_it_off_an_instance():
    """A property read off the CLASS is the property object — truthy, and silently wrong.

    Both readers in run.py use `getattr(rw, ...)` on an instance. This pins that, because the
    failure mode is invisible: every rewriter would look deterministic and best-of would collapse
    everywhere at once.
    """
    assert bool(T5ParaphraseRewriter.deterministic) is True, "read off the class, this is a property object"
    assert T5ParaphraseRewriter(sample=True).deterministic is False, "read off an instance, it answers"


@pytest.mark.slow
def test_repeated_draws_are_identical_without_sampling():
    """The measurement the flag now reports. Skipped without the model."""
    rewriter = T5ParaphraseRewriter()
    if not rewriter.available():
        pytest.skip("torch/transformers not importable")

    score = {"tier": "lite", "max": 0.7, "detectors": {}}
    draws = {rewriter.rewrite(AI, score, 0.30) for _ in range(3)}
    assert len(draws) == 1, "beam search returned different text across draws"
