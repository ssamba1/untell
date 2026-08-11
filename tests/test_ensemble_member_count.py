""""the ensemble is now selecting over N of M members" was arithmetic on the wrong set.

`_MEMBER_FAILED` is module-level: it accumulates every member name that has failed anywhere in the
process. The warning subtracted its total length from *this* ensemble's member count, so one
ensemble was charged for another's failures. MEASURED with three ensembles built in one process,
one member failing in each:

    A (3 members)   "2 of 3"     correct
    B (2 members)   "0 of 2"     one live member, reported as none
    C (1 member)    "-2 of 1"    a negative count of rewriters

"0 of 2" says the ensemble cannot function, and it had a working member. The warning exists because
a shrinking pool makes this class look like it is simply not helping — an overstated shrink is that
same error, louder.
"""

from __future__ import annotations

import logging
import re

import pytest

from untell.rewriter import ensemble as E
from untell.scripts.score import score_text

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus."
)
COUNT = re.compile(r"selecting over (-?\d+) of (\d+) members")


class _Boom:
    def rewrite(self, text, score_result, threshold):
        raise RuntimeError("member down")


class _Fine:
    def rewrite(self, text, score_result, threshold):
        return text.replace("Moreover, ", "Also ")


@pytest.fixture
def clean_failure_set(monkeypatch: pytest.MonkeyPatch):
    """The set is global and never resets, so a leftover from another test would be indistinguishable
    from the bug under test."""
    monkeypatch.setattr(E, "_MEMBER_FAILED", set())


def _counts(caplog: pytest.LogCaptureFixture) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in COUNT.findall(caplog.text)]


def test_each_ensemble_counts_only_its_own_members(
    clean_failure_set, caplog: pytest.LogCaptureFixture
) -> None:
    scored = score_text(TEXT, tier="lite")
    shapes = [
        ([("boom", _Boom()), ("fine1", _Fine()), ("fine2", _Fine())], (2, 3)),
        ([("other", _Boom()), ("fine3", _Fine())], (1, 2)),
        ([("third", _Boom())], (0, 1)),
    ]
    with caplog.at_level(logging.WARNING, logger=E.logger.name):
        for members, _ in shapes:
            rewriter = E.EnsembleRewriter()
            rewriter._members = members
            rewriter.rewrite(TEXT, scored, 0.3)

    assert _counts(caplog) == [expected for _, expected in shapes], caplog.text


def test_the_count_is_never_negative(clean_failure_set, caplog: pytest.LogCaptureFixture) -> None:
    """The specific absurdity the old arithmetic produced: -2 of 1."""
    scored = score_text(TEXT, tier="lite")
    with caplog.at_level(logging.WARNING, logger=E.logger.name):
        for name in ("a", "b", "c"):
            rewriter = E.EnsembleRewriter()
            rewriter._members = [(name, _Boom())]
            rewriter.rewrite(TEXT, scored, 0.3)

    counts = _counts(caplog)
    assert counts, "no member-failure warning was emitted; the fixture no longer fails"
    assert all(0 <= live <= total for live, total in counts), counts


def test_a_second_failure_in_one_ensemble_lowers_the_count(
    clean_failure_set, caplog: pytest.LogCaptureFixture
) -> None:
    """Guards the guard: counting only this instance must not become counting nothing. Two of the
    same ensemble's members failing has to show up as a real shrink."""
    scored = score_text(TEXT, tier="lite")
    rewriter = E.EnsembleRewriter()
    rewriter._members = [("x", _Boom()), ("y", _Boom()), ("z", _Fine())]
    with caplog.at_level(logging.WARNING, logger=E.logger.name):
        rewriter.rewrite(TEXT, scored, 0.3)

    assert _counts(caplog) == [(2, 3), (1, 3)], caplog.text


def test_the_working_member_still_produces_a_rewrite(
    clean_failure_set, caplog: pytest.LogCaptureFixture
) -> None:
    """The count is a claim about whether the ensemble still works. Check that it does — a message
    saying "1 of 2" over a rewriter that returns the input unchanged would be true and useless."""
    scored = score_text(TEXT, tier="lite")
    rewriter = E.EnsembleRewriter()
    rewriter._members = [("dead", _Boom()), ("alive", _Fine())]
    with caplog.at_level(logging.WARNING, logger=E.logger.name):
        out = rewriter.rewrite(TEXT, scored, 0.3)

    assert _counts(caplog) == [(1, 2)]
    assert out in (TEXT, _Fine().rewrite(TEXT, scored, 0.3)), out
