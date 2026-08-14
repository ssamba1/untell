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

    # `method` alone, deliberately. Stubbing `recommended_bar` as well used to short-circuit the
    # very adaptation this test is named for: `recommended_bar()` reads `method()`, so pinning both
    # meant the `method` stub was never called and the chain under test never ran. FOUND by counting
    # monkeypatch stubs that are never invoked — 404 installed across the suite, 52 never called.
    monkeypatch.setattr(q, "method", lambda: "token_overlap")
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
    monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 0.0)

    orig = "Furthermore, the program runs in a consistent and predictable fashion throughout."
    off_topic = "Quarterly revenue exceeded analyst expectations on strong enterprise demand."
    assert r.humanness_reward(orig, off_topic) == -1.0


def test_faithful_paraphrase_the_loop_accepts_is_not_gated(monkeypatch):
    """The reward's meaning gate must agree with the deployed loop's.

    The loop gates candidates on `meaning_preserved` (NLI contradiction + bidirectional
    entailment when the stack is present), NOT on a raw similarity bar. The reward used to gate
    on `similarity >= recommended_bar()`, so a faithful paraphrase that the loop's own gate
    admits — measured 0.664-0.704 against the 0.76 embedding cosine bar — earned -1.0, the SAME
    reward as an off-topic rewrite. The policy then had no gradient toward the paraphrases the
    deployed loop accepts. The docstring's own measurement of the raw cosine gate admits 4 of 11
    meaning-broken rewrites; NLI admits 0 of 11, so aligning the reward with the loop is not a
    loosening of the gate, it is the gate the loop actually ships.
    """
    import training.reward as r

    orig = "The cat sat on the mat in the warm afternoon sun, perfectly content."
    faithful = "The feline rested upon the rug during the sunny afternoon, quite satisfied."
    # Sanity: the raw cosine bar WOULD have gated this (the old behavior).
    from untell.scripts.quality import similarity

    assert similarity(orig, faithful) < 0.76
    # The loop's meaning gate admits it (NLI present in the test env), so the reward must too.
    from untell.scripts.entailment import meaning_preserved

    assert meaning_preserved(orig, faithful, similarity(orig, faithful), 0.76)
    assert r.humanness_reward(orig, faithful, tier="lite") > -1.0


class TestTheGateIsTheWorstOutcome:
    """A gate-PASSING candidate must never rank below a gate-FAILING one.

    The gates pay -1.0 — "no evasion credit" — which is only a meaningful punishment if nothing
    scored can go lower. The continuous path had no lower bound: tells_penalty is
    ``_TELLS_W * tells_per_100w`` and that rate is unbounded. MEASURED on the free ensemble, a
    27-word candidate made of 26 catalogued tells scored -1.4445, below the gate. GRPO normalises
    rewards within a group, so ordering is the entire signal: the policy was being taught that
    abandoning the meaning beat keeping it.
    """

    # 27 words, 26 catalogued tells -> 96.3 per 100w -> a 1.4445 penalty on its own.
    TELL_SATURATED = (
        "Moreover, utilize the robust, seamless, holistic, paradigm, leverage, "
        "elevate, foster, bolster, garnered, pivotal, transformative, innovative, "
        "noteworthy, groundbreaking, comprehensive, nuanced, meticulous, vibrant, "
        "bustling, multifaceted, intricate, paramount, plethora, myriad."
    )

    def test_a_tell_saturated_but_faithful_rewrite_stays_above_the_gate(self, monkeypatch):
        import training.reward as r

        monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 1.0)
        # Identical text: similarity 1.0 and equal length, so both hard gates pass.
        reward = r.humanness_reward(self.TELL_SATURATED, self.TELL_SATURATED, sim_floor=0.0)
        assert reward > -1.0, "a gate-passing candidate scored at or below the gate"
        assert reward == r._MIN_SCORED_REWARD

    def test_it_still_ranks_below_a_faithful_clean_rewrite(self, monkeypatch):
        """Flooring must not flatten the ordering that matters."""
        import training.reward as r

        monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 0.1)
        clean = "Exercise makes the heart stronger and lifts the mood over time."
        good = r.humanness_reward(clean, clean, sim_floor=0.0)
        bad = r.humanness_reward(self.TELL_SATURATED, self.TELL_SATURATED, sim_floor=0.0)
        assert good > bad > -1.0

    def test_the_penalties_are_still_applied_below_saturation(self, monkeypatch):
        """The floor must be a floor, not a flat rate — normal tell densities still cost."""
        import training.reward as r

        monkeypatch.setattr(r, "target_ai_score", lambda text, tier="full": 0.2)
        plain = "The report covers the third quarter and the outlook for the next one."
        telly = "Moreover, the report delves into the third quarter. Furthermore, it is important "
        telly += "to note the outlook, showcasing a robust and multifaceted landscape."
        assert r.humanness_reward(plain, plain, sim_floor=0.0) > r.humanness_reward(
            telly, telly, sim_floor=0.0
        )

    def test_the_floor_sits_above_the_gate_value(self):
        import training.reward as r

        assert r._MIN_SCORED_REWARD > r._GATE_REWARD


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
