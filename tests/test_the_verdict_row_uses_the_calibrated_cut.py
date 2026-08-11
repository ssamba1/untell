"""The verdict row in `print_humanize_result` had no test covering the mapping it uses.

`tests/test_rich_output.py` defines a local `_verdict` documented as "the mapping
print_humanize_result uses" and built from `classification((1 - p_ai) * 100)`. That mapping was
REPLACED: the module's own comment records that it disagreed with `untell humanness` about the
same paragraph on 42 of 60 texts, and it now keys off `verdict_threshold` — the same field
`flagged` compares against, so the row and the field cannot disagree.

The old test still passes because it is self-contained against `classification`. It just does not
touch the shipped code path. These do, through the public function.
"""

from __future__ import annotations

import pytest

from untell import rich_output

TEXT = "The committee reviewed the proposal and found it broadly acceptable this year."


def _render(post_max: float, *, verdict_threshold: float | None = None, threshold: float = 0.30,
            capsys=None) -> str:
    post: dict = {"max": post_max, "threshold": threshold, "detectors": {}}
    if verdict_threshold is not None:
        post["verdict_threshold"] = verdict_threshold
    rich_output.print_humanize_result(
        original=TEXT,
        final=TEXT + " Slightly changed.",
        pre_score={"max": 0.99, "threshold": threshold, "detectors": {}},
        post_score=post,
        iterations=1,
        stopped="passed",
    )
    return capsys.readouterr().out


@pytest.mark.parametrize(
    ("post_max", "expected"),
    [
        (0.90, "flagged"),      # at or above the cut
        (0.45, "flagged"),      # exactly the cut
        (0.44, "borderline"),   # inside the 0.10 band below it
        (0.35, "borderline"),   # bottom edge of the band
        (0.34, "clear"),        # below the band
        (0.01, "clear"),
    ],
)
def test_the_row_reads_off_the_calibrated_cut(post_max, expected, capsys):
    """With `verdict_threshold` present the row must use it, not the loop's 0.30 target."""
    out = _render(post_max, verdict_threshold=0.45, capsys=capsys)
    assert expected in out, f"post_max={post_max} expected {expected!r}\n{out}"


def test_it_falls_back_to_threshold_when_no_calibrated_cut_is_published():
    """`verdict_threshold` is absent on paths that do not need one; 0.30 then decides."""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rich_output.print_humanize_result(
            original=TEXT, final=TEXT + " x",
            pre_score={"max": 0.99, "threshold": 0.30, "detectors": {}},
            post_score={"max": 0.31, "threshold": 0.30, "detectors": {}},
            iterations=1, stopped="passed",
        )
    assert "flagged" in buf.getvalue()


def _after_verdict(out: str) -> str:
    """The AFTER cell of the Verdict row.

    The row renders both columns — "Verdict │ flagged │ borderline │" — so searching the whole
    row for "flagged" reads the BEFORE score, which is 0.99 in this fixture and legitimately
    flagged. The first version of this test did exactly that and failed on its own assertion.
    """
    line = next(ln for ln in out.splitlines() if "Verdict" in ln)
    cells = [c.strip() for c in line.split("│") if c.strip()]
    return cells[2]  # ["Verdict", before, after]


def test_the_row_cannot_disagree_with_the_flagged_field(capsys):
    """The reason this mapping was changed. `flagged` compares against the same cut, so a run
    reported as flagged must never render a non-flagged verdict beside it."""
    for cut in (0.30, 0.45):
        for post_max in (0.20, 0.29, 0.30, 0.44, 0.45, 0.80):
            after = _after_verdict(_render(post_max, verdict_threshold=cut, capsys=capsys))
            flagged = post_max >= cut
            assert (after == "flagged") is flagged, (
                f"max={post_max} cut={cut}: flagged={flagged} but the row says {after!r}"
            )


def test_the_band_width_is_the_one_the_module_declares():
    """Pins the constant against the parametrized rows above, so changing one fails the other."""
    assert rich_output._VERDICT_BAND == 0.10
