"""Tests for the detector integrity audit.

The classification logic is tested with fakes (fast, no model downloads). The real-model check —
that no shipped detector is actually DEAD or INVERTED — lives in test_detectors_full.py behind the
torch guard, since it needs the models.
"""
from __future__ import annotations

from eval.detector_audit import audit_all, audit_detector, render


class _Fake:
    """A detector whose score is looked up per text, so behaviour can be dialled precisely."""

    def __init__(self, table, default=0.5, available=True, raises=False):
        self._table = table
        self._default = default
        self._available = available
        self._raises = raises

    def available(self):
        return self._available

    def score(self, text):
        if self._raises:
            raise RuntimeError("boom")
        return self._table.get(text, self._default)


def _const(value):
    """A detector that ignores its input entirely — the fast_detectgpt failure mode."""
    return _Fake({}, default=value)


def test_flags_constant_detector_as_dead():
    """The exact bug that shipped: same output regardless of input."""
    r = audit_detector("dead_one", _const(0.30))
    assert r["verdict"] == "DEAD"
    assert r["range"] < 0.05


def test_flags_inverted_detector():
    """Human scoring above AI means the sign/label convention is backwards."""
    from eval.detector_audit import AI_PROBES, HUMAN_PROBES

    table = {t: 0.9 for t in HUMAN_PROBES}
    table.update({t: 0.1 for t in AI_PROBES})
    r = audit_detector("inverted_one", _Fake(table))
    assert r["verdict"] == "INVERTED"
    assert r["gap"] < 0


def test_healthy_detector_is_ok_and_separated():
    from eval.detector_audit import AI_PROBES, HUMAN_PROBES

    table = {t: 0.1 for t in HUMAN_PROBES}
    table.update({t: 0.9 for t in AI_PROBES})
    r = audit_detector("good_one", _Fake(table))
    assert r["verdict"] == "OK_SEPARATED"
    assert r["gap"] > 0.5


def test_responsive_but_non_separating_is_weak_not_broken():
    """A detector that responds with real dynamic range but whose classes overlap heavily is a
    documented limitation, NOT a bug — it must not be reported as broken.

    This is the true shape of recalibrated fast_detectgpt: wide output range, tiny mean gap. Note
    the range check comes first by design — a detector with almost no spread (say 0.40 vs 0.42) is
    DEAD, not weak, however 'correct' its direction looks.
    """
    from eval.detector_audit import AI_PROBES, HUMAN_PROBES

    table = dict(zip(HUMAN_PROBES, [0.20, 0.40, 0.60, 0.30, 0.50]))
    table.update(zip(AI_PROBES, [0.25, 0.45, 0.65, 0.35, 0.52]))
    r = audit_detector("weak_one", _Fake(table))
    assert r["verdict"] == "WEAK"
    assert r["range"] > 0.05      # genuinely responsive
    assert 0 < r["gap"] < 0.05    # but the classes do not separate


def test_tiny_spread_is_dead_even_if_direction_is_right():
    """Range is checked before gap: near-zero spread means the detector contributes nothing,
    regardless of which way the means happen to lean."""
    from eval.detector_audit import AI_PROBES, HUMAN_PROBES

    table = {t: 0.40 for t in HUMAN_PROBES}
    table.update({t: 0.42 for t in AI_PROBES})
    assert audit_detector("barely_moves", _Fake(table))["verdict"] == "DEAD"


def test_unavailable_and_erroring_detectors_are_not_called_broken():
    """A detector that cannot load is correctly EXCLUDED from the ensemble — not a defect."""
    assert audit_detector("gone", _Fake({}, available=False))["verdict"] == "UNAVAILABLE"
    assert audit_detector("boom", _Fake({}, raises=True))["verdict"].startswith("SCORE_ERR")


def test_audit_all_reports_shape_and_render():
    report = audit_all()
    assert "results" in report and "broken" in report
    assert isinstance(report["broken"], list)
    assert {r["detector"] for r in report["results"]} >= {"perplexity_burstiness", "roberta_openai"}
    out = render(report)
    assert "detector" in out and "BROKEN" in out


def test_perplexity_burstiness_is_healthy():
    """The zero-dependency detector always runs, so its health is always assertable."""
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    r = audit_detector("perplexity_burstiness", PerplexityBurstinessDetector())
    assert r["verdict"] not in ("DEAD", "INVERTED"), r


# --- sentence granularity ----------------------------------------------------------------------
# perplexity_burstiness passed the paragraph audit while scoring AUROC 0.000 on single sentences,
# and sentences.py scores each sentence in isolation to pick rewrite targets. The audit now covers
# that granularity — but at a stricter bar, because six probes per class is 36 pairs and an AUROC
# near 0.5 is chance rather than evidence.


def test_sentence_probe_sets_exist_and_are_single_sentences():
    from eval.detector_audit import SENTENCE_AI_PROBES, SENTENCE_HUMAN_PROBES

    assert len(SENTENCE_AI_PROBES) >= 5 and len(SENTENCE_HUMAN_PROBES) >= 5
    for s in SENTENCE_AI_PROBES + SENTENCE_HUMAN_PROBES:
        assert s.rstrip().count(". ") == 0, f"probe is more than one sentence: {s!r}"


def test_audit_all_covers_sentence_granularity():
    report = audit_all()
    labels = {r["detector"] for r in report["results"]}
    assert any(d.endswith("[sentence]") for d in labels), "sentence rows missing from the audit"
    assert "perplexity_burstiness [sentence]" in labels


def test_perplexity_burstiness_is_healthy_on_single_sentences():
    """The regression this granularity was added for: it measured AUROC 0.000 here."""
    from eval.detector_audit import SENTENCE_AI_PROBES, SENTENCE_HUMAN_PROBES
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    r = audit_detector(
        "perplexity_burstiness",
        PerplexityBurstinessDetector(),
        (SENTENCE_HUMAN_PROBES, SENTENCE_AI_PROBES),
    )
    assert r["verdict"] not in ("DEAD", "INVERTED"), r
    assert r["auroc"] > 0.9, r


def test_near_chance_sentence_row_is_reported_but_not_called_broken():
    """fast_detectgpt scored 0.444 on these probes and was labelled INVERTED — then measured 0.915
    on 40 real HC3 sentence pairs. Gating a build on 36 pairs of noise is worse than not gating."""
    from eval.detector_audit import SENTENCE_BROKEN_AUROC

    assert 0.0 < SENTENCE_BROKEN_AUROC < 0.5
    rows = [
        {"detector": "x [sentence]", "verdict": "INVERTED", "auroc": 0.444, "granularity": "sentence"},
        {"detector": "y [sentence]", "verdict": "INVERTED", "auroc": 0.000, "granularity": "sentence"},
        {"detector": "z", "verdict": "INVERTED", "auroc": 0.444},
    ]
    broken = [
        r["detector"]
        for r in rows
        if r["verdict"] in ("DEAD", "INVERTED")
        and (r.get("granularity") != "sentence" or r.get("auroc") is None
             or r["auroc"] <= SENTENCE_BROKEN_AUROC)
    ]
    assert "x [sentence]" not in broken   # chance-level: reported, not fatal
    assert "y [sentence]" in broken       # a true inversion 36 pairs cannot produce by chance
    assert "z" in broken                  # paragraph rows keep the original, stricter treatment
