"""Tests for the dataset loader — verifies builtin fallback and HF-backed loads."""
from __future__ import annotations

from eval.datasets import _BUILTIN, load_samples


def test_builtin_returns_expected_count():
    samples = load_samples("builtin", n=3)
    assert len(samples) == 3
    for s in samples:
        assert isinstance(s, str) and len(s) > 20


def test_builtin_respects_n_larger_than_available():
    """When n exceeds the built-in pool, repeat the pool."""
    samples = load_samples("builtin", n=100)
    assert len(samples) == 100


def test_padding_the_builtin_pool_is_not_silent(caplog):
    """Padding is intended — the harness must run offline — but it must not be invisible.

    `--n 2000` against the builtin set returns 2000 items that are 5 texts repeated 400 times.
    rl_humanizer builds one GRPO prompt per item, so a run reported as 2000 samples trains on
    five; distill and eval_policy print the padded number as their denominator. Every count
    derived from a silently padded load is fabricated.
    """
    import logging

    with caplog.at_level(logging.WARNING, logger="eval.datasets"):
        samples = load_samples("builtin", n=100)

    assert len(samples) == 100
    assert len(set(samples)) == len(_BUILTIN)  # the padding really is repetition
    assert any("padded" in r.message or "padded" in r.getMessage() for r in caplog.records), (
        "padding the builtin pool must warn; a silent pad makes every reported count wrong"
    )


def test_no_warning_when_the_pool_covers_the_request(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="eval.datasets"):
        load_samples("builtin", n=len(_BUILTIN))
    assert not [r for r in caplog.records if "padded" in r.getMessage()]


def test_builtin_all_formulaic():
    """Every built-in sample should have AI tells (formulaic transitions, stilted vocab)."""
    from untell.scripts.tells import score_tells

    for s in _BUILTIN:
        r = score_tells(s)
        assert r["tells"] >= 1, f"Built-in sample should register AI tells: {s[:60]}... got {r}"


def test_unknown_dataset_falls_back_to_builtin():
    """An unknown dataset name should fall back to the builtin set."""
    samples = load_samples("nonexistent_dataset_xyz", n=2)
    assert len(samples) == 2


def test_raid_falls_back_gracefully_without_hf():
    """Without HuggingFace datasets installed, raid should fall back to builtin."""
    import sys

    # Simulate datasets not being available
    saved = sys.modules.pop("datasets", None)
    try:
        samples = load_samples("raid", n=2)
        assert len(samples) == 2
    finally:
        if saved:
            sys.modules["datasets"] = saved


def test_hc3_falls_back_gracefully_without_hf():
    """Without HuggingFace datasets installed, hc3 should fall back to builtin."""
    import sys

    saved = sys.modules.pop("datasets", None)
    try:
        samples = load_samples("hc3", n=2)
        assert len(samples) == 2
    finally:
        if saved:
            sys.modules["datasets"] = saved
