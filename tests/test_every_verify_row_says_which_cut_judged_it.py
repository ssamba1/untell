"""One report, two bars, and only the summary row said which one answered.

FOUND by extending Result 173's question — are the loop threshold and the verdict threshold used
consistently? — to the one surface that check did not cover. `score_text`, `untell_text`, `pre` and
`post` all agreed. `verify` is the command that exits non-zero, and it is the one that disagreed with
itself.

The history is in the file. An earlier fix moved `verify`'s LOCAL rows from the loop threshold onto
the published `verdict_threshold`, recording why:

    raw max >= 0.30          21/40  (52%)
    score_text "flagged"      7/40  (18%)   <- calibrated
    verify "not passing"     21/40  (52%)   <- this surface, uncalibrated

Two things survived that fix.

**Commercial and browser rows still judge at the loop threshold**, so a report containing both kinds
applies 0.45 to some rows and 0.30 to others. That is not a defect to fix by unifying them:
`verdict_threshold` is swept for the local stdlib ensemble and published by `score_text` for it, and
a commercial detector returns its own probability on its own scale. Borrowing the local calibration
would be a guess wearing a measurement's clothes.

**So the fix is that every row states the cut that judged it** — which is exactly the reason the
`local:max` row already carried the field, in a comment that says "a pass at 0.38 is not read as a
pass at 0.30". The per-detector local rows moved onto `verdict_cut` without gaining that field, so
the only row in the report explaining its own bar was the summary.

MEASURED after, over 6 in-band HC3 documents, 12 rows: 0 scored rows with no stated cut, 0 rows whose
`passes` disagrees with its own stated cut, and an explicit `--threshold` still reported verbatim.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import DEFAULT_THRESHOLD
from untell.scripts.verify import verify

TEXT = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead. "
    "The grit gives tyres something to bite on once the ice has gone soft near the kerb."
)


class _StubDetector:
    """A commercial-style checker: its own scale, no local calibration behind it."""

    name = "stub_commercial"
    tier = "full"  # part of the detector protocol; verify reads it when reporting the row

    def __init__(self, score: float) -> None:
        self._score = score

    def available(self) -> bool:
        return True

    def score(self, _text: str) -> float:
        return self._score


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def with_stub(monkeypatch):
    """Reach the row that has no local calibration. Without this the assertions below run only over
    `local:` rows, which is the half that was already fixed — and the first pass of this question
    measured exactly that and saw no disagreement, because commercial and browser checkers are
    unavailable in this configuration."""
    import untell.detectors.commercial as commercial

    monkeypatch.setattr(commercial, "commercial_detectors", lambda: [_StubDetector(0.38)])


def _rows(result: dict) -> dict[str, dict]:
    return result.get("results") or {}


def test_every_scored_row_states_the_cut_that_judged_it(with_stub) -> None:
    result = verify(TEXT, tier="lite", threshold=DEFAULT_THRESHOLD)
    silent = [k for k, v in _rows(result).items()
              if v.get("ai") is not None and v.get("verdict_threshold") is None]
    assert not silent, silent


def test_the_stub_row_is_actually_present(with_stub) -> None:
    """The denominator. Without a commercial row the test above covers only the rows that already
    carried the field, and would pass on a report that never exercises the uncalibrated path."""
    assert "stub_commercial" in _rows(verify(TEXT, tier="lite", threshold=DEFAULT_THRESHOLD))


def test_passes_agrees_with_the_cut_the_row_names(with_stub) -> None:
    """The property that makes the field worth having: a reader can recompute the verdict."""
    for key, row in _rows(verify(TEXT, tier="lite", threshold=DEFAULT_THRESHOLD)).items():
        if row.get("ai") is None:
            continue
        assert row["passes"] == (row["ai"] < row["verdict_threshold"]), (key, row)


def test_the_two_kinds_of_row_keep_their_own_bars(with_stub) -> None:
    """The local ensemble is judged at its swept cut; a commercial score is judged at the caller's.
    Collapsing them would apply a calibration derived from one scorer to a different one."""
    rows = _rows(verify(TEXT, tier="lite", threshold=DEFAULT_THRESHOLD))
    local = [v["verdict_threshold"] for k, v in rows.items()
             if k.startswith("local:") and v.get("ai") is not None]
    assert local and all(c > DEFAULT_THRESHOLD for c in local), local
    assert rows["stub_commercial"]["verdict_threshold"] == DEFAULT_THRESHOLD


def test_an_explicit_threshold_is_reported_verbatim(with_stub) -> None:
    """An explicit `--threshold` is a request, and substituting a different number would be its own
    dishonesty — including in the field that claims to say which cut answered."""
    rows = _rows(verify(TEXT, tier="lite", threshold=0.25))
    cuts = {v["verdict_threshold"] for v in rows.values() if v.get("ai") is not None}
    assert cuts == {0.25}, cuts


def test_a_failed_row_still_reports_no_pass(with_stub, monkeypatch) -> None:
    """Guards the guard on the error path: a row that could not score must not acquire a cut it
    never applied, nor a pass it never earned."""
    import untell.detectors.commercial as commercial

    class _Broken(_StubDetector):
        def score(self, _text: str) -> float:
            raise RuntimeError("no signal")

    monkeypatch.setattr(commercial, "commercial_detectors", lambda: [_Broken(0.38)])
    row = _rows(verify(TEXT, tier="lite", threshold=DEFAULT_THRESHOLD))["stub_commercial"]
    assert row["passes"] is False
    assert row["ai"] is None
