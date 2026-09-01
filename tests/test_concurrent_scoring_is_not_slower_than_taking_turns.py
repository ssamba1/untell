"""Running the scorer on threads used to be three to four times slower than not.

The API server offloads every endpoint with `asyncio.to_thread`, so two simultaneous requests run
on two threads. MEASURED on `score_text`, threaded against the same calls made one after another:

    n=2   sequential 0.176s   threaded 0.640s   3.65x
    n=4   sequential 0.340s   threaded 1.148s   3.37x
    n=8   sequential 0.656s   threaded 1.504s   2.29x

Not the GIL. Under the GIL, N CPU-bound threads take about as long as N sequential calls — a ratio
near 1.0, which is exactly what `_claimed_spans` (1.17x), `score_tells` (0.97x) and the detector
(1.22x) all measure. **Only spaCy's model pass degrades**, at 4.13x, and it took isolating each
component to see that, because at the `score_text` level it just looks like "threads are bad here".

So `preserve._NER_LOCK` serialises that one call. If running two passes at once costs four times
running them in turn, taking turns is the optimisation — and the lock is uncontended in the
single-request case, where a call stays at its MEASURED 73.2ms median.

These are timing tests, which are the flakiest kind, so they compare threaded work against the
identical sequential work in the same process and assert on the *ratio*. A slow machine moves both
terms together and cancels; only the pathology moves them apart.
"""

from __future__ import annotations

import itertools
import statistics
import threading
import time

import pytest

import untell.scripts.preserve as preserve

_TEXT = ("Moreover, the system processes data efficiently. Furthermore, it is important to note "
         "that the results demonstrate significant improvement. ") * 20
_counter = itertools.count()

# Observed with the lock: 0.96-1.22 over seven trials, median 1.06. Observed without it: 3.17-4.13.
# 2.0 sits clear of the first and well under the second, so it separates the two states rather than
# tracking either closely.
MAX_THREADED_RATIO = 2.0
TRIALS = 5
CONCURRENCY = 4


def _unique() -> str:
    """Fresh text each call: `_spacy_entity_spans` is `lru_cache`d, and cache hits never reach the
    model pass this is about — a repeated string would measure the cache."""
    return f"Report {next(_counter)}. " + _TEXT


def _ratio(call) -> float:
    start = time.perf_counter()
    for _ in range(CONCURRENCY):
        call()
    sequential = time.perf_counter() - start

    threads = [threading.Thread(target=call) for _ in range(CONCURRENCY)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    threaded = time.perf_counter() - start
    return threaded / sequential if sequential > 0 else float("inf")


def _median_ratio(call) -> float:
    call()  # warm: the first call pays the spaCy model load
    return statistics.median(_ratio(call) for _ in range(TRIALS))


def test_threaded_ner_is_not_slower_than_sequential_ner():
    """The defect, at the component where it actually lives."""
    ratio = _median_ratio(lambda: preserve._spacy_entity_spans(_unique()))
    assert ratio < MAX_THREADED_RATIO, (
        f"{CONCURRENCY} concurrent NER passes took {ratio:.2f}x the time of running them one after "
        f"another. Threads are supposed to cost nothing here, not multiply the work — check that "
        f"`preserve._NER_LOCK` still wraps the `nlp(text)` call.")


def test_threaded_scoring_is_not_slower_than_sequential_scoring():
    """The same property at the level a request actually sees."""
    from untell.scripts.score import score_text

    ratio = _median_ratio(lambda: score_text(_unique(), tier="lite"))
    assert ratio < MAX_THREADED_RATIO, (
        f"{CONCURRENCY} concurrent score_text calls took {ratio:.2f}x sequential")


def test_the_lock_exists_and_wraps_the_model_pass():
    """Structural, so a refactor that drops the lock fails here and names it, rather than only
    showing up as a timing test going red on a busy machine."""
    import inspect

    assert isinstance(preserve._NER_LOCK, type(threading.Lock()))
    source = inspect.getsource(preserve._spacy_entity_spans_impl)
    assert "_NER_LOCK" in source, "the model pass is no longer serialised"
    assert "with _NER_LOCK" in source and "nlp(text)" in source


def test_an_uncontended_lock_costs_nothing_measurable():
    """The trade only holds if the single-request path is unaffected, which is the common case."""
    call = lambda: preserve._spacy_entity_spans(_unique())  # noqa: E731
    call()
    runs = []
    for _ in range(7):
        start = time.perf_counter()
        call()
        runs.append(time.perf_counter() - start)
    # Generous: this asserts the lock did not introduce a stall, not a benchmark. A contended or
    # deadlocked lock shows up here as seconds, not milliseconds.
    assert statistics.median(runs) < 1.0


@pytest.mark.parametrize("component,call", [
    ("_claimed_spans", lambda: __import__("untell.scripts.tells", fromlist=["x"])
     ._claimed_spans(_unique())),
    ("score_tells", lambda: __import__("untell.scripts.tells", fromlist=["x"])
     .score_tells(_unique())),
])
def test_the_pure_python_components_were_never_the_problem(component, call):
    """Pins the diagnosis, not just the fix.

    If these ever went superlinear too, the cause would not be spaCy and the lock would be the wrong
    answer. Keeping them measured is what makes the NER result mean something.
    """
    ratio = _median_ratio(call)
    assert ratio < MAX_THREADED_RATIO, f"{component} now degrades on threads too: {ratio:.2f}x"
