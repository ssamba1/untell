"""Half this repository's constants had no stated reason, and the worst were not constants at all.

Rounds eighty-six and eighty-seven each swept one unchosen parameter under a published claim. Two
instances is an anecdote, so round eighty-nine counted them: **111 module-level numeric constants
across `untell/` and `eval/`, 49 of them with nothing anywhere saying why they hold that value.**

The sharper half of the finding is what a census of *assignments* cannot see. `lite_score` — the
function every headline figure in this repository is computed by — ended in five bare literals:

    common_signal = clamp01((common - 0.30) / 0.30)
    burst_signal  = clamp01((0.55 - burst) / 0.55)
    return clamp01(max(rep, 0.6 * burst_signal + 0.4 * common_signal))

They are named constants now, and `eval/constant_sensitivity.py` sweeps them over the same two arms
that produced the published AUROC. **MEASURED across 30 settings of five parameters: not one brings
the AUROC above 0.5** (range 0.3103–0.4131 against 0.3538 shipped). The inversion on academic
abstracts is not reachable from the detector's calibration.

These tests hold three things in place: the sweep must stay faithful to the shipped function, the
scoring functions must stay free of unexplained inline numbers, and the inversion's independence
from the constants must be re-derivable rather than asserted.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from eval import constant_census as census
from eval import constant_sensitivity as cs
from untell.detectors import perplexity_burstiness as pb

REPO = Path(__file__).resolve().parent.parent
SWEEP = json.loads((REPO / "eval" / "data" / "constant_sensitivity.json").read_text())
CENSUS = json.loads((REPO / "eval" / "data" / "constant_census.json").read_text())

CACHE = REPO / ".anthology-cache"
needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)

SAMPLES = [
    "We propose a novel neural architecture for machine translation. It improves BLEU by two "
    "points on WMT. We evaluate on four language pairs and release all code and data.",
    "The bus never came. I waited twenty minutes in the rain, then gave up and walked, and of "
    "course it passed me two streets later with empty seats.",
    "One single sentence standing alone with quite enough words in it to be scored properly here.",
    "Short one.",
    "",
]


def test_the_sweep_is_faithful_to_the_shipped_function():
    """Everything else here is worthless if `score_from` is not `lite_score`."""
    report = cs.verify_reimplementation(SAMPLES, limit=None)
    assert report["faithful"], report
    assert report["worst_gap"] == 0.0, "exact, not close — the arithmetic is the same arithmetic"


def test_the_sweep_reads_its_defaults_from_the_detector():
    """A sweep with its own copy of the constants measures numbers the detector may not use."""
    assert cs.DEFAULTS.common_mid == pb._COMMON_MID
    assert cs.DEFAULTS.common_scale == pb._COMMON_SCALE
    assert cs.DEFAULTS.burst_mid == pb._BURST_MID
    assert cs.DEFAULTS.burst_scale == pb._BURST_SCALE
    assert cs.DEFAULTS.burst_weight == pb._BURST_WEIGHT


def test_naming_the_constants_changed_no_score():
    """The refactor's whole licence is that it is invisible from outside."""
    assert pb._COMMON_MID == 0.30
    assert pb._COMMON_SCALE == 0.30
    assert pb._BURST_MID == 0.55
    assert pb._BURST_SCALE == 0.55
    assert pb._BURST_WEIGHT == 0.60
    for text in SAMPLES:
        feat = cs.features(text)
        shipped = pb.lite_score(text)
        if feat is None or shipped is None:
            assert feat is None and shipped is None
            continue
        assert cs.score_from(feat, cs.DEFAULTS, text=text) == shipped


def test_no_scoring_function_contains_an_unexplained_number():
    """The literals in `lite_score` were invisible to a census for as long as they existed."""
    report = census.census()
    assert report["inline_literals_in_scoring_functions"] == 0, [
        f"{e['file']}:{e['line']} in {e['function']}() -> {e['value']}" for e in report["inline"]
    ]


def test_the_census_still_finds_the_constants_it_claims_to():
    """A scan that silently stops matching reports a clean repository."""
    report = census.census()
    assert report["named_constants"] > 100, "the scan found almost nothing — it is broken"
    assert report["named_undefended"] > 0, (
        "zero undefended constants means the justification test started matching everything; "
        "the check would then pass forever without being able to fail"
    )


def test_the_inversion_does_not_come_from_the_calibration():
    """The round-89 finding, and the one a later edit is most likely to soften."""
    assert SWEEP["inversion_survives_every_setting"] is True
    aurocs = [row["auroc"] for rows in SWEEP["sweeps"].values() for row in rows]
    assert len(aurocs) >= 25, "too few settings to establish anything"
    assert max(aurocs) < 0.5, (
        "some setting of a constant nobody chose puts the AUROC above 0.5 — the headline finding "
        "would then be a statement about this calibration, not about the detector"
    )


def test_every_parameter_actually_moves_the_score():
    """A sweep over a parameter the score ignores proves nothing about robustness."""
    for name, rows in SWEEP["sweeps"].items():
        aurocs = {row["auroc"] for row in rows}
        assert len(aurocs) > 1, f"{name} changed nothing — it is not reaching the score"
        assert any(row["shipped"] for row in rows), f"{name} never tests its shipped value"


def test_the_shipped_blend_is_not_the_best_one_on_this_corpus():
    """Reported because it is awkward: the weights favour the weaker signal on this register."""
    weights = {row["value"]: row["auroc"] for row in SWEEP["sweeps"]["burst_weight"]}
    assert weights[0.0] < weights[1.0], (
        "the common-word signal should discriminate further from 0.5 than burstiness here, "
        "matching round 79's independently measured component AUROCs"
    )


def test_the_verdict_would_change_if_the_measurement_did():
    """A renderer that cannot report the bad news is not reporting."""
    good = cs.render(SWEEP)
    assert "not a calibration artefact" in good

    bad = json.loads(json.dumps(SWEEP))
    bad["inversion_survives_every_setting"] = False
    bad["summary"][0]["any_above_half"] = True
    assert "DOES depend on a constant nobody chose" in cs.render(bad)


@needs_corpus
def test_the_committed_sweep_is_what_the_code_produces():
    machine, human = cs.build_arms(CACHE)
    fresh = cs.sweep(machine, human, threshold=SWEEP["threshold"])
    assert fresh["sweeps"] == SWEEP["sweeps"]
    assert fresh["base"] == SWEEP["base"]


def test_a_changed_constant_changes_the_score_not_just_the_report():
    """Guards `score_from` against ignoring the parameters it is handed."""
    feat = cs.features(SAMPLES[0])
    assert feat is not None
    base = cs.score_from(feat, cs.DEFAULTS, text=SAMPLES[0])
    moved = cs.score_from(feat, replace(cs.DEFAULTS, burst_weight=0.0), text=SAMPLES[0])
    assert base != moved
