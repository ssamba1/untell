"""Detector contract tests — run in the lite tier with zero ML installed."""

from __future__ import annotations

from untell.detectors.base import clamp01, load_detectors, resolved_tier
from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector, lite_score

AI_TEXT = (
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it has "
    "enabled organizations to improve efficiency. Furthermore, it can analyze data quickly. "
    "Overall, the impact continues to grow significantly across various sectors."
)
HUMAN_TEXT = (
    "I almost missed the bus. Rain again — of course. My shoes were soaked through by the time "
    "the 8:14 finally rattled up, half-empty, smelling faintly of wet dog and someone's coffee, "
    "and I squeezed into the corner seat I always grab when nobody beats me to it. Worth it."
)


def test_lite_detector_always_available():
    d = PerplexityBurstinessDetector()
    assert d.available() is True
    assert d.tier == "lite"


def test_scores_in_unit_interval():
    d = PerplexityBurstinessDetector()
    for text in (AI_TEXT, HUMAN_TEXT, "x"):
        s = d.score(text)
        assert 0.0 <= s <= 1.0


def test_empty_text_returns_none_not_a_number():
    """Protocol (base.py): empty/too-short input must return None so the ensemble EXCLUDES it.

    This previously returned 0.5, which is not "neutral" — it is a fabricated score folded into the
    max/mean aggregation, and score_text("") duly reported flagged=True for an empty string.
    """
    d = PerplexityBurstinessDetector()
    for text in ("", "   ", "\n\t "):
        assert d.score(text) is None


def test_empty_text_is_not_flagged_by_the_ensemble():
    from untell.scripts.score import score_text

    r = score_text("", tier="lite")
    assert r["flagged"] is False
    assert r["detectors"]["perplexity_burstiness"] is None  # excluded, not scored


def test_single_sentence_can_reach_below_the_threshold():
    """Single-sentence inputs used to have a hard floor of exactly 0.30 — the detection threshold —
    because an "undefined" burstiness contributed a fixed 0.6 * 0.5. Every single sentence therefore
    sat on the decision boundary regardless of content. The lower range must be reachable."""
    plain = lite_score("Mitochondrial ribosomes synthesize hydrophobic peptides.")
    formulaic = lite_score("It is important to note that this is the best way to do the thing.")
    assert plain < 0.30              # was pinned at exactly 0.30
    assert formulaic > plain         # and the signal still discriminates on one sentence


def test_ai_scores_higher_than_human_lite():
    # The lite heuristic is weak, but should still rank formulaic AI text above bursty human text.
    assert lite_score(AI_TEXT) > lite_score(HUMAN_TEXT)


def test_load_detectors_never_empty_and_lite_present():
    dets = load_detectors("lite")
    assert dets, "lite tier must always yield at least the heuristic detector"
    assert any(d.name == "perplexity_burstiness" for d in dets)
    assert resolved_tier(dets) == "lite"


def test_full_tier_degrades_to_available():
    # Without torch installed, requesting 'full' still only returns available detectors.
    dets = load_detectors("full")
    for d in dets:
        assert d.available()


def test_clamp01():
    assert clamp01(-1.0) == 0.0
    assert clamp01(2.0) == 1.0
    assert clamp01(0.5) == 0.5
    assert clamp01(float("nan")) == 0.5


def test_new_detectors_registered():
    from untell.detectors.base import all_detectors

    names = {d.name for d in all_detectors()}
    assert "hc3_roberta" in names
    assert "radar" in names


def test_radar_is_opt_in_gated(monkeypatch):
    # RADAR is non-commercial licensed -> excluded unless UNTELL_ENABLE_RADAR is set, even with torch.
    from untell.detectors.radar import RadarDetector

    monkeypatch.delenv("UNTELL_ENABLE_RADAR", raising=False)
    assert RadarDetector().available() is False


def test_mage_direct_load_scores():
    # Heavy: downloads yaful/MAGE (~600MB). Opt-in via UNTELL_TEST_MAGE=1. Verifies the pipeline-free
    # direct load works on a modern transformers/numpy stack (the fix that un-breaks MAGE).
    import os

    import pytest

    if os.environ.get("UNTELL_TEST_MAGE") != "1":
        pytest.skip("set UNTELL_TEST_MAGE=1 to load yaful/MAGE (~600MB)")
    from untell.detectors.mage import MageDetector

    MageDetector._dead = False  # reset any prior-session failure latch
    d = MageDetector()
    s = d.score("Furthermore, this underscores a pivotal and transformative paradigm shift.")
    assert s is not None and 0.0 <= s <= 1.0
    assert MageDetector._dead is False
