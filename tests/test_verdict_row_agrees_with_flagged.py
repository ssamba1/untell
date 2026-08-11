"""The humanize report's Verdict row labelled P(AI) with another metric's calibration.

It called `classification((1 - p_ai) * 100)`. That function's boundaries are fitted to `humanness()`
scores specifically — its own docstring says "lowest HUMAN score 75.6, highest AI score 72.0 ... a
boundary at 75 misclassifies 0 of 80". `(1 - P(AI)) * 100` is a different quantity on a different
scale. MEASURED on 60 HC3 and RAID texts, comparing `classification(humanness(t))` against
`classification((1 - max) * 100)`:

    labels agree on 18 of 60 — 30%

So `untell humanize` and `untell humanness` disagreed about the same paragraph seven times in ten,
through the same labelling function.

The row sits directly under `P(AI) max` and glosses it, so it is now labelled against
`verdict_threshold` — the cut that decides `flagged`, and the only calibrated decision this repo
makes about that number. The two can no longer disagree.

The earlier fix recorded in that code was real: passing P(AI) in raw put every value under the
bottom band, so the row printed "AI" -> "AI" for every input including a run that took 0.86 to 0.02.
Rescaling into the wrong calibration replaced a constant with a mislabel.
"""

from __future__ import annotations

import pytest

import untell.rich_output as rich_output

pytest.importorskip("rich", reason="the report degrades to plain text without rich")


@pytest.fixture(autouse=True)
def _rich(monkeypatch: pytest.MonkeyPatch):
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    monkeypatch.setattr(rich_output, "_RICH", True)
    for name, value in (("_Panel", Panel), ("_Table", Table), ("_Text", Text)):
        monkeypatch.setattr(rich_output, name, value, raising=False)
    monkeypatch.setattr(rich_output, "_CONSOLE", Console(width=100), raising=False)


def _report(before: float, after: float, cut: float = 0.45) -> str:
    """Render one run and return the plain text."""
    from io import StringIO

    from rich.console import Console

    buffer = StringIO()
    console = Console(file=buffer, width=100, force_terminal=False, no_color=True)
    original_console = rich_output._CONSOLE
    rich_output._CONSOLE = console
    try:
        rich_output.print_humanize_result(
            "Moreover the framework leverages robust methodologies to deliver outcomes at scale.",
            "The setup uses solid methods to deliver outcomes at scale across the corpus today.",
            {"max": before, "tier": "lite", "verdict_threshold": cut},
            {"max": after, "tier": "lite", "verdict_threshold": cut},
            iterations=1,
            stopped="passed",
        )
    finally:
        rich_output._CONSOLE = original_console
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("p_ai", "expected"),
    [
        (0.90, "flagged"),
        (0.46, "flagged"),
        (0.45, "flagged"),   # at the cut, `flagged` is `max >= threshold`
        (0.44, "borderline"),
        (0.36, "borderline"),
        (0.34, "clear"),
        (0.02, "clear"),
    ],
    ids=lambda x: str(x),
)
def test_the_label_follows_the_verdict_threshold(p_ai: float, expected: str) -> None:
    out = _report(p_ai, p_ai, cut=0.45)
    assert expected in out, out


def test_the_label_moves_with_the_threshold() -> None:
    """The cut is read from the score result, not hard-coded — a run at a different tier or
    threshold must relabel accordingly, or the row goes back to describing something else."""
    assert "flagged" in _report(0.40, 0.40, cut=0.30)
    assert "clear" in _report(0.10, 0.10, cut=0.30)


def test_the_row_is_not_constant() -> None:
    """The defect the earlier fix was for: the row printed the same word whatever the numbers.
    A regression to any constant label would pass every equality test above that happens to match
    it, so this asserts the row DISCRIMINATES."""
    labels = {
        _report(p, p).split("Verdict")[1].split("\n")[0].strip()
        for p in (0.02, 0.40, 0.90)
    }
    assert len(labels) >= 2, labels


def test_before_and_after_are_labelled_independently() -> None:
    """A run that moves a text across the cut has to show it — that is the whole point of the row."""
    out = _report(0.90, 0.05, cut=0.45)
    verdict_line = out.split("Verdict")[1].split("\n")[0]
    assert "flagged" in verdict_line and "clear" in verdict_line, verdict_line
