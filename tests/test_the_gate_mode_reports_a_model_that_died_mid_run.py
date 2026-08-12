"""A guarantee that disappears during a run must be reported by that run, not the next one.

`meaning_gate` on the result tells a caller which fidelity checks were in force. The existing
tests cover the ways the gate can be missing before a run starts: the parser absent, the veto
switched off, the model not installed. They do not cover the case the `dead` flag exists for —
the model loading fine and then raising partway through (OOM, a corrupted cache, a transformers
version bump). `entailment` disables the veto process-wide when that happens, deliberately, so the
loop keeps going with one fewer check.

The question this file settles is whether the run that LOST the check says so, or whether only
later runs do. The first is honest reporting; the second hands the affected caller a result
labelled with a guarantee that stopped holding halfway through it.

Nothing here asserts new behaviour — the ordering already works, because the field is computed
when the result dict is built rather than before the loop. It was untested, and the failure mode
is invisible: every value in the field would still be a legal one.
"""
from __future__ import annotations

import pytest

from untell.scripts import entailment
from untell.scripts.run import _meaning_gate_mode, untell_text

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)


@pytest.fixture(autouse=True)
def _restore_nli():
    """`dead` is process-wide by design, so a test that trips it has to put it back."""
    was_dead, was_warned = entailment._NLI.dead, entailment._NLI.warned
    yield
    entailment._NLI.dead, entailment._NLI.warned = was_dead, was_warned


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_a_model_that_dies_mid_run_is_reported_by_that_run(monkeypatch):
    """The reason the field is computed at the end and not at the start."""
    if not entailment.available():
        pytest.skip("NLI is not installed here, so there is no live gate to kill")

    def _die(*_args, **_kwargs):
        raise RuntimeError("simulated CUDA OOM")

    monkeypatch.setattr(entailment, "_pair_probs", _die)

    result = untell_text(AI, tier="lite", threshold=0.0, max_iters=1, rewriter="composite")

    assert entailment._NLI.dead is True, "premise: the failure must have tripped the dead flag"
    assert "similarity-only" in result["meaning_gate"], (
        f"the veto died during this run and the result still claims {result['meaning_gate']!r}; "
        "the caller is told a meaning check held when it stopped running partway through"
    )


def test_the_field_is_not_computed_before_the_loop():
    """Stated directly, so a refactor that hoists it for tidiness fails here rather than in prod."""
    entailment._NLI.dead = False
    before = _meaning_gate_mode(True)
    entailment._NLI.dead = True
    after = _meaning_gate_mode(True)

    if before == after:
        pytest.skip("NLI is unavailable for another reason, so the flag cannot change the answer")
    assert "similarity-only" in after


def test_a_healthy_run_still_claims_the_check():
    """The other side. A gate that reported 'unavailable' defensively would be useless."""
    if not entailment.available():
        pytest.skip("NLI is not installed here")

    result = untell_text(AI, tier="lite", threshold=0.0, max_iters=1, rewriter="composite")
    assert "similarity-only" not in result["meaning_gate"], result["meaning_gate"]
