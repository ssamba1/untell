

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
