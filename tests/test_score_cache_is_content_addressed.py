"""The per-text detector score cache is sound: hits are hits, misses are misses, and
a hit can never diverge from a recomputation.

The rewrite loop re-scores text that has not changed between iterations — the per-iteration
targeting pass re-scores EVERY sentence of the current best on every iteration, and only the
sentences the rewriter changed differ from the previous one. MEASURED on a 19-sentence HC3
document at the model-backed lite tier: one `score_sentences` pass is ~70 s and the loop pays
it up to `max_iters` times. The cache is content-addressed (key = text + detector names +
tier + threshold), so a rewritten sentence is a new key — invalidation is automatic, and
unchanged sentences hit. These tests pin the properties that make that safe: cache hits
return results identical to recomputation, caller mutation cannot corrupt an entry, failures
are never frozen, and oversized texts bypass the cache (the same shape as the round-1 spaCy
NER cache).
"""
from __future__ import annotations

import os

import untell.scripts.score as S


class _FakeDetector:
    """Minimal stand-in: name, tier, score(), mode() — all `_score_with_detectors` touches."""

    def __init__(self, name: str, value: float = 0.5):
        self.name = name
        self.tier = "lite"
        self.value = value

    def score(self, text):
        return self.value

    def mode(self):
        return "fake"

    def available(self):
        return True


def _spy_uncached(monkeypatch):
    """Wrap the uncached aggregation so tests can count real detector work."""
    calls = {"n": 0}
    real = S._score_with_detectors_uncached

    def spy(detectors, text, tier="full", threshold=S.DEFAULT_THRESHOLD):
        calls["n"] += 1
        return real(detectors, text, tier, threshold)

    monkeypatch.setattr(S, "_score_with_detectors_uncached", spy)
    return calls


def test_repeat_identical_text_hits_the_cache(monkeypatch, stdlib_lite):
    calls = _spy_uncached(monkeypatch)
    text = "The quick brown fox jumps over the lazy dog."
    first = S.score_text(text, tier="lite")
    second = S.score_text(text, tier="lite")
    assert first == second, "cached and recomputed scores must be identical"
    assert calls["n"] == 1, "the identical text must not be re-run through the detectors"


def test_changed_text_misses_the_cache(monkeypatch, stdlib_lite):
    calls = _spy_uncached(monkeypatch)
    S.score_text("One sentence that is entirely different.", tier="lite")
    S.score_text("A second sentence with different words.", tier="lite")
    assert calls["n"] == 2, "different text is a different key, so both must score"


def test_oversized_texts_bypass_the_cache(monkeypatch, stdlib_lite):
    calls = _spy_uncached(monkeypatch)
    big = "x" * (S._SCORE_CACHE_MAX_CHARS + 1)
    S.score_text(big, tier="lite")
    S.score_text(big, tier="lite")
    assert calls["n"] == 2, "past the cap every call must run the detectors"


def test_caller_mutation_does_not_corrupt_the_cache(monkeypatch, stdlib_lite):
    _spy_uncached(monkeypatch)
    text = "The quick brown fox jumps over the lazy dog."
    first = S.score_text(text, tier="lite")
    # Corrupt the dict a caller holds; the cache must hand out a fresh copy next time.
    first["warning"] = "CORRUPTED"
    first["detectors"]["perplexity_burstiness"] = 0.999
    again = S.score_text(text, tier="lite")
    assert again.get("warning") != "CORRUPTED"
    assert again["detectors"]["perplexity_burstiness"] != 0.999
    assert again == S.score_text(text, tier="lite")


def test_cache_key_includes_threshold(monkeypatch, stdlib_lite):
    calls = _spy_uncached(monkeypatch)
    text = "The quick brown fox jumps over the lazy dog."
    S.score_text(text, tier="lite", threshold=0.30)
    S.score_text(text, tier="lite", threshold=0.90)
    assert calls["n"] == 2, "a different threshold can flip `flagged`, so it is part of the key"


def test_failed_detector_results_are_not_cached(monkeypatch):
    """A transient failure must not be frozen for the life of the process."""
    calls = {"n": 0}

    class BoomDetector:
        name = "boom"
        tier = "lite"

        def score(self, text):
            calls["n"] += 1
            raise RuntimeError("flaky")

        def mode(self):
            return "fake"

        def available(self):
            return True

    monkeypatch.setattr(S, "load_detectors", lambda tier: [BoomDetector()])
    S.score_text("same text", tier="lite")
    S.score_text("same text", tier="lite")
    assert calls["n"] == 2, "an errored result must never be cached, so retries reach the detector"


def test_batch_and_single_paths_share_one_cache(monkeypatch, stdlib_lite):
    calls = _spy_uncached(monkeypatch)
    sent = "The quick brown fox jumps over the lazy dog."
    S.batch_score_texts([sent], tier="lite")
    S.score_text(sent, tier="lite")
    assert calls["n"] == 1, "both paths funnel into _score_with_detectors, so the second call must hit"


def test_lru_evicts_oldest_entries(monkeypatch):
    """The cache is bounded: beyond _SCORE_CACHE_SIZE entries, the oldest leaves."""
    # The uncached path runs `_mostly_locked_warning`, which calls lock() -> spaCy NER on
    # every fresh text. This test inserts >1024 DISTINCT texts, so neutralize that one
    # caveat (it is not what is being tested) to keep the test at unit speed.
    monkeypatch.setattr(S, "_mostly_locked_warning", lambda text: None)
    S._score_cache.clear()
    n = S._SCORE_CACHE_SIZE + 8
    for i in range(n):
        det = [_FakeDetector(f"fake{i}", 0.1 + (i % 9) * 0.1)]
        S._score_with_detectors(det, f"text number {i} here", tier="lite")
    assert len(S._score_cache) <= S._SCORE_CACHE_SIZE
    # The first entries were evicted; the newest are still there. The key is the full
    # production key, mode component included (UNTELL_LITE_NO_TORCH=1 in the ambient env).
    mode = tuple(
        (name, os.environ.get(name)) for name in S._SCORING_MODE_ENV_VARS if os.environ.get(name)
    )
    assert S._score_cache.get(
        ("text number 0 here", ("fake0",), "lite", S.DEFAULT_THRESHOLD, mode)
    ) is None
    assert S._score_cache.get(
        (f"text number {n - 1} here", (f"fake{n - 1}",), "lite", S.DEFAULT_THRESHOLD, mode)
    ) is not None
    S._score_cache.clear()
