"""`seed=` stopped meaning anything the moment a second thread appeared.

`untell_text` seeds the GLOBAL `random` module — `structural.py` draws from it in 27 places — and
restores the caller's state on the way out. Save/seed/restore is only atomic if nothing else runs in
between, so on two threads T2's `getstate` captures T1's SEEDED state, both draw from one stream,
and whichever finishes last restores a state that was never the caller's.

MEASURED before the lock, three threads asking for the same seed they had just been given serially:

    serial, same seed, same text        reproducible
    3 threads, attempt 0 / 1 / 2        1/3, 0/3, 1/3 match their serial result
    caller's own RNG stream afterwards  changed

Both guarantees the seeding was added for, gone. After the lock: 3/3 on every attempt, and the
caller's stream is byte-identical.

The REST server did not hit this, for a reason that is its own defect: every endpoint is
`async def` and calls `untell_text` directly, so a rewrite runs ON the event loop and blocks every
other request until it finishes. That blocking is what serialised the RNG — which means the obvious
performance fix, offloading to a threadpool, would have introduced a reproducibility bug rather than
found one.

The lock is not the best answer. Threading a `random.Random(seed)` instance through the call is, and
it is a 27-site change in structural.py plus callers — named here rather than done blind. The lock
makes today's behaviour correct and explicit, and costs only parallel rewrites within one process,
which nothing currently asks for.
"""

from __future__ import annotations

import concurrent.futures
import random

import pytest

from untell.scripts.run import untell_text

TEXTS = [
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder. Furthermore, it underscores the pivotal integration of methods.",
    "Additionally, the study delves into a multifaceted tapestry of considerations at scale. "
    "Notably, it showcases the comprehensive landscape of modern research and its impact.",
    "In conclusion, the seamless solution demonstrates significant value for the organisation. "
    "Ultimately, the implications extend far beyond the immediate technical domain of work.",
]
SEED = 4242


@pytest.fixture(scope="module")
def stdlib_lite(request):
    mp = pytest.MonkeyPatch()
    mp.setenv("UNTELL_LITE_NO_TORCH", "1")
    request.addfinalizer(mp.undo)
    return mp


def _run(text: str, seed: int = SEED) -> str:
    return untell_text(
        text, tier="lite", rewriter="structural", max_iters=1, best_of=2,
        threshold=0.001, seed=seed,
    )["final"]


@pytest.fixture(scope="module")
def serial(stdlib_lite) -> dict[str, str]:
    return {t: _run(t) for t in TEXTS}


def test_the_same_seed_reproduces_serially(serial: dict[str, str]) -> None:
    """The premise. Without this the threaded comparison has no baseline to differ from."""
    assert {t: _run(t) for t in TEXTS} == serial


def test_the_rewrite_actually_uses_the_rng(stdlib_lite) -> None:
    """Guards the guard. If this configuration drew no random numbers, every test here would pass
    while measuring nothing — a lock around a function that does not touch the RNG is untestable
    this way."""
    outs = {_run(t, seed=s) for t in TEXTS[:1] for s in (1, 2, 3, 4, 5)}
    assert len(outs) > 1, "different seeds gave one output; this text does not exercise the RNG"


@pytest.mark.parametrize("attempt", range(3))
def test_concurrent_callers_get_their_seeded_result(
    attempt: int, serial: dict[str, str], stdlib_lite
) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEXTS)) as pool:
        futures = {pool.submit(_run, t): t for t in TEXTS}
        got = {futures[f]: f.result() for f in concurrent.futures.as_completed(futures)}

    mismatched = [t[:40] for t in TEXTS if got[t] != serial[t]]
    assert not mismatched, (
        f"{len(mismatched)}/{len(TEXTS)} threaded runs differ from their serial result at the same "
        f"seed, so `seed=` does not survive concurrency: {mismatched}"
    )


def test_a_concurrent_run_leaves_the_callers_rng_where_it_was(stdlib_lite) -> None:
    random.seed(7)
    before = [random.random() for _ in range(3)]

    random.seed(7)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEXTS)) as pool:
        list(pool.map(_run, TEXTS))
    after = [random.random() for _ in range(3)]

    assert before == after, (
        f"a library caller who seeded their own RNG found it moved by concurrent untell runs: "
        f"{before} -> {after}"
    )
