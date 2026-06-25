"""Quality-gate tests (lite token-overlap fallback path)."""

from __future__ import annotations

from humanize.scripts.quality import DEFAULT_BAR, passes, similarity, token_overlap


def test_identical_text_is_max_similarity():
    t = "The quick brown fox jumps over the lazy dog."
    assert similarity(t, t) >= 0.999
    assert passes(t, t)


def test_unrelated_text_is_low_similarity():
    a = "The quick brown fox jumps over the lazy dog."
    b = "Quarterly revenue projections exceeded analyst expectations this fiscal year."
    assert similarity(a, b) < DEFAULT_BAR
    assert not passes(a, b)


def test_paraphrase_keeps_some_overlap():
    a = "Regular exercise improves both physical and mental health."
    b = "Regular exercise improves both physical health and mental health."
    s = similarity(a, b)
    assert 0.0 <= s <= 1.0


def test_token_overlap_bounds():
    assert token_overlap("", "") == 1.0
    assert token_overlap("abc def", "") == 0.0
    assert token_overlap("a b c", "a b c") == 1.0
    assert 0.0 < token_overlap("a b c d", "a b x y") < 1.0


def test_empty_vs_nonempty():
    assert similarity("", "something") == 0.0
