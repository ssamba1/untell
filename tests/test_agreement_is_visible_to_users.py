"""A verdict a user can see must not hide that it is the most accusatory of three readings.

`score_text` computes union / majority / unanimous, but the CLI table showed only the union verdict.
Measured on 72 human abstracts across three detectors, union flags 32 and unanimity flags 0 — so
showing the union alone hands a reader the worst of three answers and calls it the answer.

These exercise the renderer rather than inspecting its source. An earlier version of this file
asserted on the text of `rich_output.py`, which would have passed even if the row never rendered;
`rich` is an optional dependency and was simply absent, so the weaker test looked green for the wrong
reason.
"""

from __future__ import annotations

import contextlib
import io

import pytest

pytest.importorskip("rich", reason="the rich table is what is under test here")

from untell.rich_output import print_humanize_result  # noqa: E402

BASE = {"max": 0.6, "verdict_threshold": 0.45}


def _render(post_score: dict) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_humanize_result("a b c", "a b d", {"max": 0.9, "verdict_threshold": 0.45},
                              post_score, 1, "threshold")
    return buffer.getvalue()


def _agreement_row(output: str) -> str | None:
    rows = [line for line in output.splitlines() if "Agreement" in line]
    return rows[0] if rows else None


def test_a_multi_detector_run_shows_how_many_flagged_and_which_rules_fired():
    row = _agreement_row(_render({**BASE, "agreement": {
        "detectors_scoring": 3, "detectors_flagging": 2,
        "any": True, "majority": True, "unanimous": False, "degenerate": False}}))
    assert row is not None, "the spread is computed but never displayed"
    assert "2/3" in row
    assert "any" in row and "majority" in row
    assert "unanimous" not in row, "a rule that did not fire must not be listed as if it had"


def test_a_single_detector_run_is_not_rendered_as_unanimous():
    """With one detector the three rules coincide. Printing 'unanimous' would claim an agreement one
    detector cannot supply — the flattering failure this row exists to prevent."""
    row = _agreement_row(_render({**BASE, "agreement": {
        "detectors_scoring": 1, "detectors_flagging": 1,
        "any": True, "majority": True, "unanimous": True, "degenerate": True}}))
    assert row is not None
    assert "1 detector only" in row
    assert "unanimous" not in row


def test_no_row_when_nothing_scored():
    """An absent spread must not render an empty row that reads as a measurement."""
    assert _agreement_row(_render(dict(BASE))) is None


def test_the_union_verdict_is_still_shown_beside_it():
    """The Agreement row supplements the verdict; it does not replace it."""
    output = _render({**BASE, "agreement": {
        "detectors_scoring": 3, "detectors_flagging": 1,
        "any": True, "majority": False, "unanimous": False, "degenerate": False}})
    assert "Verdict" in output
    row = _agreement_row(output)
    assert "1/3" in row and "any" in row and "majority" not in row
