"""`flagged` is the union rule, and the union rule is the one that maximises false accusations.

The research pass behind ROADMAP section 7 found that the aggregation rule moves the false-positive
rate further than the choice of detector does: scoring abstracts with three tools, the union rule
measured 44.44% false accusations against 4.17% for majority, and a four-detector study went from
1.3% individually to near zero by requiring agreement.

`agreement()` publishes all three so a reader can disagree with `flagged`. These tests pin the
arithmetic, and — more importantly — pin the two cases where a wrong answer would be *reassuring*:
one detector masquerading as consensus, and a dead detector counted as a vote.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import agreement


def test_the_three_rules_separate_when_detectors_disagree():
    spread = agreement({"a": 0.9, "b": 0.1, "c": 0.8}, 0.45)
    assert spread["any"] is True
    assert spread["majority"] is True
    assert spread["unanimous"] is False
    assert (spread["detectors_flagging"], spread["detectors_scoring"]) == (2, 3)


def test_one_flag_out_of_three_is_union_only():
    """The shape of a false accusation: a single outlier drives the reported verdict."""
    spread = agreement({"a": 0.9, "b": 0.1, "c": 0.2}, 0.45)
    assert spread["any"] is True
    assert spread["majority"] is False
    assert spread["unanimous"] is False


def test_a_single_detector_is_flagged_as_degenerate():
    """All three rules coincide at n=1. Reporting `unanimous` there would claim an agreement that
    one detector cannot supply — the most flattering possible way to be wrong."""
    spread = agreement({"only": 0.9}, 0.45)
    assert spread["unanimous"] is True
    assert spread["degenerate"] is True, "n=1 must not read as consensus"


def test_failed_detectors_are_not_counted_as_votes():
    """`__error` sidecars are strings. Counting one as a vote would inflate the denominator and make
    `unanimous` unreachable, or — worse — shrink it and make consensus look easy."""
    spread = agreement({"a": 0.9, "b": 0.8, "b__error": "boom"}, 0.45)
    assert spread["detectors_scoring"] == 2
    assert spread["unanimous"] is True


def test_nothing_scored_returns_none_rather_than_a_clean_verdict():
    assert agreement({}, 0.45) is None
    assert agreement({"a__error": "boom"}, 0.45) is None


@pytest.mark.parametrize("scores,majority", [
    ({"a": 0.9, "b": 0.9, "c": 0.1, "d": 0.1}, False),  # exactly half is NOT a majority
    ({"a": 0.9, "b": 0.9, "c": 0.9, "d": 0.1}, True),
])
def test_majority_is_strictly_more_than_half(scores, majority):
    """An even split must not read as a majority: 2-of-4 deciding an accusation is the bug."""
    assert agreement(scores, 0.45)["majority"] is majority


def test_the_threshold_boundary_is_inclusive_like_flagged():
    """`flagged` uses `>=`. If agreement used `>`, the two could disagree on a boundary score and
    the report would contradict itself."""
    assert agreement({"a": 0.45}, 0.45)["any"] is True


def test_score_text_publishes_the_spread():
    from untell.scripts.score import score_text

    result = score_text("The quick brown fox jumps over the lazy dog. " * 12, tier="lite")
    if result.get("scored") is False:
        pytest.skip("no detector scored in this environment")
    assert "agreement" in result
    assert result["agreement"]["any"] is result["flagged"]
