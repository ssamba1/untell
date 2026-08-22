"""A run where nothing scored rendered a full table of beaten detectors.

`score_text` returns `max: 0.0` and 0.0 detector entries as PLACEHOLDERS when no detector produced
a number, and sets `scored: False` to say so. A placeholder is numeric, so it passes the
`isinstance(..., (int, float))` pairing test in `_per_detector` and is treated as a real score of
zero -- which is below any threshold, so every detector reads as beaten on every sample.

MEASURED, five rows with `scored: False`:

    bypass_rate        0.0      guarded, correct
    beat_rate          1.0      "beaten on 100% of samples"
    hardest_detector   "d1"     a headline drawn from nothing

`_bypass_rate` records this exact trap in its own docstring and filters on
`scored is not False`; `_per_detector`'s docstring records the paired-filtering version of it.
This was the third place in the same file and the only one where the guard was missing -- and the
one whose number is quoted PER DETECTOR, which is the form most likely to be read as a result
about a specific detector rather than as an aggregate.

The asymmetry is what makes it worth a test rather than a comment: erroring out reads as
bypassing, and it reads that way in the most flattering possible direction.
"""

from __future__ import annotations

import pytest

from eval.report import _bypass_rate, _per_detector, summarize


class _Row:
    """The parts of a benchmark result row that `report` actually reads."""

    def __init__(self, pre: float, post: float, scored: bool, sim: float = 0.9, iters: int = 1):
        self.pre = {"max": pre, "detectors": {"d1": pre, "d2": pre}}
        self.post = {"max": post, "detectors": {"d1": post, "d2": post}, "scored": scored}
        self.similarity = sim
        self.iterations = iters


UNSCORED = [_Row(0.0, 0.0, scored=False) for _ in range(5)]
SCORED = [_Row(0.9, 0.2, scored=True) for _ in range(3)]


def test_no_detector_is_reported_as_beaten_when_nothing_scored():
    assert _per_detector(UNSCORED, 0.3) == {}, (
        "placeholder zeros were paired as real scores and read as a clean sweep"
    )


def test_no_hardest_detector_is_named_from_a_run_that_did_not_score():
    summary = summarize({"rewrite": UNSCORED}, 0.3)["strategies"]["rewrite"]

    assert summary["n_scored"] == 0, "premise: this fixture must score nothing"
    assert summary["per_detector"] == {}
    assert summary["hardest_detector"] is None, (
        f"named a hardest detector from no data: {summary['hardest_detector']!r}"
    )


def test_the_aggregate_guard_and_the_per_detector_guard_now_agree():
    """`_bypass_rate` was already right. The point is that the two no longer disagree."""
    assert _bypass_rate(UNSCORED, 0.3) == 0.0
    assert _per_detector(UNSCORED, 0.3) == {}


def test_a_real_run_is_completely_unaffected():
    """The guard must cost nothing on the path that matters."""
    per = _per_detector(SCORED, 0.3)

    assert set(per) == {"d1", "d2"}
    assert per["d1"]["pre"] == pytest.approx(0.9)
    assert per["d1"]["post"] == pytest.approx(0.2)
    assert per["d1"]["beat_rate"] == 1.0
    assert per["d1"]["n"] == 3.0


def test_a_mixed_run_counts_only_the_rows_that_scored():
    """The denominator has to be the scored rows, not all of them.

    `n` is carried specifically so the renderer can show the denominator rather than implying it
    is the sample count, which makes it the field most worth checking here.
    """
    per = _per_detector(SCORED + UNSCORED, 0.3)

    assert per["d1"]["n"] == 3.0, f"unscored rows leaked into the denominator: {per['d1']['n']}"
    assert per["d1"]["pre"] == pytest.approx(0.9), "a placeholder zero dragged the pre-mean down"
    assert per["d1"]["beat_rate"] == 1.0
