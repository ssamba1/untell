"""Every false-positive number in this repository answers half a question.

A detector that flags nothing has no false positives. One that flags everything catches every machine
document. Neither figure means anything alone, and the other half was unmeasurable here because HC3
and RAID both need network access this environment denies — which is why round seventy-five could
measure that correcting `_burstiness` cuts false positives from 19.44% to 12.41% and could not say
whether that was an improvement.

`eval/data/generated_abstracts.py` supplies the missing arm: text written by a language model, so the
label is provenance rather than annotation.

MEASURED at the shipped verdict threshold, matched by length against pre-LLM ACL abstracts, the
detector flags **10.7%** of machine abstracts and **30.4%** of human ones over the matched 40-100
range, with non-overlapping intervals — and flags human text more often in *every* band. On this
register it is not a weak detector; it is pointed the wrong way.

These tests pin the comparison machinery, not that result. The result lives in round seventy-six of
the ledger and in `eval/detection_power.py`, both of which state its limits. What must not break is
the machinery's ability to *report* an inversion, and its refusal to pool arms that are not matched.
"""

from __future__ import annotations

import pytest

from eval.data.generated_abstracts import ABSTRACTS
from eval.detection_power import (
    BANDS,
    compare,
    component_auroc,
    main,
    ranking_auroc,
    register_comparison,
    render,
    score_arm,
)


def _arm(rate: float, n: int, words: int, high: float = 0.9, low: float = 0.1):
    """`n` scores at one length, of which `rate` are above any threshold in (low, high)."""
    flagged = round(rate * n)
    return [(words, high)] * flagged + [(words, low)] * (n - flagged)


def test_an_inverted_detector_is_reported_as_inverted():
    """The finding's shape: the machine arm flagged less, intervals apart."""
    report = compare(_arm(0.10, 200, 70), _arm(0.60, 200, 70), threshold=0.45)
    assert report["inverted"]
    assert "INVERTED" in render(report)


def test_a_working_detector_is_not_reported_as_inverted():
    """Guards the guard. A checker that cried inversion at everything would have produced the real
    corpus's verdict by luck."""
    report = compare(_arm(0.80, 200, 70), _arm(0.05, 200, 70), threshold=0.45)
    assert not report["inverted"]
    assert "INVERTED" not in render(report)


def test_overlapping_intervals_are_not_called_an_inversion():
    """A point estimate pointing the wrong way is not a finding at small n. This is the distinction
    that kept the first run of this comparison — n=24, intervals overlapping — from being stated as
    a result."""
    report = compare(_arm(0.10, 10, 70), _arm(0.30, 12, 70), threshold=0.45)
    assert report["matched"]["machine"]["rate"] < report["matched"]["human"]["rate"]
    assert not report["inverted"], "overlapping intervals must not be reported as separation"


def test_arms_are_pooled_only_where_both_have_data():
    """The confound `eval/arms.py` exists for. If one arm is systematically shorter, pooling across
    all lengths compares length as much as authorship — and this detector's length effect is large
    enough to swamp any real signal."""
    machine = _arm(0.10, 50, 70)               # 60-100 only
    human = _arm(0.10, 50, 70) + _arm(0.90, 500, 300)  # plus a long band the machine arm lacks
    report = compare(machine, human, threshold=0.45)
    assert report["matched"]["human"]["n"] == 50, (
        "the long band has no machine counterpart and must not enter the pooled comparison")
    assert report["bands"]["100+"]["machine"] is None
    assert report["bands"]["100+"]["human"]["n"] == 500


def test_a_band_present_in_one_arm_is_reported_rather_than_dropped():
    """Silently dropping it is what makes an unmatched comparison look matched."""
    report = compare(_arm(0.1, 20, 70), _arm(0.1, 20, 300), threshold=0.45)
    assert report["bands"]["60-100"]["machine"]["n"] == 20
    assert report["bands"]["60-100"]["human"] is None
    assert report["matched"]["machine"]["n"] == 0


def test_the_bands_match_the_human_corpus_they_are_compared_against():
    assert BANDS[0][0] == 40, "the corpus is built at a 40-word floor for this comparison"
    assert all(low < high for low, high in BANDS)
    assert [b[1] for b in BANDS[:-1]] == [b[0] for b in BANDS[1:]], "bands must not have gaps"


def test_the_generated_corpus_is_usable_as_an_arm():
    """It is data, so it gets checked like data: enough of it, varied, and spanning the lengths the
    human arm has."""
    words = sorted(len(" ".join(a.split()).split()) for a in ABSTRACTS)
    assert len(ABSTRACTS) >= 50, f"only {len(ABSTRACTS)} abstracts"
    assert len(set(ABSTRACTS)) == len(ABSTRACTS), "duplicates would inflate n without adding data"
    assert words[0] >= 40 and words[-1] >= 150, words[:3] + words[-3:]
    assert sum(1 for w in words if 40 <= w < 100) >= 40, "the matched band needs the most of them"


@pytest.mark.parametrize("machine,human", [([], []), ([(70, 0.9)], []), ([], [(70, 0.9)])])
def test_an_empty_arm_does_not_divide_by_zero(machine, human):
    report = compare(machine, human, threshold=0.45)
    assert report["inverted"] is False
    assert isinstance(render(report), str)


# --- the threshold-free half, added in round seventy-seven ---------------------------------------


def test_auroc_is_a_half_for_indistinguishable_arms():
    assert ranking_auroc([0.4] * 20, [0.4] * 20) == 0.5


def test_auroc_is_one_when_every_machine_score_is_higher():
    assert ranking_auroc([0.9, 0.8], [0.2, 0.1]) == 1.0


def test_auroc_is_zero_when_the_detector_is_exactly_reversed():
    """Below 0.5 means the detector ranks human text as more machine-like. On the real matched arms
    it is 0.3538 with a bootstrap interval entirely below 0.5."""
    assert ranking_auroc([0.1, 0.2], [0.8, 0.9]) == 0.0


def test_auroc_counts_ties_as_half():
    """Coarse scores produce ties, and counting them as wins or losses would bias the summary in
    whichever direction the tie-break favoured."""
    assert ranking_auroc([0.5, 0.5], [0.5, 0.9]) == 0.25


def test_auroc_is_not_moved_by_shifting_every_score():
    """The property that makes it the right summary here, and the one a flag rate lacks.

    Round seventy-six read an improved machine-to-human flag ratio as the burstiness correction
    helping. It was not: lowering every score moves fewer documents of BOTH classes across a fixed
    bar. AUROC is invariant to that, and by AUROC the correction was 0.3538 -> 0.3402 — no gain.
    """
    machine = [0.30, 0.35, 0.40]
    human = [0.45, 0.50, 0.55]
    before = ranking_auroc(machine, human)
    after = ranking_auroc([m - 0.1 for m in machine], [h - 0.1 for h in human])
    assert before == after

    # A flag rate at a fixed threshold, by contrast, moves a lot.
    rate = lambda xs, t: sum(x >= t for x in xs) / len(xs)  # noqa: E731
    assert rate(human, 0.45) == 1.0
    assert rate([h - 0.1 for h in human], 0.45) < 1.0


def test_the_report_carries_the_auroc_alongside_the_rates():
    report = compare([(70, 0.2)] * 30, [(70, 0.8)] * 30, threshold=0.45)
    assert report["auroc"] == 0.0
    assert "AUROC" in render(report)


@pytest.mark.parametrize("machine,human", [([], [0.5]), ([0.5], []), ([], [])])
def test_auroc_on_an_empty_arm_is_none_rather_than_a_number(machine, human):
    assert ranking_auroc(machine, human) is None


def test_component_auroc_finds_the_term_that_inverts():
    """The question round seventy-eight asked: is one term dragging the score down?"""
    machine = [{"good": 0.9, "bad": 0.1} for _ in range(20)]
    human = [{"good": 0.1, "bad": 0.9} for _ in range(20)]
    scores = component_auroc(machine, human, ("good", "bad"))
    assert scores["good"] == 1.0
    assert scores["bad"] == 0.0


def test_component_auroc_reports_a_uniformly_bad_feature_set_as_such():
    """The answer it actually gave. Both live components sit below 0.5, so there is no term to drop
    — which is why 'remove burstiness' was refuted rather than confirmed."""
    machine = [{"a": 0.2, "b": 0.3} for _ in range(20)]
    human = [{"a": 0.7, "b": 0.8} for _ in range(20)]
    scores = component_auroc(machine, human, ("a", "b"))
    assert all(v < 0.5 for v in scores.values())


def test_a_constant_component_scores_exactly_a_half():
    """`rep` does, in every band, and that is correct: it is a degenerate-collapse guard documented
    as returning 0.0 on real text. A constant carries no ranking information and 0.5 says so."""
    machine = [{"c": 0.0} for _ in range(30)]
    human = [{"c": 0.0} for _ in range(30)]
    assert component_auroc(machine, human, ("c",))["c"] == 0.5


def test_the_repetition_guard_fires_on_degenerate_text_and_not_on_prose():
    """Pins what the constant means, after a first probe got it wrong.

    That probe used inputs under the function's own 40-word minimum, so it measured the length
    guard and concluded the term never fires. It does.
    """
    from untell.detectors.perplexity_burstiness import _repetition_signal

    assert _repetition_signal("the " * 100) == 1.0
    assert _repetition_signal("alpha beta " * 60) == 1.0
    assert _repetition_signal("We show that the model works. " * 25) == 1.0
    prose = ("The system processes each record and stores the result in a database that other "
             "components query when they need it, which happens often enough to matter. ") * 3
    assert _repetition_signal(prose) == 0.0
    # Under the minimum, it declines rather than guessing — which is what the first probe hit.
    assert _repetition_signal("the " * 12) == 0.0


def test_a_missing_component_is_skipped_rather_than_defaulted():
    """Defaulting an absent key to zero would silently compare documents that have the feature
    against documents that do not."""
    machine = [{"a": 0.9}, {}]
    human = [{"a": 0.1}, {}]
    assert component_auroc(machine, human, ("a",))["a"] == 1.0
    assert component_auroc(machine, human, ("missing",))["missing"] is None


# --- one command reproduces the arc, added in round eighty-four -----------------------------------


def test_score_arm_returns_a_length_and_a_score_for_each_text():
    arm = score_arm(["The system processes each record and stores the result carefully. " * 3])
    assert len(arm) == 1
    words, score = arm[0]
    assert words > 20 and 0.0 <= score <= 1.0


def test_score_arm_skips_text_the_detector_declines_to_score():
    """A detector returning no signal is not a zero. Folding one in would add a fabricated
    most-human-possible document to whichever arm was short enough to trigger it."""
    assert score_arm(["", "   ", "hi"]) == []


def test_the_register_comparison_returns_both_matched_bands():
    bands = register_comparison()
    assert set(bands) == {"tells_60_100", "tells_30_60"}
    assert set(bands["tells_60_100"]) == {"academic", "assistant"}
    assert set(bands["tells_30_60"]) == {"academic", "promotional"}
    for band in bands.values():
        for arm in band.values():
            assert arm, "a band with an empty arm cannot be compared"


def test_the_register_bands_reproduce_the_published_separation():
    """The round eighty-two figures, through the shipped path rather than a script."""
    bands = register_comparison()
    academic = bands["tells_60_100"]["academic"]
    assistant = bands["tells_60_100"]["assistant"]
    assert ranking_auroc(assistant, academic) == 1.0
    assert sum(bands["tells_30_60"]["academic"]) == 0.0


def test_the_cli_refuses_rather_than_guessing_when_given_no_human_arm(capsys):
    """`--human` and `--run` are the two ways to supply one. Without either, inventing a default
    would produce a comparison nobody chose."""
    code = main([])
    assert code == 2
    assert "--run" in capsys.readouterr().err


def test_the_cli_names_the_missing_corpus_rather_than_reporting_an_empty_comparison(capsys, tmp_path):
    """An empty human arm would render as a table of dashes and an AUROC of None, which reads as a
    result. It is a missing download."""
    code = main(["--run", "--cache", str(tmp_path)])
    assert code == 1
    assert "pre_llm_fpr --download" in capsys.readouterr().err
