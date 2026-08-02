"""Rich terminal output — the display layer that reports the loop's result to the user.

Display bugs of this shape have shipped here before (browser_check read "Human: 45%" as 45% AI).
A number rendered wrongly is indistinguishable, to the reader, from the loop working wrongly.
"""

from __future__ import annotations

import pytest

from untell import rich_output
from untell.humanness import classification


def _verdict(p_ai: float) -> str:
    """The mapping print_humanize_result uses: P(AI) in [0,1] -> humanness 0-100 -> a band."""
    return classification((1.0 - p_ai) * 100.0)


VERDICTS = [
    (0.98, "AI"),
    (0.86, "AI"),
    (0.60, "mixed"),
    (0.50, "mixed"),
    (0.29, "mostly human"),
    (0.10, "human"),
    (0.00, "human"),
]


@pytest.mark.parametrize("p_ai,expected", VERDICTS)
def test_verdict_scale_is_converted_not_passed_through(p_ai, expected):
    """`classification()` takes a HUMANNESS score in 0-100 (higher = more human); `max` is P(AI)
    in 0-1. Passing P(AI) straight in put every value under the bottom band, so the Verdict row
    printed "AI" -> "AI" for every input — including a run that took 0.86 down to 0.02. It was not
    merely wrong, it was constant: the row carried no information at all."""
    assert _verdict(p_ai) == expected
    # The bug, stated directly: the raw value classifies as "AI" whatever it is.
    assert classification(p_ai) == "AI"


def test_verdict_actually_varies_across_the_range():
    """The property the constant-output bug violated."""
    assert len({_verdict(p) for p in (0.0, 0.3, 0.5, 0.7, 1.0)}) > 1


def test_uniform_burstiness_row_is_not_hidden_by_falsy_zero(monkeypatch, capsys):
    """A CV of exactly 0.0 means perfectly uniform sentence lengths — the strongest burstiness
    tell there is. `if tells.get("burstiness_cv"):` hid the row precisely when it mattered most."""
    printed = []
    monkeypatch.setattr(rich_output, "_RICH", True)
    monkeypatch.setattr(
        rich_output, "_CONSOLE", type("C", (), {"print": lambda self, *a, **k: printed.append(a)})()
    )
    rich_output.print_tells_result(
        {"tells": 3, "tells_per_100w": 10.0, "burstiness_cv": 0.0, "low_burstiness": True,
         "by_category": {"ai_vocab": 3}}
    )
    assert any("Burstiness" in str(a) for args in printed for a in args), (
        "a CV of 0.0 was hidden by a truthiness check"
    )


def test_undefined_burstiness_row_is_still_omitted(monkeypatch):
    """None means undefined (fewer than two sentences) and must stay hidden — the fix is about
    zero, not about printing a row for a value that does not exist."""
    printed = []
    monkeypatch.setattr(rich_output, "_RICH", True)
    monkeypatch.setattr(
        rich_output, "_CONSOLE", type("C", (), {"print": lambda self, *a, **k: printed.append(a)})()
    )
    rich_output.print_tells_result(
        {"tells": 0, "tells_per_100w": 0.0, "burstiness_cv": None, "by_category": {}}
    )
    assert not any("Burstiness" in str(a) for args in printed for a in args)


def test_plain_text_fallback_needs_no_rich(monkeypatch, capsys):
    """The module is documented to degrade gracefully; the fallback path must not touch _CONSOLE."""
    monkeypatch.setattr(rich_output, "_RICH", False)
    monkeypatch.setattr(rich_output, "_CONSOLE", None)

    rich_output.print_humanize_result(
        "original text", "final text", {"max": 0.86}, {"max": 0.02}, 2, "passed"
    )
    rich_output.print_tells_result({"tells": 1, "tells_per_100w": 5.0, "by_category": {"cliche": 1}})
    rich_output.print_humanness(73.0, "mostly human")
    rich_output.progress_iteration(1, 3, "full", 0.42)

    out = capsys.readouterr().out
    assert "0.86" in out and "0.02" in out
    assert "Humanness: 73.0/100" in out
    assert "tier=full" in out
