"""Tests for the local LLaMA-as-judge detector — offline (no model download)."""
from __future__ import annotations

from untell.detectors.local_judge import LocalJudgeDetector


def test_unavailable_without_torch():
    """Without torch/transformers, available() must return False."""
    d = LocalJudgeDetector()
    # On a CI/clean install without torch, this is False.
    # We validate the contract: if unavailable, score returns None.
    if not d.available():
        assert d.score("some text") is None


def test_empty_input_returns_none(monkeypatch):
    d = LocalJudgeDetector()
    monkeypatch.setattr(d, "available", lambda: True)
    assert d.score("   ") is None


def test_registered_in_detector_list():
    from untell.detectors.base import all_detectors

    names = {d.name for d in all_detectors()}
    assert "local_judge" in names


def test_every_model_size_is_heavy_tier():
    """An LLM generation per candidate is heavy-tier work at any parameter count.

    The 1.5B model used to be "full" — the documented default tier — but score() raised on every
    call, so nothing noticed the cost. Measured once it worked: 3.71s warm per call against
    0.03-0.06s for every other full-tier detector, for AUROC 0.514 over 40 labelled HC3 pairs.
    """
    for model_id in ("Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-7B-Instruct"):
        assert LocalJudgeDetector(model_id=model_id).tier == "heavy"


def test_local_judge_is_not_in_the_default_full_tier(monkeypatch):
    """Pins the cost decision where a caller can see it: --tier full must stay fast."""
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")
    monkeypatch.delenv("UNTELL_ENABLE_LOCAL_JUDGE", raising=False)
    from untell.detectors.base import load_detectors

    assert "local_judge" not in {d.name for d in load_detectors("full")}


def test_local_judge_is_not_in_the_default_heavy_tier_either(monkeypatch):
    """It does not discriminate, and `max` aggregation let it decide the tier's verdict.

    MEASURED on 20 labelled HC3 pairs at the default threshold: local_judge alone scores human text
    at a mean of 0.853 and flags 89% of it, for AUROC 0.591 — barely above chance. Because the
    ensemble takes `max`, the heavy tier inherited that: 90% of human documents flagged, against
    15% for full. The strongest tier was the least trustworthy, and the loop would then rewrite
    text that was already human.
    """
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")
    monkeypatch.delenv("UNTELL_ENABLE_LOCAL_JUDGE", raising=False)
    from untell.detectors.base import load_detectors

    assert "local_judge" not in {d.name for d in load_detectors("heavy")}


def test_local_judge_can_still_be_opted_into(monkeypatch):
    """Opt-in, not deleted — the same shape RADAR uses, so it stays usable for experiments."""
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")
    monkeypatch.setenv("UNTELL_ENABLE_LOCAL_JUDGE", "1")
    from untell.detectors.base import load_detectors

    d = LocalJudgeDetector()
    if not d.available():
        import pytest

        pytest.skip("torch/transformers unavailable")
    assert "local_judge" in {x.name for x in load_detectors("heavy")}
