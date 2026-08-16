"""Same input, same seed, same output — including when the rewriter instance is reused.

Every measurement in `docs/free-ceiling-measured.md` depends on this and none of it asserted it.
The harnesses behind Results 48, 56, 59 and 73 all construct one rewriter and drive many texts
through it, so a rewriter carrying state between calls would not have made those measurements
noisy — it would have made them wrong in a way that reruns reproduce.

MEASURED when this was written: 6 of 6 HC3 texts reproducible with a fresh rewriter, 4 of 4 with a
reused one, and a text's output identical whether or not another text had been processed on the
same instance first.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.run import untell_text

TEXTS = [
    "Moreover, the framework leverages a robust approach to deliver outcomes at scale. "
    "Furthermore, it is important to note that this significantly enhances efficiency overall.",
    "In today's rapidly evolving landscape, organizations must navigate an increasingly complex "
    "array of challenges. By leveraging cutting-edge tools, they unlock meaningful growth.",
]


@pytest.fixture(scope="module", autouse=True)
def _warm_up() -> None:
    """Run the loop once before any assertion, and it is not a workaround.

    MEASURED: the FIRST call in a process produces different output from every call after it, at
    the same seed. Not the rewriter — `rw.rewrite()` alone is byte-identical 4 of 4 either way —
    and not the scorers, gates or sentence targeting, all of which were checked and are stable.
    The first call lazy-loads models, that loading draws from the global RNG, and the substitution
    step downstream therefore sees a different stream. Once warm, the RNG state after each call is
    identical and a FRESH rewriter reproduces exactly.

    So "reproducible" is a property of a warm process, and a harness that seeds before its first
    call gets one perturbed result. Paired comparisons survive it — both arms take the hit in the
    same position — which is why the measurements in this repository stand.
    """
    _run(get_rewriter("composite"), TEXTS[0])


def _run(rewriter, text: str, seed: int = 42) -> str:
    """`threshold=0.0` so the loop actually rewrites.

    At the default threshold this returned the input untouched: TEXTS[0] scores 0.1681 at lite
    tier, below 0.30, so the loop answered `stopped: passed` with `iterations: 0, rewrites: 0`.
    Every reproducibility test above was then comparing three identical no-ops — which is the exact
    hazard `test_the_rewrite_actually_did_something` exists to catch, and it duly failed while its
    neighbours passed for the wrong reason.

    Forcing the threshold makes the loop run on text that does not need it, which is what these
    tests want: the property under test is that a rewrite is deterministic, not that this
    particular text triggers one.
    """
    random.seed(seed)
    return untell_text(
        text, tier="lite", max_iters=1, best_of=2, rewriter=rewriter, threshold=0.0
    )["final"]


@pytest.mark.parametrize("text", TEXTS, ids=["ai_formal", "ai_marketing"])
def test_a_fresh_rewriter_is_reproducible(text: str) -> None:
    outs = {_run(get_rewriter("composite"), text) for _ in range(3)}
    assert len(outs) == 1, f"three runs at one seed produced {len(outs)} different outputs"


@pytest.mark.parametrize("text", TEXTS, ids=["ai_formal", "ai_marketing"])
def test_a_REUSED_rewriter_is_reproducible(text: str) -> None:
    """The pattern every measurement harness in this repository actually uses."""
    rewriter = get_rewriter("composite")
    outs = {_run(rewriter, text) for _ in range(3)}
    assert len(outs) == 1, f"a reused instance produced {len(outs)} different outputs at one seed"


def test_one_text_does_not_change_the_next() -> None:
    """Cross-text state leakage would not show up as noise. It would show up as a measurement that
    depends on corpus ORDER and reproduces perfectly on rerun — the hardest kind to notice."""
    alone = _run(get_rewriter("composite"), TEXTS[1], seed=7)

    shared = get_rewriter("composite")
    _run(shared, TEXTS[0], seed=0)
    after = _run(shared, TEXTS[1], seed=7)

    assert alone == after, "processing one text changed what the next produced on the same instance"


def test_the_rewrite_actually_did_something(monkeypatch) -> None:
    """Guards every test above: three identical no-ops are also 'reproducible'."""
    # Pin the torch/gpt2 scoring path explicitly (issue #18). Under UNTELL_LITE_NO_TORCH=1
    # the stdlib lite scorer rates TEXTS[0] at 0.8667, the composite rewriter's candidates
    # never beat it, and the loop returns the input untouched — which makes this guard fail
    # for the wrong reason. The variable is read at call time, so deleting it here is enough;
    # the test must not depend on what the ambient environment happened to set.
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    assert _run(get_rewriter("composite"), TEXTS[0]) != TEXTS[0]
