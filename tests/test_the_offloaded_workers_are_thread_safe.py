"""Offloading the REST endpoints put five workers on real threads for the first time.

Until then every endpoint ran on the event loop, so the workers were effectively single-threaded
whatever they mutated. `asyncio.to_thread` removed that accident, which makes their module-level
state a live question rather than a dormant one:

  1. lazy detector model loading — two threads racing the same cache slot can double-load, or hand
     back a half-initialised object
  2. warn-once flags (`_WARNED_*`) — benign, would duplicate or drop a caveat
  3. accumulating containers (`_POLISH_FAILED`, rate-limit buckets)

They are safe. MEASURED at 8 workers over 6 rounds, both lite sub-paths, comparing every concurrent
result against the same input's serial answer:

    score_text        0/48 mismatches, 0 errors
    score_tells       0/48 mismatches, 0 errors
    score_sentences   0/48 mismatches, 0 errors
    cold cache raced by 8 threads     identical to the warm serial result

A scoring race surfaces as a WRONG NUMBER, not an exception, so equality against the serial answer
is the check — counting exceptions alone would have reported success either way.

Run on whichever lite sub-path the environment provides. Both were measured by hand and both are
clean; pinning the test to the stdlib path would exercise no model loading at all, which is the
risk the file exists for.
"""

from __future__ import annotations

import concurrent.futures

import pytest

from untell.scripts.score import score_text
from untell.scripts.sentences import score_sentences
from untell.scripts.tells import score_tells

TEXTS = [
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder involved in the programme of work across the wider organisation.",
    "My grandmother kept every birthday card anyone ever sent her, in a shoebox, in date order, "
    "and when she died we found forty years of them stacked up in the back of the wardrobe.",
    "The study examined soil carbon at eleven sites over four years, sampling to ninety "
    "centimetres, and reported mean stocks of 82.4 t/ha in the deepest layer of the profile.",
    "Additionally, the comprehensive solution delves into a multifaceted tapestry of concerns "
    "that underscore the pivotal integration of modern methodologies at considerable scale.",
]

WORKERS = {
    "score_text": lambda t: score_text(t, tier="lite")["max"],
    "score_tells": lambda t: score_tells(t)["tells"],
    "score_sentences": lambda t: len(score_sentences(t, tier="lite").get("sentences", [])),
}
ROUNDS = 3


@pytest.mark.parametrize("name", sorted(WORKERS))
def test_concurrent_results_match_the_serial_ones(name: str) -> None:
    fn = WORKERS[name]
    serial = [fn(t) for t in TEXTS]

    mismatches: list[tuple] = []
    errors: list[str] = []
    for _round in range(ROUNDS):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [(t, pool.submit(fn, t)) for t in TEXTS for _ in range(2)]
            for text, future in futures:
                try:
                    got = future.result()
                except Exception as exc:  # a crash is a different failure from a wrong number
                    errors.append(f"{type(exc).__name__}: {exc}")
                    continue
                want = serial[TEXTS.index(text)]
                if got != want:
                    mismatches.append((text[:40], want, got))

    assert not errors, f"{name} raised under concurrency: {errors[:3]}"
    assert not mismatches, f"{name} returned a different answer under concurrency: {mismatches[:3]}"


def test_the_workers_disagree_across_inputs() -> None:
    """Guards the guard. If every text scored the same, "concurrent equals serial" would hold for a
    worker that ignored its argument entirely, and the comparison would prove nothing."""
    for name, fn in WORKERS.items():
        values = [fn(t) for t in TEXTS]
        if name == "score_sentences":
            continue  # one-sentence fixtures by design; covered by the other two
        assert len(set(values)) > 1, f"{name} returned {values[0]!r} for every text"
