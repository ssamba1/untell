"""The same text must give the same run, whatever the process rewrote first.

`structural.py` draws from the global `random` module in 27 places and nothing seeded it, so the
stream carried over between calls. MEASURED before the fix — one process, stdlib path, one
document, identical tier/max_iters/rewriter, differing only in position:

    scored first                       post 0.4003, 778 chars
    scored after two other documents   post 0.4325, 770 chars

Same input, different answer. Every batch figure in eval/ was therefore a function of iteration
order, and no reported number could be reproduced without replaying the sequence that preceded it.

`untell_text` now seeds from a blake2b digest of its input — not `hash()`, which is salted per
process and would have reproduced this exact bug while looking like a fix — and restores the
caller's RNG state on the way out.

The seeding is per RUN, not per rewrite, and that distinction is load-bearing: best-of-N calls
`rw.rewrite()` N times with byte-identical arguments and depends on the stream advancing between
them. Seeding per rewrite would collapse all N draws into one and silently undo best-of, which is
worth 33% -> 0% still-flagged. The last test here is what tells those two designs apart.
"""
from __future__ import annotations

import random

import pytest

from untell.scripts.run import untell_text

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "In conclusion, these findings underscore the importance of a comprehensive approach."
)
OTHER = (
    "Furthermore, organizations increasingly adopt these transformative technologies to optimize "
    "operational workflows. Overall, the impact continues to expand across numerous sectors."
)


@pytest.fixture(autouse=True)
def _stdlib_path(monkeypatch):
    """The heuristic path: fast, and deterministic in the detector so only the RNG is in play."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _run(text: str, **kw) -> dict:
    return untell_text(text, tier="lite", threshold=0.30, max_iters=1, rewriter="composite", **kw)


def test_position_in_a_batch_does_not_change_the_result():
    """The regression itself: run a text first, then again after other work, and compare."""
    first = _run(AI)

    _run(OTHER)
    _run(OTHER)
    later = _run(AI)

    assert later["final"] == first["final"], (
        "the same document produced different text depending on how many others preceded it; "
        "the RNG stream is carrying over between runs again"
    )
    assert later["post"]["max"] == first["post"]["max"]


def test_the_callers_rng_is_left_where_they_put_it():
    """Seeding is an implementation detail of the loop, not something it does to the caller."""
    random.seed(1234)
    before = random.getstate()
    _run(AI)
    assert random.getstate() == before, "untell_text moved the caller's RNG stream"


def test_an_explicit_seed_still_selects_a_stream():
    """Sweeps must stay possible: several tests vary the seed to show a knob is not inert."""
    a, b = _run(AI, seed=1), _run(AI, seed=2)
    again = _run(AI, seed=1)

    assert again["final"] == a["final"], "the same explicit seed did not reproduce"
    assert a["final"] != b["final"] or a["post"]["max"] != b["post"]["max"], (
        "two different seeds gave an identical run, so the seed parameter selects nothing"
    )


def test_different_documents_still_get_different_streams():
    """Seeding from the text, not from a constant. A fixed seed for every input would make the
    rewriter's choices correlate across unrelated documents."""
    assert _run(AI)["final"] != _run(OTHER)["final"]


def test_best_of_still_draws_more_than_once():
    """The check that separates per-run seeding from per-rewrite seeding.

    Per-rewrite seeding would hand every draw the same stream, so N candidates would be one
    candidate N times — best-of would still *report* its draws and still be dead. `rewrites`
    counts actual calls into the rewriter.
    """
    one = _run(AI, best_of=1)
    three = _run(AI, best_of=3)
    assert one["rewrites"] == 1
    assert three["rewrites"] == 3, "best-of is no longer drawing the candidates it claims"
