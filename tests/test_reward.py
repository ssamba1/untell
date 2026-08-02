"""Training-reward tests.

A wrong reward is not a misreported number — it is the thing the model learns, so a silent
failure here costs GPU hours and yields an adapter trained on noise.
"""

from __future__ import annotations

import pytest


def test_sim_floor_adapts_to_the_active_similarity_metric(monkeypatch):
    """similarity() is backend-adaptive (BERTScore 0.88 / embedding 0.76 / token-overlap 0.50), so a
    hard-coded 0.76 floor was only meaningful for the middle one.

    With no sentence-transformers installed — a lightweight/CPU training box — similarity() falls
    back to token overlap, where 0.76 is ~50% too strict. A faithful paraphrase was then hard-gated
    to -1.0, the SAME reward as an off-topic rewrite, so every meaningful candidate scored -1.0 and
    GRPO learned to make trivially small edits while the loss curve looked plausible."""
    import training.reward as r
    import untell.scripts.quality as q

    orig = "Furthermore, the program runs in a consistent and predictable fashion throughout."
    cand = "Furthermore, the system operates in a predictable and uniform manner throughout."

    monkeypatch.setattr(q, "method", lambda: "token_overlap")
    monkeypatch.setattr(r, "recommended_bar", lambda: q.TOKEN_BAR)
    monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 0.1)

    # The old hard-coded floor would have gated this faithful paraphrase.
    assert q.similarity(orig, cand) < 0.76
    # With the metric-appropriate floor it is not gated and earns a real reward.
    assert q.similarity(orig, cand) >= q.TOKEN_BAR
    assert r.humanness_reward(orig, cand) > -1.0


def test_off_topic_rewrite_is_still_hard_gated(monkeypatch):
    """The gate must still do its job — meaning stays non-negotiable."""
    import training.reward as r
    import untell.scripts.quality as q

    monkeypatch.setattr(q, "method", lambda: "token_overlap")
    monkeypatch.setattr(r, "recommended_bar", lambda: q.TOKEN_BAR)
    monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 0.0)

    orig = "Furthermore, the program runs in a consistent and predictable fashion throughout."
    off_topic = "Quarterly revenue exceeded analyst expectations on strong enterprise demand."
    assert r.humanness_reward(orig, off_topic) == -1.0


def test_out_of_range_sidecar_cannot_enter_the_weighted_mean(monkeypatch):
    """score_text records a clamped value plus the raw one. If the raw value leaks into the reward's
    weighted mean as a phantom detector, a correct ~0.75 reward becomes ~-49.5."""
    import training.reward as r

    monkeypatch.setattr(
        r, "score_text",
        lambda text, tier="full": {
            "detectors": {"gptzero": 1.0},   # clamped only — the raw value lives outside this dict
            "max": 1.0,
            "out_of_range_raw": {"gptzero": 100.0},
        },
    )
    assert r.free_ensemble_score("some text", tier="full") == 1.0


def test_no_detector_signal_refuses_to_return_a_reward(monkeypatch):
    """`res["max"]` is a 0.0 PLACEHOLDER when nothing scored, and 0.0 means "not AI at all" — so
    the reward came back as 1.0, the MAXIMUM evasion credit, for text no detector ever looked at.

    A GRPO/DPO run against a broken ML stack would optimise a constant perfect reward: every
    candidate ties, the gradient carries no information, and hours of GPU time produce an adapter
    trained on nothing, with no error anywhere to show it.

    Same unscored-placeholder bug as humanness() and report._bypass_rate — worst here, because a
    wrong reward is not a misreported number, it is the thing the model learns.
    """
    import training.reward as R

    monkeypatch.setattr(R, "score_text", lambda text, tier="full", threshold=0.30: {
        "tier": "lite", "detectors": {"d__error": "boom"}, "max": 0.0, "mean": 0.0,
        "threshold": threshold, "flagged": False, "scored": False,
        "warning": "no detector produced a score", "failed_detectors": ["d"],
    })
    text = "original text here that is long enough to clear the length gate"
    with pytest.raises(RuntimeError, match="no training signal"):
        R.humanness_reward(text, text, sim_floor=0.0)


def test_partial_detector_failure_still_scores(monkeypatch):
    """One dead detector must NOT abort training — only a total absence of signal does. The
    surviving detectors are renormalized, which is the documented behaviour."""
    import training.reward as R

    monkeypatch.setattr(R, "score_text", lambda text, tier="full", threshold=0.30: {
        "tier": "full",
        "detectors": {"hc3_roberta": 0.80, "mage__error": "boom", "mage": None},
        "max": 0.80, "mean": 0.80, "threshold": threshold, "flagged": True,
        "failed_detectors": ["mage"],
    })
    assert R.free_ensemble_score("some text here") == pytest.approx(0.80)


def test_fast_reward_path_needs_no_detectors(monkeypatch):
    """UNTELL_REWARD_FAST=1 is the documented escape hatch named in the error message, so it must
    not depend on the detector stack it exists to avoid."""
    import training.reward as R

    monkeypatch.setenv("UNTELL_REWARD_FAST", "1")

    def _boom(*a, **k):
        raise AssertionError("the fast path must not call score_text")

    monkeypatch.setattr(R, "score_text", _boom)
    text = "Furthermore, we leverage robust solutions to delve into the realm of synergy."
    assert -1.0 <= R.humanness_reward(text, text, sim_floor=0.0) <= 1.0
