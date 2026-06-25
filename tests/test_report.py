"""Benchmark report tests (lite, builtin)."""

from __future__ import annotations

from eval.benchmark import run
from eval.report import _bypass_rate, render, summarize


def _by():
    return run("builtin", 4, "lite", 0.30, ["noop", "single_pass", "full_loop"])


def test_summarize_shape():
    s = summarize(_by(), 0.30)
    assert set(s["strategies"]) == {"noop", "single_pass", "full_loop"}
    for st in s["strategies"].values():
        assert st["n"] == 4
        assert 0.0 <= st["bypass_rate"] <= 1.0
        assert 0.0 <= st["mean_similarity"] <= 1.0
        assert "perplexity_burstiness" in st["per_detector"]
        pd = st["per_detector"]["perplexity_burstiness"]
        assert 0.0 <= pd["pre"] <= 1.0 and 0.0 <= pd["post"] <= 1.0
    assert "thesis_pass" in s and isinstance(s["thesis_pass"], bool)


def test_render_is_ascii_safe_and_complete():
    md = render(_by(), 0.30)
    md.encode("ascii")  # no emoji -> never crashes a Windows cp1252 console
    assert "# humanize benchmark" in md
    assert "Per-detector" in md
    assert "Thesis" in md


def test_per_detector_has_beat_rate_and_hardest():
    s = summarize(_by(), 0.30)
    for st in s["strategies"].values():
        pd = st["per_detector"]["perplexity_burstiness"]
        assert 0.0 <= pd["beat_rate"] <= 1.0
        assert "hardest_detector" in st
    # with only the lite detector present, it must be the hardest
    assert s["strategies"]["noop"]["hardest_detector"] == "perplexity_burstiness"


def test_render_shows_beat_and_hardest():
    md = render(_by(), 0.30)
    assert "beat%" in md
    assert "Hardest detector" in md


def test_bypass_rate_empty_is_zero():
    assert _bypass_rate([], 0.30) == 0.0


def test_noop_is_identity():
    # noop never changes the text, so pre==post and similarity is perfect — true at any tier
    # (the lite perplexity detector auto-upgrades to GPT-2 when torch is present, so the absolute
    # bypass rate is environment-dependent and must not be asserted to an exact value).
    s = summarize(run("builtin", 3, "lite", 0.30, ["noop"]), 0.30)
    noop = s["strategies"]["noop"]
    assert noop["mean_pre_max"] == noop["mean_post_max"]
    assert noop["mean_similarity"] == 1.0
    assert 0.0 <= noop["bypass_rate"] <= 1.0
