"""Eval-harness smoke tests (lite tier, builtin dataset, zero downloads)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from eval.baselines import api_loop, full_loop, noop, rewrite, single_pass
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


def test_full_loop_caps_iterations():
    text = load_samples("builtin", 1)[0]
    res = full_loop(text, tier="lite", max_iters=2)
    assert res.iterations <= 2


def test_unknown_dataset_falls_back_to_builtin():
    # An unrecognized name must not crash — it degrades to the packaged samples.
    samples = load_samples("does-not-exist", 2)
    assert len(samples) == 2
    assert all(isinstance(s, str) and s for s in samples)


def test_builtin_repeats_to_satisfy_large_n():
    samples = load_samples("builtin", 12)
    assert len(samples) == 12


def test_api_loop_falls_back_to_scripted_without_rewriter(monkeypatch):
    # No SDK/key configured -> get_rewriter() is None -> scripted fallback, never crashes.
    import untell.rewriter

    monkeypatch.setattr(untell.rewriter, "get_rewriter", lambda prefer=None: None)
    res = api_loop(load_samples("builtin", 1)[0], tier="lite")
    assert res.post["max"] <= res.pre["max"] + 1e-9
    assert res.iterations >= 1


def test_api_loop_uses_a_configured_rewriter(monkeypatch):
    import untell.rewriter

    class _FakeRW:
        name = "fake"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            # A bursty, human-ish rewrite that the lite detector should not flag.
            return "It broke. Twice. Nobody knew why until someone actually read the logs, finally."

    monkeypatch.setattr(untell.rewriter, "get_rewriter", lambda prefer=None: _FakeRW())
    src = "Furthermore, the formulaic system continues to operate predictably and uniformly throughout."
    res = api_loop(src, tier="lite")
    assert isinstance(res.text, str) and res.text
    assert res.post["max"] <= res.pre["max"] + 1e-9


def test_raid_load_samples_excludes_attack_variants(monkeypatch):
    """load_samples('raid') must only return rows where attack is 'none' or absent.

    _raid_pairs enforces this filter with an explicit comment explaining why: adversarially
    perturbed variants (homoglyphs, whitespace, synonym swaps) answer a DIFFERENT question
    from normal AI text, and mixing them in makes a measurement answer neither cleanly.
    load_samples lacked the same filter, so --dataset raid in ceiling/benchmark/eval-policy
    silently returned a mixed population.

    Known-positive check: with an attacked row and a clean row in the stream, only the clean
    row should appear in the result.
    """
    # > 30 words each so the word-count gate passes.
    _W = "word " * 8
    attack_row = {"generation": _W + "attack", "model": "chatgpt", "attack": "homoglyph"}
    clean_row = {"generation": _W + "clean", "model": "chatgpt", "attack": "none"}
    no_attack_key = {"generation": _W + "nokey", "model": "chatgpt"}

    mock_datasets = MagicMock()
    mock_datasets.load_dataset.return_value = iter([attack_row, clean_row, no_attack_key])

    monkeypatch.setitem(sys.modules, "datasets", mock_datasets)

    import importlib
    import eval.datasets as ds_mod
    importlib.reload(ds_mod)

    result = ds_mod.load_samples("raid", 10)

    assert len(result) == 2, (
        f"Expected 2 samples (clean + no-key), got {len(result)}. "
        "If 3, the attack filter is missing."
    )
    texts = {r.strip() for r in result}
    assert any("clean" in t for t in texts), "clean row (attack='none') not returned"
    assert any("nokey" in t for t in texts), "row with no attack key not returned"
    assert not any("attack" in t for t in texts), "attacked row must be excluded"


def test_api_loop_survives_rewriter_exception(monkeypatch):
    import untell.rewriter

    class _BoomRW:
        name = "boom"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            raise RuntimeError("api down")

    monkeypatch.setattr(untell.rewriter, "get_rewriter", lambda prefer=None: _BoomRW())
    res = api_loop(load_samples("builtin", 1)[0], tier="lite")  # must fall back, not raise
    assert res.iterations >= 1


def test_raid_load_samples_excludes_attack_variants(monkeypatch):
    """load_samples('raid') must only return rows where attack is 'none' or absent.

    _raid_pairs enforces this filter with an explicit comment explaining why: adversarially
    perturbed variants (homoglyphs, whitespace, synonym swaps) answer a DIFFERENT question
    from normal AI text, and mixing them in makes a measurement answer neither cleanly.
    load_samples lacked the same filter, so --dataset raid in ceiling/benchmark/eval-policy
    silently returned a mixed population.

    Known-positive: given an attacked row, a clean row, a no-key row and a human row in the
    stream, only the clean row and the no-key row (both machine, attack absent/none) pass.
    """
    import sys
    from unittest.mock import MagicMock
    import eval.datasets as ds_mod

    # 36 words per body — well above the > 30 word gate in load_samples.
    _body = "the quick brown fox jumps over the lazy dog " * 4  # 36 words
    rows = [
        {"generation": _body + "attacked", "model": "chatgpt", "attack": "homoglyph"},
        {"generation": _body + "clean", "model": "chatgpt", "attack": "none"},
        {"generation": _body + "nokey", "model": "chatgpt"},  # no 'attack' key
        {"generation": _body + "human", "model": "human", "attack": "none"},  # human, excluded
    ]

    mock_ds = MagicMock()
    mock_ds.load_dataset.return_value = iter(rows)
    monkeypatch.setitem(sys.modules, "datasets", mock_ds)

    result = ds_mod.load_samples("raid", 10)

    assert len(result) == 2, (
        f"Expected 2 samples (clean + nokey), got {len(result)}. "
        "If 3, the attack-variant filter in load_samples is missing."
    )
    joined = " ".join(result)
    assert "attacked" not in joined, "row with attack='homoglyph' must be excluded"
    assert "clean" in joined, "row with attack='none' must be included"
    assert "nokey" in joined, "row with no 'attack' key must be included"
    assert "human" not in joined, "human-authored row must be excluded"
