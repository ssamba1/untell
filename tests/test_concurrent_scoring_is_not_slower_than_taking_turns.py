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

⚠️ That cancellation holds for STEADY load and not for a transient spike, which is how this test
failed once in a full-suite run at **2.41x** while passing in isolation, in three repeats, in a
140-file replay of everything that runs before it, and in a second full-suite run byte-identical to
the baseline. A spike landing in one trial's threaded half inflates that trial permanently, and a
median over five trials moves once three of them are hit.

So the estimator is the MINIMUM of the paired ratios rather than their median. Noise only ever adds
time, so the least-contaminated trial is the best estimate of the true cost — and one bad trial
cannot move a minimum at all. MEASURED on this machine, 12 reps against 8 competing CPU-bound
processes: min-of-ratios stayed within 0.98-1.06, median-of-ratios reached 1.32.

Two estimators were tried and rejected on measurement rather than taste. `min(threaded) /
min(sequential)` takes its two terms from DIFFERENT trials, which breaks the pairing that makes load
cancel; it was the worst of the three under load (1.69 on one rep where the median gave 1.12).
Widening the bar was not tried, because it would have weakened the test to hide a noisy estimator.
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
#
# RE-MEASURED on a 4-core machine with the lock replaced by `contextlib.nullcontext()`, which is the
# positive control for this whole file: **14.66-23.39x**, min-of-ratios 14.66 at its lowest. The
# original 3.17-4.13 stands as what was seen where it was taken; the pathology is simply far larger
# here, and the two readings are recorded rather than one replacing the other. Either way 2.0 sits
# clear of the healthy state and nowhere near the broken one, so the bar is unchanged — a bar moved
# to quiet a noisy estimator would be the wrong fix, and the estimator is what changed.
# RAISED from 2.0 to 5.0, which REVERSES a decision made two rounds earlier in this same file.
#
# That round said widening the bar "would weaken the test to hide a noisy estimator", and that was
# right at the time: the estimator WAS the problem, a median over five trials that three bad trials
# could move. Switching to the minimum of the paired ratios fixed that, and it measurably helped —
# the excursion fell from 2.41x to 2.09x.
#
# It did not fall below 2.0, and 2.09 is a MINIMUM over five trials, so it is not one contaminated
# trial. All five were slow. The bar is simply inside the healthy range under load:
#
#     healthy, isolated (many reps, torch installed or not)   0.91 - 1.07
#     healthy, inside a 40-minute full-suite run (observed)   up to 2.41
#     PATHOLOGICAL, `_NER_LOCK` replaced by nullcontext()    14.66 - 23.39
#
# A threshold whose job is to separate two states should sit between them, and 2.0 sits inside the
# first. Five is above every healthy value ever measured here and nearly three times below the
# lowest pathological one, so it separates them with room on both sides rather than tracking either.
#
# What is NOT claimed: that the cause of the loaded-run excursion is understood. It does not
# reproduce in isolation, and the obvious explanation — torch's OpenMP pool contending with the four
# NER threads — was tested and REFUTED: 0.98 baseline, 0.99 after warming the pool with matmuls,
# 0.91 with `torch.set_num_threads(1)`. So this is a bar calibrated on observed behaviour, not on a
# mechanism, and that is worth saying out loud rather than implying more than was established.
MAX_THREADED_RATIO = 5.0
TRIALS = 5
CONCURRENCY = 4


def _unique() -> str:
    """Fresh text each call: `_spacy_entity_spans` is `lru_cache`d, and cache hits never reach the
    model pass this is about — a repeated string would measure the cache."""
    return f"Report {next(_counter)}. " + _TEXT


def _ratio(call, threaded_first: bool = False) -> float:
    """One paired measurement: the same work on threads, over the same work in turn.

    `threaded_first` alternates which half runs first. Whichever goes second inherits whatever the
    first left behind — a warmed allocator, a GC generation due — and always running them in the
    same order folds that bias into every trial identically, where alternating cancels it.
    """
    def sequential_pass() -> float:
        start = time.perf_counter()
        for _ in range(CONCURRENCY):
            call()
        return time.perf_counter() - start

    def threaded_pass() -> float:
        threads = [threading.Thread(target=call) for _ in range(CONCURRENCY)]
        start = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return time.perf_counter() - start

    if threaded_first:
        threaded = threaded_pass()
        sequential = sequential_pass()
    else:
        sequential = sequential_pass()
        threaded = threaded_pass()
    return threaded / sequential if sequential > 0 else float("inf")


def _stable_ratio(call) -> float:
    """The smallest paired ratio over `TRIALS`, which is the least-contaminated one.

    NOT the median: see the module docstring. The pathology this file exists for is systematic —
    every trial shows it — so taking the best trial costs no detection power, MEASURED at 14.66x
    with the lock removed against 0.85-1.08 with it.
    """
    call()  # warm: the first call pays the spaCy model load
    return min(_ratio(call, threaded_first=i % 2 == 1) for i in range(TRIALS))


def test_threaded_ner_is_not_slower_than_sequential_ner():
    """The defect, at the component where it actually lives."""
    ratio = _stable_ratio(lambda: preserve._spacy_entity_spans(_unique()))
    assert ratio < MAX_THREADED_RATIO, (
        f"{CONCURRENCY} concurrent NER passes took {ratio:.2f}x the time of running them one after "
        f"another. Threads are supposed to cost nothing here, not multiply the work — check that "
        f"`preserve._NER_LOCK` still wraps the `nlp(text)` call.")


def test_threaded_scoring_is_not_slower_than_sequential_scoring():
    """The same property at the level a request actually sees."""
    from untell.scripts.score import score_text

    ratio = _stable_ratio(lambda: score_text(_unique(), tier="lite"))
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
    ratio = _stable_ratio(call)
    assert ratio < MAX_THREADED_RATIO, f"{component} now degrades on threads too: {ratio:.2f}x"
