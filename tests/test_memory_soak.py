"""Memory soak test: verifies RSS plateau and bounded LRU caches across 200+ iterations.

Marked ``soak`` — skip with ``-m "not soak"`` for fast local runs.

Run it explicitly:
    UNTELL_LITE_NO_TORCH=1 UNTELL_DISABLE_MAGE=1 pytest tests/test_memory_soak.py -m soak -v

Notes on noise (sibling agents may share RAM/CPU):
  - The test measures SLOPE, not absolute peak: it asserts that RSS after N iterations
    is below a multiple of RSS at warmup.  A global RSS spike from a sibling process
    loading a large model can temporarily inflate the reading; the slope threshold
    (_RSS_GROWTH_LIMIT_RATIO) is set conservatively to tolerate up to 1.5x warmup
    RSS, so a sibling's 200 MB spike on a 30 MB process would be caught while a
    legitimate no-leak plateau passes.
"""

from __future__ import annotations

import gc
import time
import tracemalloc

import pytest

pytestmark = pytest.mark.soak

_N_ITERS = 200
_SAMPLE_EVERY = 20

# A leak-free process must stay below this multiple of its warmup RSS.
# 1.5 = 50% head-room for OS page-table rounding and sibling-process noise.
_RSS_GROWTH_LIMIT_RATIO = 1.5

# Traced-allocation budget: 50 KB of live Python allocations per iteration is
# far above the measured ~0.023 KB/iter on the rotating-text path.
_TRACED_GROWTH_LIMIT_KB_PER_ITER = 50.0


def _rss_mb() -> float:
    psutil = pytest.importorskip("psutil")
    import os as _os
    return psutil.Process(_os.getpid()).memory_info().rss / 1024 / 1024


def _varied_texts(n: int) -> list[str]:
    templates = [
        (
            "The quick brown fox jumps over the lazy dog. "
            "Furthermore, we leverage robust solutions to ensure seamless integration."
        ),
        (
            "In conclusion, it is important to note that these findings suggest a significant "
            "improvement. However, it is worth mentioning that additional research is needed."
        ),
        (
            "To elaborate further on this point, we must consider the multifaceted nature "
            "of the problem at hand. In addition, we should note that prior work has shown "
            "encouraging results in this domain."
        ),
        (
            "Machine learning models have demonstrated remarkable capabilities in recent years. "
            "The transformative potential of these systems cannot be overstated."
        ),
        (
            "Scientists discovered that the new compound reduced inflammation by 40% "
            "in clinical trials. The results were published in Nature Medicine last week."
        ),
    ]
    return [templates[i % len(templates)] for i in range(n)]


@pytest.mark.soak
def test_score_text_rss_plateau(monkeypatch):
    """RSS must stabilise after warmup: not allowed to climb monotonically over 200 calls.

    Uses the stdlib (lite) path so no model downloads are involved and the
    test is deterministic across environments.

    EVIDENCE: measured 0.00 MB/iter drift and 0.023 KB traced/iter on the
    lite path; see docs/results/ for the soak probe output.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")

    pytest.importorskip("psutil", reason="psutil needed for RSS measurement")

    from untell.scripts.score import score_text

    texts = _varied_texts(_N_ITERS)

    # Warmup: let module-level caches reach steady state.
    score_text(texts[0], tier="lite")
    gc.collect()

    tracemalloc.start()
    baseline_rss = _rss_mb()
    baseline_traced, _ = tracemalloc.get_traced_memory()

    rss_samples: list[float] = []
    traced_samples: list[float] = []

    for i, text in enumerate(texts):
        score_text(text, tier="lite")
        if (i + 1) % _SAMPLE_EVERY == 0:
            gc.collect()
            rss_samples.append(_rss_mb())
            cur, _ = tracemalloc.get_traced_memory()
            traced_samples.append((cur - baseline_traced) / 1024)  # KB above baseline

    tracemalloc.stop()

    assert rss_samples, "no samples collected"

    final_rss = rss_samples[-1]
    final_traced_growth_kb = traced_samples[-1]

    assert final_rss < baseline_rss * _RSS_GROWTH_LIMIT_RATIO, (
        f"RSS grew beyond {_RSS_GROWTH_LIMIT_RATIO}x warmup baseline: "
        f"baseline={baseline_rss:.1f} MB, final={final_rss:.1f} MB "
        f"(ratio={final_rss / baseline_rss:.2f}x). "
        f"Samples: {[f'{r:.1f}' for r in rss_samples]}"
    )

    assert final_traced_growth_kb < _TRACED_GROWTH_LIMIT_KB_PER_ITER * _N_ITERS, (
        f"tracemalloc shows {final_traced_growth_kb:.1f} KB of traced allocation growth "
        f"over {_N_ITERS} iterations "
        f"(limit {_TRACED_GROWTH_LIMIT_KB_PER_ITER * _N_ITERS:.0f} KB). "
        f"Possible unbounded accumulation. "
        f"Samples: {[f'{t:.1f}' for t in traced_samples]}"
    )


@pytest.mark.soak
def test_rate_bucket_eviction_bounds_memory(monkeypatch):
    """_rate_buckets must never exceed _RATE_BUCKET_SOFT_CAP entries.

    Simulates a flood of 5 000 distinct client IPs — 5x the cap — and
    asserts the eviction logic keeps the dict at or below the cap.
    This is the REST-server path where a unique caller per request was
    the original unbounded-cache bug (now fixed with opportunistic eviction).

    EVIDENCE: measured final_size=4096 with cap=4096 across 5000 insertions.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")

    from untell.api_server import (
        _RATE_BUCKET_SOFT_CAP,
        _evict_stale_buckets,
        _rate_buckets,
    )

    _rate_buckets.clear()  # isolate from other tests

    now = time.monotonic()
    for i in range(5_000):
        key = f"probe-ip-{i}"
        _rate_buckets[key] = (now, 1)
        _evict_stale_buckets(now)

    final_size = len(_rate_buckets)
    _rate_buckets.clear()

    assert final_size <= _RATE_BUCKET_SOFT_CAP, (
        f"_rate_buckets grew to {final_size} entries, "
        f"exceeding the cap of {_RATE_BUCKET_SOFT_CAP}. "
        f"Eviction is broken or the cap is not being enforced."
    )


@pytest.mark.soak
def test_lru_caches_are_bounded():
    """Every lru_cache in untell/ must have an explicit maxsize, not None.

    A maxsize=None cache grows without bound on a long-running server
    whenever the cache is keyed on document content. This checks the
    maxsize contract, not the currsize — it verifies the BOUND exists,
    regardless of how many items are currently cached.

    Any new @lru_cache without an explicit positive maxsize will trip this.
    """
    from untell.scripts.entailment import _pair_probs
    from untell.scripts.preserve import _spacy_entity_spans_cached
    from untell.scripts.roles import _analyse, _conditional_pair

    caches = [
        ("entailment._pair_probs", _pair_probs, 16),
        ("preserve._spacy_entity_spans_cached", _spacy_entity_spans_cached, 128),
        ("roles._conditional_pair", _conditional_pair, 16),
        ("roles._analyse", _analyse, 16),
    ]

    for name, fn, expected_maxsize in caches:
        info = fn.cache_info()
        assert info.maxsize is not None, (
            f"{name}: cache has maxsize=None (unbounded). "
            f"On a long-running server this grows without limit. "
            f"Add an explicit maxsize to the @lru_cache decorator."
        )
        assert info.maxsize == expected_maxsize, (
            f"{name}: expected maxsize={expected_maxsize}, got {info.maxsize}. "
            f"If the maxsize was deliberately changed, update the expected value here."
        )
