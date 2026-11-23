"""The full-tier verdict is calibrated on held-out human text (calibration_full_v3.json).

These pin the RULE with synthetic detector scores, so they need no model: which path applies, and
that a detector giving most humans 1.0 no longer decides the verdict alone. The measured effect is
in docs/observatory/calibration.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from untell.scripts.score import DEFAULT_THRESHOLD, calibrated_verdict

GPT2 = {"perplexity_burstiness": "gpt2"}


_DET = Path(__file__).resolve().parents[1] / "untell/detectors"


def _table(version):
    return json.loads((_DET / f"calibration_full_{version}.json").read_text(encoding="utf-8"))


def test_the_shipped_table_names_the_six_detectors_and_its_provenance():
    cal = _table("v3")
    assert set(cal["detectors"]) == {"perplexity_burstiness", "roberta_openai", "hc3_roberta",
                                     "mage", "fast_detectgpt", "modernbert"}
    assert cal["fit_n"] == 868 and cal["target_fpr"] == 0.05 and "2022-11-30" in cal["_about"]
    for table in cal["detectors"].values():
        assert table == sorted(table) and len(table) == 201


def test_v3_only_adds_modernbert_to_v2():
    # v3 was fitted on the same 868 documents; the five detectors v2 already had must keep exactly
    # v2's tables, so the only change between the two verdicts is the new detector and its cut.
    v2, v3 = _table("v2"), _table("v3")
    assert v3["fit_n"] == v2["fit_n"]
    for name, table in v2["detectors"].items():
        assert v3["detectors"][name] == table, name


def test_v3_is_the_verdict_scoring_uses():
    from untell.scripts import score

    assert score._CALIBRATION_FILE.name == "calibration_full_v3.json"
    assert score._calibration()["cut"] == _table("v3")["cut"]


def test_mage_at_one_alone_no_longer_flags():
    # MAGE gave the median pre-2022 human document 1.000; on its own it must not decide a verdict.
    scores = {"mage": 1.0, "roberta_openai": 0.01, "hc3_roberta": 0.05, "fast_detectgpt": 0.08,
              "perplexity_burstiness": 0.2}
    agg, cut = calibrated_verdict(scores, GPT2, DEFAULT_THRESHOLD)
    assert agg < cut


def test_extreme_scores_on_reliable_detectors_still_flag():
    scores = {"mage": 1.0, "roberta_openai": 1.0, "hc3_roberta": 1.0, "fast_detectgpt": 0.99,
              "perplexity_burstiness": 0.9}
    agg, cut = calibrated_verdict(scores, GPT2, DEFAULT_THRESHOLD)
    assert agg >= cut


def test_an_explicit_threshold_keeps_the_raw_max_rule():
    assert calibrated_verdict({"mage": 1.0, "roberta_openai": 1.0}, GPT2, 0.2) is None


def test_it_does_not_apply_without_model_backed_detectors():
    assert calibrated_verdict({"perplexity_burstiness": 0.9}, {"perplexity_burstiness": "stdlib"},
                              DEFAULT_THRESHOLD) is None
    assert calibrated_verdict({"perplexity_burstiness": 0.9, "mage": 1.0}, GPT2,
                              DEFAULT_THRESHOLD) is None  # one model-backed detector is not enough


def test_error_sidecars_and_unknown_detectors_are_ignored():
    scores = {"roberta_openai": 0.5, "hc3_roberta": 0.5, "hc3_roberta__error": "x", "gptzero": 0.99}
    assert calibrated_verdict(scores, GPT2, DEFAULT_THRESHOLD) is not None
