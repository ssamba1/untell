"""The spaCy entity pass is cached, because lock() runs from the scoring path too.

`_mostly_locked_warning` re-locks the text on EVERY detector pass, so one loop
run pays spaCy NER on the same documents repeatedly. MEASURED on a 309-word
flagged doc: 53 lock() calls in one loop run, 28 of them on texts already seen,
~0.11s per pass — roughly 6s of the run, all of it repeat work. The spans are a
pure function of the text and the cached pipeline, so repeat calls must hit the
LRU and not re-run the model. Texts past the scoring truncation cap bypass the
cache (repeats are rare, and caching would pin huge strings).
"""
from __future__ import annotations

import untell.scripts.preserve as preserve


def test_repeat_spacy_calls_hit_the_cache(monkeypatch):
    called = {"n": 0}
    real_impl = preserve._spacy_entity_spans_impl

    def spy(text):
        called["n"] += 1
        return real_impl(text)

    monkeypatch.setattr(preserve, "_spacy_entity_spans_impl", spy)
    preserve._spacy_entity_spans_cached.cache_clear()

    text = "Alice met Bob in Paris on Monday and they discussed the merger with Carol from Acme. " * 10
    first = preserve._spacy_entity_spans(text)
    second = preserve._spacy_entity_spans(text)
    assert first == second, "cached and uncached spans must be identical"
    assert called["n"] == 1, "the identical text must not be re-run through spaCy"


def test_oversized_texts_bypass_the_cache(monkeypatch):
    called = {"n": 0}

    def spy(text):
        called["n"] += 1
        return []

    monkeypatch.setattr(preserve, "_spacy_entity_spans_impl", spy)
    preserve._spacy_entity_spans_cached.cache_clear()

    big = "x" * (preserve._SPACY_CACHE_MAX_CHARS + 1)
    preserve._spacy_entity_spans(big)
    preserve._spacy_entity_spans(big)
    assert called["n"] == 2, "past the cap every call must run the model"


def test_cache_stays_consistent_with_impl(monkeypatch):
    """Both paths must return the same spans for the same text."""
    text = "The Eiffel Tower in Paris was visited by Marie Curie last Tuesday. "
    preserve._spacy_entity_spans_cached.cache_clear()
    cached = preserve._spacy_entity_spans(text)  # populates the cache
    direct = preserve._spacy_entity_spans_impl(text)
    assert [tuple(s) for s in cached] == [tuple(s) for s in direct]
    preserve._spacy_entity_spans_cached.cache_clear()
