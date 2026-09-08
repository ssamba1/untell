"""`_evict_stale_buckets`'s second guard, which survived the boundary sweep.

    if len(_rate_buckets) > _RATE_BUCKET_SOFT_CAP:
        for k, _v in sorted(_rate_buckets.items(), key=...)[: len(_rate_buckets) - CAP]:
            del _rate_buckets[k]

Round 135 filed this as an EQUIVALENT mutant and that was WRONG. The reasoning compared the two
operators by which keys they delete: at exactly the cap the slice bound is `len - CAP == 0`, so
`>=` enters the loop and deletes nothing, same as `>` skipping it. True, and beside the point — the
slice is taken from `sorted(...)`, which under `>=` runs over the whole dict before the empty slice
discards it. The eviction is a memory guard on the one component that listens on a socket, it runs
on the request path, and the cap is 4096, so the mutant buys an O(n log n) sort of four thousand
entries per request at exactly the boundary the guard exists to sit on.

Deleting nothing is not the same as doing nothing. The observable is the sort.
"""

from __future__ import annotations

import pytest

from untell import api_server
from untell.api_server import _RATE_BUCKET_SOFT_CAP, _RATE_WINDOW_SECONDS


@pytest.fixture
def buckets(monkeypatch):
    """A fresh bucket dict, so the module's real one is never mutated by a test."""
    fresh: dict[str, tuple[float, int]] = {}
    monkeypatch.setattr(api_server, "_rate_buckets", fresh)
    return fresh


@pytest.fixture
def sort_spy(monkeypatch):
    """Counts `sorted` calls inside the module.

    A module-global shadows the builtin for name lookup inside its functions, so this sees the call
    the mutant would make without changing what the call does.
    """
    calls: list[int] = []
    real = sorted

    def counting(iterable, **kw):
        result = real(iterable, **kw)
        calls.append(len(result))
        return result

    monkeypatch.setattr(api_server, "sorted", counting, raising=False)
    return calls


def _fill(buckets: dict, live: int, stale: int, now: float) -> None:
    """`live` buckets inside the window and `stale` ones past it."""
    for i in range(live):
        buckets[f"live-{i}"] = (now, 1)
    for i in range(stale):
        buckets[f"stale-{i}"] = (now - _RATE_WINDOW_SECONDS - 1.0, 1)


def test_landing_exactly_on_the_cap_after_the_sweep_does_not_sort(buckets, sort_spy):
    """One over the cap, one of them stale: the sweep leaves exactly `_RATE_BUCKET_SOFT_CAP`.

    At the cap there is nothing to drop, and the guard's job is to say so without paying for a sort.
    Under `>=` this request sorts 4096 buckets to delete none of them.
    """
    now = 1_000.0
    _fill(buckets, live=_RATE_BUCKET_SOFT_CAP, stale=1, now=now)
    assert len(buckets) == _RATE_BUCKET_SOFT_CAP + 1

    api_server._evict_stale_buckets(now)

    assert len(buckets) == _RATE_BUCKET_SOFT_CAP, "the stale bucket should have gone, and only it"
    assert sort_spy == [], (
        "at exactly the cap the oldest-bucket sort must not run: it is O(n log n) over 4096 "
        "entries on the request path, and it would delete nothing")


def test_one_over_the_cap_after_the_sweep_does_sort_and_drops_the_oldest(buckets, sort_spy):
    """The neighbour. Without it the assertion above would also pass on a guard that never fires."""
    now = 1_000.0
    _fill(buckets, live=_RATE_BUCKET_SOFT_CAP + 1, stale=1, now=now)

    api_server._evict_stale_buckets(now)

    assert len(buckets) == _RATE_BUCKET_SOFT_CAP
    assert sort_spy, "over the cap the oldest bucket must be found and dropped"


def test_below_the_cap_returns_before_either_pass(buckets, sort_spy):
    """The first guard, pinned so the two tests above cannot be read as covering it."""
    now = 1_000.0
    _fill(buckets, live=10, stale=5, now=now)
    api_server._evict_stale_buckets(now)
    assert len(buckets) == 15, "below the cap nothing is swept at all"
    assert sort_spy == []
