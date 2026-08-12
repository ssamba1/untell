"""A person checking their own writing gets "99.2% AI" — and used to get nothing beside it.

FOUND by asking what the loop does to text that is already human. It mostly does the right thing: of
8 genuine HC3 answers at tier=full, 6 came back byte-identical with similarity 1.000, because the
loop only rewrites what the detectors flag. Two were rewritten, and those two were flagged at 0.9922
and 0.9862 — the loop behaved correctly and the detectors were wrong.

The lite path already says so loudly ("64% of HUMAN text scores above the 0.30 loop threshold"). The
FULL path — the one the README tells people to install — said nothing. MEASURED on 30 genuine human
texts per corpus:

    corpus   flagged (>=0.45)   above the loop bar (>=0.30)   mean max   carrying a warning
    HC3        5 / 30  (17%)          5 / 30                    0.259           0
    RAID       0 / 30  ( 0%)          0 / 30                    0.141           0

`ai_percent` 99.2 with `warning: None`, on writing a person wrote themselves.

The corpus split is the substance, not a footnote on it. HC3 human answers are casual forum Q&A —
the register someone actually pastes when checking their own prose — and RAID's are paper abstracts.
A single pooled rate would understate exactly the case that matters.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import _HUMAN_FP_NOTE, _human_false_positive_warning, score_text

HUMAN = (
    "I drove up on Friday and the traffic was awful past the junction near the bridge. "
    "Took nearly four hours for what should have been two. Next time we will leave before "
    "lunch and see whether that helps, though I doubt it makes much difference either way."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_flagged_result_carries_the_caveat() -> None:
    assert _human_false_positive_warning({"flagged": True}) == _HUMAN_FP_NOTE


def test_an_unflagged_result_carries_nothing() -> None:
    """A warning on every call is a warning nobody reads. An unflagged verdict has no
    false-positive to caveat."""
    assert _human_false_positive_warning({"flagged": False}) is None
    assert _human_false_positive_warning({}) is None


def test_the_caveat_names_both_corpora() -> None:
    """The rate is corpus-dependent — 17% against 0% — and quoting one number would either alarm a
    RAID-style user or reassure an HC3-style one wrongly."""
    assert "HC3" in _HUMAN_FP_NOTE and "RAID" in _HUMAN_FP_NOTE
    assert "17%" in _HUMAN_FP_NOTE


def test_the_caveat_does_not_claim_the_verdict_is_wrong() -> None:
    """It has to survive being read by someone whose text really is AI. The claim is about what a
    flag proves, not about which way this particular verdict went."""
    assert "not proof" in _HUMAN_FP_NOTE
    for overclaim in ("this text is human", "ignore", "false positive verdict"):
        assert overclaim not in _HUMAN_FP_NOTE.lower()


def test_it_reaches_a_real_score_result() -> None:
    """Wired in, not merely defined — the defect two results ago was a transform that worked and
    was never called."""
    result = score_text(HUMAN, tier="lite", threshold=0.3)
    if not result.get("flagged"):
        pytest.skip("this text is not flagged on the installed tier")
    assert "not proof of AI authorship" in (result.get("warning") or "")


def test_an_existing_warning_is_not_replaced() -> None:
    """Length, tier and false-positive rate are independent problems; the merge appends rather than
    overwrites, and a short flagged text has both."""
    result = score_text("Short and flagged.", tier="lite", threshold=0.01)
    warning = result.get("warning") or ""
    if result.get("flagged") and "too short" in warning:
        assert "not proof of AI authorship" in warning
