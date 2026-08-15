"""The humanness bar renderer must survive scores it was not designed for.

`print_humanness` takes a bare float and paints a 30-cell bar from it. Fuzz-found:
`int(nan / 100 * 30)` raises ValueError, `int(inf / 100 * 30)` raises OverflowError,
and an out-of-range score like 999999 paints a bar of ~300,000 block characters —
a renderer that turns one number into a megabyte of terminal output is a hang/OOM
vector, not a display. The bar must stay exactly ``bar_len`` wide whatever the input.
"""

from __future__ import annotations

import math

from untell import rich_output


def test_nonfinite_score_does_not_crash(capsys):
    """NaN/inf must render (as an undetermined mid-bar), not raise into the caller."""
    for score in (float("nan"), float("inf"), float("-inf")):
        rich_output.print_humanness(score, "mixed")
        out = capsys.readouterr().out
        assert out, f"expected some output for {score}"


def test_out_of_range_score_keeps_the_bar_bounded(capsys):
    """score=999999 previously painted ~300,000 block chars; the bar must stay 30 cells."""
    rich_output.print_humanness(999999.0, "mixed")
    out = capsys.readouterr().out
    bar_line = next(line for line in out.splitlines() if "█" in line or "░" in line)
    assert len(bar_line) == 30, f"bar is {len(bar_line)} cells, expected exactly 30"


def test_negative_score_keeps_the_bar_bounded(capsys):
    """score=-5 painted 31 cells (empty fill plus a 31-cell hollow bar); must stay 30."""
    rich_output.print_humanness(-5.0, "mixed")
    out = capsys.readouterr().out
    bar_line = next(line for line in out.splitlines() if "█" in line or "░" in line)
    assert len(bar_line) == 30
