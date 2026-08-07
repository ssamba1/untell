"""Tests for the dataset loader — verifies builtin fallback and HF-backed loads."""
from __future__ import annotations

import pytest

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


class TestPairedCorporaBeyondHC3:
    """Every paired measurement in this repo ran on HC3 alone — 2022-era ChatGPT answering forum
    questions — and "we only have one dated corpus" was the stated reason several calibration
    problems went unfixed. RAID and MAGE were listed in _KNOWN_DATASETS but load_pairs refused
    them, so the hole was invisible: callers got [] and a warning.

    RAID matters most: multi-domain, multi-generator, and EXACTLY paired — every machine row
    carries the source_id of the human document it came from. MEASURED on the first 4000 rows:
    493 source_ids, all 493 with both sides.
    """

    def test_load_pairs_handles_raid_and_mage(self):
        """A name in _KNOWN_DATASETS that load_pairs rejects is a silent hole — every measurement
        quietly falls back to HC3 while reporting whatever name was asked for."""
        import inspect

        from eval import datasets as ds

        src = inspect.getsource(ds.load_pairs)
        for name in ("raid", "mage"):
            assert f'"{name}"' in src, f"load_pairs has no branch for {name}"
            assert hasattr(ds, f"_{name}_pairs"), f"no _{name}_pairs loader"

    def test_unknown_dataset_returns_empty_rather_than_substituting(self):
        """Substituting another corpus under the requested name is how a demo corpus ends up
        reported as real-text results."""
        from eval.datasets import load_pairs

        assert load_pairs("no-such-corpus", n=3) == []

    def test_raid_excludes_adversarially_attacked_rows(self):
        """RAID ships perturbed copies (homoglyph, whitespace, synonym). Mixing them in answers
        'how does a detector survive an attack' instead of the question being asked."""
        import inspect

        from eval import datasets as ds

        assert "attack" in inspect.getsource(ds._raid_pairs)

    def test_mage_is_documented_as_domain_matched_not_prompt_paired(self):
        """MAGE has no key linking a machine sample to its human source; pairing is on the `src`
        domain prefix. Reporting that as equivalent to HC3/RAID pairing would overstate it."""
        import inspect

        doc = inspect.getdoc(__import__("eval.datasets", fromlist=["_mage_pairs"])._mage_pairs)
        assert "not** prompt-paired" in doc or "not prompt-paired" in doc.replace("**", "")

    def test_raid_pairs_are_distinct_and_meet_min_words(self):
        """Network-dependent: skipped when the corpus cannot be reached."""
        from eval.datasets import load_pairs

        pairs = load_pairs("raid", n=4, min_words=60)
        if not pairs:
            pytest.skip("RAID unavailable (no network, or missing the .[eval] extra)")
        for human, ai in pairs:
            assert human.strip() and ai.strip()
            assert human != ai, "a pair must not be the same text twice"
            assert len(human.split()) >= 60 and len(ai.split()) >= 60
