"""Eval-harness smoke tests (lite tier, builtin dataset, zero downloads)."""

from __future__ import annotations

from eval.baselines import full_loop, noop, rewrite, single_pass
from eval.benchmark import run
from eval.datasets import load_samples


def test_builtin_dataset_loads():
    samples = load_samples("builtin", 3)
    assert len(samples) == 3
    assert all(isinstance(s, str) and s for s in samples)


def test_rewrite_changes_text_but_keeps_meaning_words():
    text = load_samples("builtin", 1)[0]
    out = rewrite(text, strength=0.7)
    assert out != text  # something changed
    assert len(out.split()) > 10  # didn't collapse to nothing


def test_full_loop_reduces_or_matches_max_proxy():
    text = load_samples("builtin", 1)[0]
    res = full_loop(text, tier="lite")
    assert res.post["max"] <= res.pre["max"] + 1e-9
    assert 0.0 <= res.similarity <= 1.0
    assert res.iterations >= 1


def test_noop_is_identity():
    text = load_samples("builtin", 1)[0]
    res = noop(text)
    assert res.text == text
    assert res.iterations == 0


def test_full_loop_respects_similarity_gate():
    # The closed loop must never accept a rewrite that breaks the quality gate; single-pass can.
    samples = load_samples("builtin", 5)
    for t in samples:
        assert full_loop(t, tier="lite", sim_bar=0.76).similarity >= 0.76 - 1e-9


def test_full_loop_preserves_meaning_better_than_single_pass():
    # The honest mechanical thesis: the gated loop keeps similarity at least as high as the blind
    # single pass (which ignores the quality bar and can drift). Detection-vs-meaning is a
    # trade-off; the loop wins the *combined* objective.
    samples = load_samples("builtin", 5)
    sp_sim = sum(single_pass(t, tier="lite").similarity for t in samples) / len(samples)
    fl_sim = sum(full_loop(t, tier="lite").similarity for t in samples) / len(samples)
    assert fl_sim >= sp_sim - 1e-9


def test_run_returns_all_strategies():
    by = run("builtin", 3, "lite", 0.30, ["noop", "single_pass", "full_loop"])
    assert set(by.keys()) == {"noop", "single_pass", "full_loop"}
    assert all(len(v) == 3 for v in by.values())
