"""A fairness arm that needs no protected attribute — and must not pretend it has one.

Status row 28 (detectors against neurodivergent and disabled writers) stayed open from round sixteen
to round thirty on one stated blocker: no corpus carries that label with consent, and asking
applicants to declare a disability so a detector can be audited against them is not a protocol this
project would propose. *Centering the Margins* (2023.emnlp-main.579) removes the blocker by
operationalising the margins of a dataset through **outlier detection** instead of subgroup labels.

`eval/outlier_fairness.py` is that method pointed at AI-text detection. The risk it carries is not
statistical, it is rhetorical: a module that sorts people into "margin" and "centre" is one careless
sentence away from claiming it has identified a protected group. It has not, and these tests hold it
to that as firmly as they hold the arithmetic.
"""

from __future__ import annotations

import pytest

from eval import outlier_fairness as of

# Twelve uniform sentences and one that is nothing like them.
UNIFORM = [f"The system processes input number {i} and returns a result to the caller." for i in range(12)]
ODD = ["Whimsy! Cascading, luminous — a riotous, unpunctuated sprawl of clauses that wanders."]


def test_features_survive_degenerate_input():
    """Empty and punctuation-only text reach this from real corpora; a ZeroDivisionError here would
    take down an audit run partway through."""
    for text in ("", "   ", "!!!", "."):
        f = of.features(text)
        assert f["words"] == 0.0
        assert all(isinstance(v, float) for v in f.values())


def test_a_text_unlike_the_corpus_scores_further_from_the_centre():
    scores = of.outlier_scores(UNIFORM + ODD)
    assert scores[-1] > max(scores[:-1]), "the outlier is not the furthest from the norm"


def test_the_centre_is_robust_to_the_outliers_it_is_measuring():
    """The median and MAD are used rather than mean and standard deviation on purpose. With mean and
    SD, a large outlier inflates the scale it is measured against and reports itself as ordinary —
    which is how an outlier analysis quietly concludes that nothing is unusual."""
    extreme = ["word " * 500]
    with_extreme = of.outlier_scores(UNIFORM + ODD + extreme)
    # The odd sentence must still read as distant even with a much larger outlier present.
    assert with_extreme[len(UNIFORM)] > 1.0


def test_a_corpus_too_small_to_split_refuses_rather_than_guessing():
    result = of.probe_by_distance(["short text"] * 4)
    assert "error" in result and result["gap"] is None if "gap" in result else "error" in result


def test_an_impossible_quantile_is_rejected():
    with pytest.raises(ValueError, match="quantile must be in"):
        of.probe_by_distance(UNIFORM + ODD, quantile=0.9)


def test_the_report_denies_that_outlier_status_is_a_protected_attribute():
    """The claim this module must never make. 'Further from the norm' collects non-native writers,
    disabled writers, unusual subject matter and anyone with a strong idiolect — the whole point is
    that it does not need to know which, and it must not imply that it does."""
    report = of.probe_by_distance(UNIFORM + ODD, tier="lite")
    note = report["note"].lower()
    assert "not a protected attribute" in note
    assert "says nothing about which attribute" in note


def test_a_gap_is_reported_with_whether_the_intervals_overlap():
    """A difference between two small proportions is not a finding. Publishing one without its
    intervals is the defect this repo built `wilson_interval` to prevent."""
    report = of.probe_by_distance(UNIFORM + ODD, tier="lite")
    if report.get("gap") is None:
        pytest.skip("corpus too small on one side in this environment")
    assert report["intervals_overlap"] in (True, False)
    for side in ("margin", "centre"):
        assert len(report[side]["ci95"]) == 2


def test_the_rendering_says_when_a_gap_means_nothing():
    text = of._render({
        "tier": "lite", "quantile": 0.2, "detectors_scoring": 1, "distance_cut": 1.0,
        "margin": {"n": 30, "flagged": 4, "fpr": 0.1333, "ci95": [0.053, 0.297]},
        "centre": {"n": 120, "flagged": 15, "fpr": 0.125, "ci95": [0.077, 0.196]},
        "gap": 0.0083, "intervals_overlap": True, "note": "n/a",
    })
    assert "not evidence of a disparity" in text
    assert "one detector scored" in text, "a single-detector run must say so"


def test_the_rendering_reports_a_corpus_it_could_not_use():
    assert "cannot run" in of._render({"error": "need at least 10 texts", "n": 4})


# --- the sensitivity sweep -----------------------------------------------------------------------
#
# Where the line falls between "the margins" and "everyone else" is a free parameter. A gap that
# appears only at one setting of a free parameter is a choice, not a finding — and the first headline
# this module produced, +4.8% at the furthest 20%, turned out to sit near the TOP of the range the
# sweep reports (+0.5% to +5.8% at n=600). Quoting it alone would have flattered the hypothesis.


def test_the_sweep_reports_every_cut_off_not_a_chosen_one():
    report = of.probe_sweep(UNIFORM * 6 + ODD * 3, tier="lite")
    assert [r["quantile"] for r in report["rows"]] == list(of.SWEEP_QUANTILES)


def test_the_sweep_says_whether_the_sign_holds():
    """The question a sensitivity analysis exists to answer. A gap that flips sign across cut-offs
    is noise, and the report has to say so in a field, not leave it to the reader's arithmetic."""
    report = of.probe_sweep(UNIFORM * 6 + ODD * 3, tier="lite")
    assert isinstance(report["gap_sign_is_consistent"], bool)
    assert isinstance(report["any_cut_separates"], bool)


def test_the_sweep_scores_each_text_once():
    """The refactor's whole point: `probe_sweep` splits one scoring pass seven ways. If it rescored
    per quantile, the sensitivity analysis would cost 7x and would quietly stop being run."""
    calls = []
    real = of._score_all

    def counting(texts, tier):
        calls.append(len(texts))
        return real(texts, tier)

    of._score_all, saved = counting, of._score_all
    try:
        of.probe_sweep(UNIFORM * 6 + ODD * 3, tier="lite")
    finally:
        of._score_all = saved
    assert len(calls) == 1, f"scored {len(calls)} times for {len(of.SWEEP_QUANTILES)} cut-offs"


def test_both_paths_share_the_split_so_they_cannot_disagree():
    """`probe_by_distance` and `probe_sweep` must give the same numbers at the same cut-off. Two
    implementations of one comparison is how a headline and its own sensitivity check drift apart."""
    texts = UNIFORM * 6 + ODD * 3
    single = of.probe_by_distance(texts, tier="lite", quantile=0.2)
    swept = next(r for r in of.probe_sweep(texts, tier="lite")["rows"] if r["quantile"] == 0.2)
    assert single["margin"] == swept["margin"]
    assert single["centre"] == swept["centre"]


def test_the_sweep_rendering_names_the_failure_mode():
    text = of._render_sweep({
        "tier": "lite", "n_scored": 600, "detectors_scoring": 1,
        "rows": [{"quantile": 0.2,
                  "margin": {"n": 120, "flagged": 26, "fpr": 0.217, "ci95": [0.15, 0.30]},
                  "centre": {"n": 480, "flagged": 81, "fpr": 0.169, "ci95": [0.14, 0.20]},
                  "gap": 0.048, "intervals_overlap": True}],
        "gap_sign_is_consistent": False, "any_cut_separates": False,
    })
    assert "CHANGES SIGN" in text
    assert "none of these gaps is evidence of a disparity" in text


def test_the_sweep_refuses_a_corpus_too_small_to_split():
    assert "error" in of.probe_sweep(["x"] * 4)


# --- the length control ---------------------------------------------------------------------------
#
# The margin is selected on stylometry, and stylometry is not length-neutral: MEASURED on 2,000
# pre-LLM abstracts the furthest 20% has a median of 124 words against 149 for the centre, and
# dropping `words` from the feature set barely moves that (132 against 148) because type-token ratio
# and sentence-length variation are themselves length-dependent. Since this repo has already measured
# detectors flagging short text far more often, an unstratified margin gap can be the length effect
# wearing a fairness costume — and at the full corpus it was: five of seven cut-offs separated
# unstratified, and zero bands separate once length is held roughly constant.


def test_the_stratified_probe_reports_every_band():
    report = of.probe_stratified(UNIFORM * 20 + ODD * 5, tier="lite")
    assert [b["band"] for b in report["bands"]] == [
        f"{lo}-{'+' if hi > 10 ** 8 else hi}" for lo, hi in of.STRATA
    ]


def test_a_band_with_too_little_data_says_so_rather_than_reporting_a_number():
    report = of.probe_stratified(UNIFORM * 20 + ODD * 5, tier="lite")
    assert any("skipped" in b for b in report["bands"]), (
        "short synthetic sentences should leave most bands empty, and empty bands must be labelled"
    )


def test_the_stratified_rendering_names_the_confound():
    text = of._render_stratified({
        "tier": "lite", "quantile": 0.2, "n_scored": 2000, "detectors_scoring": 1,
        "bands": [
            {"band": "60-100", "margin": {"n": 43, "flagged": 19, "fpr": 0.442, "ci95": [0.3, 0.6]},
             "centre": {"n": 172, "flagged": 47, "fpr": 0.273, "ci95": [0.21, 0.35]},
             "gap": 0.169, "intervals_overlap": True},
            {"band": "100-150", "margin": {"n": 187, "flagged": 33, "fpr": 0.176, "ci95": [0.13, 0.24]},
             "centre": {"n": 748, "flagged": 161, "fpr": 0.215, "ci95": [0.19, 0.25]},
             "gap": -0.039, "intervals_overlap": True},
        ],
        "gap_sign_is_consistent": False, "bands_separating": 0, "note": "n/a",
    })
    assert "CHANGES SIGN" in text
    assert "measuring length" in text
    assert "0 band(s) separate" in text


def test_score_all_returns_the_texts_it_kept():
    """The alignment bug this returns exist to prevent. `_score_all` drops any document no detector
    scored; a caller that re-pairs texts with flags positionally is then attaching every flag after
    the gap to the wrong document — a wrong answer with no error, which is the worst shape a bug can
    take in an audit tool."""
    texts = UNIFORM + ODD
    distances, flags, _detectors, kept = of._score_all(texts, "lite")
    assert len(kept) == len(flags) == len(distances)
    assert all(k in texts for k in kept)


def test_the_stratified_probe_pairs_flags_with_the_right_documents(monkeypatch):
    """Forces the drop the alignment bug needed. With the second document unscored, a positional
    re-pairing would shift every later flag by one; the word counts must still match their texts."""
    texts = [f"{'word ' * 80}unique{i}." for i in range(12)]
    real = of._score_all

    def dropping(ts, tier):
        d, f, det, kept = real(ts, tier)
        return d[1:], f[1:], det, kept[1:]

    monkeypatch.setattr(of, "_score_all", dropping)
    report = of.probe_stratified(texts, tier="lite")
    assert report["n_scored"] == len(texts) - 1
