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
from eval.detection_power import BANDS, compare, render


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
