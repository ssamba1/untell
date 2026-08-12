"""Two opposite verdicts can render as the same number. The Verdict row is what tells them apart.

`print_humanize_result` shows P(AI) to two decimals, so 0.29996 and 0.30000 both appear as
**0.30** — one not flagged, one flagged, against a cut of 0.30. Everything a terminal user reads
about those two runs is identical except one word:

    just under 0.30   Verdict   flagged -> borderline
    exactly 0.30      Verdict   flagged -> flagged

That word is the whole disambiguation, and nothing tested it — "borderline" appeared nowhere in
tests/. The failure mode is quiet: drop the band and every borderline result silently reads
"clear", which is the reassuring direction.

The row reads `verdict_threshold` rather than `threshold`, deliberately, because that is what
`flagged` itself compares against — the two cannot disagree. That is pinned here too, since the
lite stdlib path publishes 0.45 where the loop targets 0.30, and a row built from the loop
threshold would call flagged text clear on exactly the tier a clean install lands on.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from untell.rich_output import _VERDICT_BAND, print_humanize_result

ORIGINAL = "Original AI text here, long enough to render properly."
FINAL = "Rewritten text here, long enough to render properly."


def _score(p_ai: float, flagged: bool, cut: float = 0.30) -> dict:
    return {
        "max": p_ai,
        "mean": 0.2,
        "detectors": {"d": p_ai},
        "threshold": 0.30,
        "flagged": flagged,
        "verdict_threshold": cut,
    }


def _render(post: dict) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_humanize_result(ORIGINAL, FINAL, _score(0.9, True), post, 2, "passed")
    return buf.getvalue()


def _verdict_after(post: dict) -> str:
    """The AFTER cell of the Verdict row, not the whole row.

    The row reads `Verdict │ flagged │ borderline`, so a substring test for "flagged" matches the
    BEFORE column and passes regardless of what the run produced. That is a documented scar in
    this repository, and the first version of this file walked straight back into it — the 0.45
    case "passed" on the before-column while the after-column said borderline.
    """
    for line in _render(post).splitlines():
        if "Verdict" in line:
            cells = [c.strip() for c in line.split("│") if c.strip()]
            assert len(cells) >= 3, f"unexpected Verdict row shape: {line!r}"
            return cells[2]
    raise AssertionError("no Verdict row rendered")


def test_the_two_scores_really_do_render_alike():
    """The premise. Without it the rest guards a problem that does not exist."""
    under, at = _score(0.29996, False), _score(0.30000, True)

    # Cells, not raw lines. The rendered rows differ by whitespace alone, because "borderline" is
    # wider than "flagged" and the table pads every column to fit — so the only visual difference
    # between a flagged run and a clear one is that padding, plus the word itself.
    def _p_ai_cells(score: dict) -> list[str]:
        line = next(ln for ln in _render(score).splitlines() if "P(AI)" in ln)
        return [c.strip() for c in line.split("│") if c.strip()]

    assert _p_ai_cells(under) == _p_ai_cells(at), (
        "the two scores no longer render the same numbers; this file's premise is stale"
    )
    assert _verdict_after(under) != _verdict_after(at), (
        "identical numbers AND identical verdicts — nothing on screen separates a flagged run "
        "from a clear one"
    )


def test_just_below_the_cut_is_borderline_not_clear():
    assert _verdict_after(_score(0.29996, False)) == "borderline"


def test_at_the_cut_is_flagged():
    assert _verdict_after(_score(0.30000, True)) == "flagged"


def test_well_below_the_cut_is_clear():
    """The band must not swallow everything, or 'borderline' stops meaning anything."""
    assert _verdict_after(_score(0.30 - _VERDICT_BAND - 0.01, False)) == "clear"


@pytest.mark.parametrize("cut", [0.30, 0.45])
def test_the_row_follows_the_verdict_threshold_not_the_loop_target(cut: float):
    """0.45 is the stdlib lite cut. A row built from the loop's 0.30 would call it clear."""
    after = _verdict_after(_score(0.40, flagged=cut <= 0.40, cut=cut))
    assert (after == "flagged") is (cut <= 0.40), (
        f"at cut {cut} a score of 0.40 rendered {after!r}, which disagrees with `flagged`"
    )
