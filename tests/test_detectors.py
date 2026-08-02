"""Detector contract tests — run in the lite tier with zero ML installed."""

from __future__ import annotations

import pytest

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
    for text in (AI_TEXT, HUMAN_TEXT):
        s = d.score(text)
        assert s is not None and 0.0 <= s <= 1.0
    # "x" is below the minimum word count: the answer is None (no signal), not a number. It used
    # to score 0.0 — a confident "definitely human" for a single character.
    assert d.score("x") is None


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


# --- single-sentence scoring was perfectly inverted -------------------------------------------
# On a lone sentence, burstiness is undefined, so the score fell back to the common-word ratio
# alone. That ratio was calibrated for an older kind of AI text: modern model prose reaches for
# inflated vocabulary ("leverage", "transformative"), which drives the ratio DOWN, while casual
# human speech is almost entirely common words, which drives it UP. Measured AUROC over the pairs
# below was 0.000 — every AI sentence ranked below every human one.
#
# It mattered because sentences.py scores each sentence in isolation: per-sentence targeting was
# pointing the rewriter at whichever sentences read most human.

_AI_SENTENCES = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
    "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
    "This robust framework enables stakeholders to seamlessly navigate complex challenges.",
    "In today's rapidly evolving landscape, businesses must delve into innovative solutions.",
    "It is important to note that this underscores the importance of robust solutions.",
]
_HUMAN_SENTENCES = [
    "I went to the store and forgot the milk again.",
    "The build broke because someone bumped the pinned version.",
    "She said it was fine, but her face said otherwise.",
    "We tried it twice and it still didn't work.",
    "He emailed me back three days later with one line.",
]


def test_single_sentence_scoring_is_not_inverted():
    """The whole point: AI single sentences must outrank human ones. AUROC was 0.000."""
    ai = [lite_score(s) for s in _AI_SENTENCES]
    human = [lite_score(s) for s in _HUMAN_SENTENCES]
    pairs = [(a, h) for a in ai for h in human]
    auroc = sum((a > h) + 0.5 * (a == h) for a, h in pairs) / len(pairs)
    assert auroc > 0.9, f"single-sentence AUROC {auroc:.3f} — was 0.000 (perfectly inverted)"


def test_ordinary_human_sentences_are_not_flagged():
    """The common-word term is the one measured to be backwards, so it is capped below the default
    0.30 threshold. At a 0.35 cap every plain human sentence landed on exactly 0.350 and flagged."""
    from untell.scripts.score import DEFAULT_THRESHOLD

    for s in _HUMAN_SENTENCES:
        assert lite_score(s) < DEFAULT_THRESHOLD, f"false positive on human sentence: {s!r}"


def test_ai_single_sentences_are_flagged():
    from untell.scripts.score import DEFAULT_THRESHOLD

    for s in _AI_SENTENCES:
        assert lite_score(s) >= DEFAULT_THRESHOLD, f"AI sentence not flagged: {s!r}"


def test_tells_failure_does_not_restore_the_inverted_ratio(monkeypatch):
    """If tells raises, the fallback must stay capped — never hand the verdict back to the term
    that was measured backwards."""
    import untell.detectors.perplexity_burstiness as pb

    def boom(*a, **k):
        raise RuntimeError("tells exploded")

    monkeypatch.setattr("untell.scripts.tells.score_tells", boom)
    # A sentence of almost entirely common words: the inverted ratio would score this very high.
    assert pb.lite_score("We tried it twice and it still did not work.") <= pb._RATIO_CEILING


def _torch_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("torch") is not None


@pytest.mark.skipif(not _torch_available(), reason="full GPT-2 path needs torch")
def test_full_gpt2_path_is_not_inverted_on_single_sentences():
    """The lite fix left this broken, and a lite-only test did not notice.

    With torch installed the detector takes the GPT-2 path, where a lone sentence had no burstiness
    and fell back to perplexity alone — measured human_mean 0.224 vs ai_mean 0.154, inverted. The
    logistic midpoint is fitted to paragraph-length text, and at sentence length the quantity flips
    sign for this distribution: casual human speech is highly predictable, modern formal AI prose
    reaches for rarer words that GPT-2 finds more surprising.

    This test is deliberately run through the detector object, not `lite_score`, so it exercises
    whichever backend is actually installed.
    """
    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch present but the GPT-2 path did not initialise")

    ai = [det.score(s) for s in _AI_SENTENCES]
    human = [det.score(s) for s in _HUMAN_SENTENCES]
    assert all(v is not None for v in ai + human)
    pairs = [(a, h) for a in ai for h in human]
    auroc = sum((a > h) + 0.5 * (a == h) for a, h in pairs) / len(pairs)
    assert auroc > 0.9, f"full-path single-sentence AUROC {auroc:.3f} (was inverted)"


# A bland, predictable sentence in the HC3 register: zero AI tells, but exactly the kind of text
# GPT-2 perplexity is good at. It is the case that exposed a regression where a 0.25 cap was
# applied to the GPT-2 path as well as the lite one.
_BLAND_AI_SENTENCE = "There are several factors that can affect the performance of a computer system."


def test_bland_sentence_has_no_tells():
    """Guard the guard: if this ever gains a tell, the two tests below stop testing the cap."""
    from untell.scripts.tells import score_tells

    assert score_tells(_BLAND_AI_SENTENCE)["tells"] == 0


@pytest.mark.skipif(not _torch_available(), reason="GPT-2 path needs torch")
def test_gpt2_single_sentence_is_not_capped_at_the_lite_ceiling():
    """Ranking and calibration fail independently, and only ranking was checked the first time.

    Capping the GPT-2 path at _RATIO_CEILING left AUROC at 0.971 — ordering intact — while pinning
    every real HC3 AI sentence to exactly 0.250, below the 0.30 threshold. `sentences.py` flags the
    worst third AND requires >= threshold, so per-sentence targeting flagged 0 of 46 sentences
    across six AI paragraphs. The cap belongs only to the lite term, which is genuinely backwards.
    """
    from untell.detectors.perplexity_burstiness import _RATIO_CEILING

    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch present but the GPT-2 path did not initialise")
    score = det.score(_BLAND_AI_SENTENCE)
    assert score > _RATIO_CEILING, (
        f"GPT-2 single-sentence score {score} is at or below the lite cap {_RATIO_CEILING} — "
        "per-sentence flagging cannot fire"
    )


def test_lite_single_sentence_keeps_the_ceiling():
    """The lite term stays capped: it is the one measured backwards, and must not flag alone."""
    from untell.detectors.perplexity_burstiness import _RATIO_CEILING

    # A tell-free sentence can never exceed the ceiling on the lite path.
    for s in _HUMAN_SENTENCES + [_BLAND_AI_SENTENCE]:
        assert lite_score(s) <= _RATIO_CEILING + 1e-9, f"lite cap breached by {s!r}"


def test_perplexity_burstiness_is_deliberately_not_windowed():
    """Pins a negative result, because this looks like a missing feature and was once "fixed".

    Every supervised adapter wraps its scorer in `windowed_max`, because `truncation=True,
    max_length=512` meant they could not see past ~380 words. This detector has no such limit and
    both its terms are aggregate: burstiness is the variation of sentence lengths ACROSS a
    document, and the common-word ratio is a document-wide proportion. Windowing destroys the
    quantity being measured, and max-of-many-noisy-windows inflates long input.

    MEASURED on real HC3 documents, windowed vs whole-document:
        3 paragraphs   AUROC 0.887 / FPR 90%   vs   0.975 / FPR 30%
        6 paragraphs   AUROC 0.980 / FPR 90%   vs   1.000 / FPR  0%
    TPR was 100% either way — windowing bought nothing and flagged 9 of 10 human documents.
    """
    import inspect

    import untell.detectors.perplexity_burstiness as pb

    assert "windowed_max(" not in inspect.getsource(pb.PerplexityBurstinessDetector.score), (
        "perplexity_burstiness must stay whole-document: windowing it measured AUROC 0.887 vs "
        "0.975 and FPR 90% vs 30% on 3-paragraph HC3 documents"
    )


def test_long_document_scoring_is_stable_not_inflated():
    """A long stretch of ordinary human prose must not become AI-flagged just for being long.

    This is the failure mode that windowing this detector produced: the max over many windows of a
    weak signal climbs with document length regardless of content.
    """
    human = (
        "I went to the store and forgot the milk again. "
        "The build broke because someone bumped the pinned version, which took a while to find. "
        "She said it was fine, but her face said otherwise and I let it go. "
        "We tried it twice and it still did not work, so we went home. "
        "Turns out the cable was loose the whole time, which nobody had checked. "
    )
    det = PerplexityBurstinessDetector()
    short = det.score(human)
    long_ = det.score(human * 12)
    assert short is not None and long_ is not None
    # Repetition genuinely reads as machine-uniform, so this asserts the weaker property that
    # matters: length alone must not drive the score up without bound.
    assert long_ <= short + 0.35, f"score inflated with length: {short:.3f} -> {long_:.3f}"
