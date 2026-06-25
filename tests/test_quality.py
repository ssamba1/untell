"""Quality-gate tests (lite token-overlap fallback path)."""

from __future__ import annotations

import json

from humanize.scripts.quality import (
    DEFAULT_BAR,
    TOKEN_BAR,
    confidence,
    method,
    passes,
    recommended_bar,
    similarity,
    token_overlap,
)
from humanize.scripts.quality import (
    main as quality_main,
)


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


def test_metric_aware_bar_is_lower_for_token_overlap():
    # sentence-transformers is absent in CI's lite path → token-overlap metric is active.
    assert TOKEN_BAR < DEFAULT_BAR
    if method() == "token_overlap":
        assert recommended_bar() == TOKEN_BAR
        assert confidence() == "low"


def test_passes_default_bar_is_metric_aware():
    t = "Regular exercise improves both physical and mental health."
    assert passes(t, t)  # identical always passes
    assert passes(t, t, bar=0.99)  # explicit override still honored


def test_quality_cli_is_ascii_safe(capsys):
    rc = quality_main(["the cat sat on the mat", "the cat sat on the mat"])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # must not raise — portable on a non-UTF-8 (Windows cp1252) stdout
    parsed = json.loads(out)
    assert parsed["method"] in ("embedding", "token_overlap")
    assert "confidence" in parsed and "bar" in parsed and "passes" in parsed
