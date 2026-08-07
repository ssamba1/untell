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


# P(AI) -> expected verdict, via humanness = 100 * (1 - p_ai).
# The 0.60 row moved from "mixed" to "likely AI" when the bands were recalibrated on 2026-08-07
# (75 / 60 / 45 / 30, fitted to 80 HC3+RAID pairs): humanness 40 now falls in the likely-AI band.
# That is the intended effect — the old bands never produced an AI verdict about AI text.
VERDICTS = [
    (0.98, "AI"),
    (0.86, "AI"),
    (0.60, "likely AI"),
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


class TestBurstinessReachesThePlainTerminalToo:
    """The burstiness row was printed only when `rich` happened to be installed.

    Uniform sentence length is the single strongest stylometric tell and the one signal the tell
    CATALOGUE cannot see, so on a plain terminal the most important line was simply absent — and
    the `is not None` fix that made a CV of exactly 0.0 visible had been applied to the rich path
    only, so the fallback hid it twice over.
    """

    def _run(self, monkeypatch, capsys, tells):
        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_tells_result(tells)
        return capsys.readouterr().out

    def test_the_cv_is_printed(self, monkeypatch, capsys):
        out = self._run(monkeypatch, capsys, {
            "tells": 3, "tells_per_100w": 10.0, "burstiness_cv": 0.42,
            "low_burstiness": False, "by_category": {"ai_vocab": 3},
        })
        assert "Burstiness CV: 0.42" in out

    def test_a_cv_of_zero_is_printed_and_marked(self, monkeypatch, capsys):
        out = self._run(monkeypatch, capsys, {
            "tells": 3, "tells_per_100w": 10.0, "burstiness_cv": 0.0,
            "low_burstiness": True, "by_category": {"ai_vocab": 3},
        })
        assert "Burstiness CV: 0.0" in out
        assert "uniform = tell" in out

    def test_an_undefined_cv_is_still_omitted(self, monkeypatch, capsys):
        out = self._run(monkeypatch, capsys, {
            "tells": 0, "tells_per_100w": 0.0, "burstiness_cv": None, "by_category": {},
        })
        assert "Burstiness" not in out

    def test_both_paths_agree_on_when_the_row_appears(self, monkeypatch, capsys):
        """The two renderers must not disagree about whether a signal exists."""
        cases = [
            ({"burstiness_cv": 0.0, "low_burstiness": True}, True),
            ({"burstiness_cv": 0.42, "low_burstiness": False}, True),
            ({"burstiness_cv": None}, False),
            ({}, False),
        ]
        for extra, expected in cases:
            tells = {"tells": 1, "tells_per_100w": 1.0, "by_category": {}, **extra}

            plain = self._run(monkeypatch, capsys, dict(tells))

            printed: list = []
            monkeypatch.setattr(rich_output, "_RICH", True)
            monkeypatch.setattr(
                rich_output, "_CONSOLE",
                # `printed` bound as a default, not captured: monkeypatch.setattr is undone at
                # TEST teardown, not at the end of an iteration, so the fake console installed
                # here outlives the loop body that made it. A late-closing capture would then
                # append into whichever list the LAST iteration created, and every assertion but
                # the final one would be reading a list some other iteration filled.
                type("C", (), {"print": lambda self, *a, _out=printed, **k: _out.append(a)})(),
            )
            rich_output.print_tells_result(dict(tells))
            rich_shown = any("Burstiness" in str(a) for args in printed for a in args)

            assert ("Burstiness" in plain) is expected, extra
            assert rich_shown is expected, extra


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


class TestNoChangeIsReportedAsSuchNotAsSuccess:
    """The loop deliberately returns the original when no candidate beats it — but the report said
    "humanization complete", showed a delta of "—", and printed the same text in two panels
    labelled "Original" and "Humanized". A run that did nothing looked exactly like one that
    worked. Measured on real input: 1-2 of 25 HC3 paragraphs come back unchanged.
    """

    SRC = "Furthermore, the system leverages robust methodologies to optimize outcomes."

    def test_plain_output_says_no_change_was_made(self, monkeypatch, capsys):
        import untell.rich_output as rich_output

        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_humanize_result(
            self.SRC, self.SRC, {"max": 0.63}, {"max": 0.63}, 3, "max_iters"
        )
        out = capsys.readouterr().out
        assert "No change was made" in out
        assert "0.63" in out  # the score it is still sitting at

    def test_plain_output_does_not_say_it_when_the_text_changed(self, monkeypatch, capsys):
        import untell.rich_output as rich_output

        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_humanize_result(
            self.SRC, "A rewritten version of it.", {"max": 0.86}, {"max": 0.02}, 2, "passed"
        )
        out = capsys.readouterr().out
        assert "No change was made" not in out

    def test_rich_output_headers_differ(self, monkeypatch):
        """Same assertion on the rich path, which is what a terminal user actually sees."""
        import untell.rich_output as rich_output

        printed = []

        class _FakeConsole:
            def print(self, *args, **kw):
                printed.append(" ".join(str(a) for a in args))

        monkeypatch.setattr(rich_output, "_RICH", True)
        monkeypatch.setattr(rich_output, "_CONSOLE", _FakeConsole())
        monkeypatch.setattr(rich_output, "_Panel", lambda *a, **k: f"PANEL({a[0]})")

        rich_output.print_humanize_result(
            self.SRC, self.SRC, {"max": 0.63}, {"max": 0.63}, 3, "max_iters"
        )
        blob = "\n".join(printed)
        assert "No change was made" in blob
        assert "Humanized" not in blob  # no panel claiming a humanized version exists
