"""The remaining rich_output branches: the no-rich import path, the word-diff delete opcode,
the saturated-max note, and the rich-only render rows (tells delta, warning panel, humanness
bar, progress line). Each asserts on the rendered output, not on incidental side effects.
"""

from __future__ import annotations

import importlib

import pytest

from untell import rich_output


class TestModuleDegradesWhenRichIsAbsent:
    def test_import_succeeds_and_flags_the_fallback(self):
        """The module must import with _RICH False and _CONSOLE None when rich is missing —
        that is the documented graceful-degradation contract for `pip install untell` without
        the rich extra."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "rich" or name.startswith("rich."):
                raise ImportError("no rich here")
            return real_import(name, *a, **k)

        builtins.__import__ = fake_import
        try:
            importlib.reload(rich_output)
            assert rich_output._RICH is False
            assert rich_output._CONSOLE is None
        finally:
            builtins.__import__ = real_import
            importlib.reload(rich_output)  # restore the real (rich-installed) state
            assert rich_output._RICH is True

    def test_fallback_diff_returns_the_rewrite_verbatim(self, monkeypatch):
        """Without rich there is no markup engine: the diff is the rewritten text itself."""
        monkeypatch.setattr(rich_output, "_RICH", False)
        assert rich_output._diff_words("one two three", "one two three four") == "one two three four"


class TestWordDiff:
    @staticmethod
    def _styles(out):
        return {str(s.style): out.plain[s.start:s.end] for s in out.spans}

    def test_deleted_words_are_shown_struck_through(self, monkeypatch):
        """A deletion must leave a trace in the report (dim/strike), not a blank space."""
        monkeypatch.setattr(rich_output, "_RICH", True)
        out = rich_output._diff_words("one two three", "one three")
        styles = self._styles(out)
        assert "two" in styles["dim strike"]  # the deleted word is still visible
        assert "strike" in "dim strike"

    def test_inserted_words_are_marked_added(self, monkeypatch):
        monkeypatch.setattr(rich_output, "_RICH", True)
        out = rich_output._diff_words("one three", "one two three")
        styles = self._styles(out)
        assert "two" in styles["bold green"]  # the added word is shown as an addition


class TestSaturatedMaxNote:
    """A pinned max (>= 0.99) cannot show an improvement, so the report must say the mean moved
    instead — and must still say SOMETHING when the mean is absent."""

    def _run_plain(self, monkeypatch, capsys, pre, post):
        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_humanize_result(
            "orig", "rewritten", pre, post, 2, "passed"
        )
        return capsys.readouterr().out

    def test_plain_output_names_the_mean_when_both_means_exist(self, monkeypatch, capsys):
        out = self._run_plain(
            monkeypatch, capsys,
            {"max": 0.995, "mean": 0.7000}, {"max": 0.999, "mean": 0.5500},
        )
        assert "pinned" in out
        assert "0.7000 -> 0.5500" in out

    def test_plain_output_still_says_pinned_when_mean_is_missing(self, monkeypatch, capsys):
        out = self._run_plain(monkeypatch, capsys, {"max": 0.995}, {"max": 0.999})
        assert "pinned" in out
        assert "Ensemble mean" not in out

    def test_rich_output_prints_the_mean_note_too(self, monkeypatch):
        printed: list = []
        monkeypatch.setattr(rich_output, "_RICH", True)
        monkeypatch.setattr(
            rich_output, "_CONSOLE",
            type("C", (), {"print": lambda self, *a, _out=printed, **k: _out.append(a)})(),
        )
        rich_output.print_humanize_result(
            "orig", "rewritten", {"max": 0.995, "mean": 0.7}, {"max": 0.999, "mean": 0.55},
            2, "passed",
        )
        blob = "\n".join(str(a) for args in printed for a in args)
        assert "pinned" in blob and "Ensemble mean" in blob


class TestPlainReportRows:
    def test_tell_counts_are_printed_on_a_plain_terminal(self, monkeypatch, capsys):
        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_humanize_result(
            "orig", "rewritten", {"max": 0.86}, {"max": 0.02}, 2, "passed",
            tells_before=4, tells_after=1,
        )
        out = capsys.readouterr().out
        assert "AI tells: 4 -> 1" in out

    def test_warning_reaches_a_plain_terminal(self, monkeypatch, capsys):
        monkeypatch.setattr(rich_output, "_RICH", False)
        monkeypatch.setattr(rich_output, "_CONSOLE", None)
        rich_output.print_humanize_result(
            "orig", "rewritten", {"max": 0.86}, {"max": 0.02}, 2, "passed",
            warning="threshold not calibrated",
        )
        assert "NOTE: threshold not calibrated" in capsys.readouterr().out


class TestRichOnlyRenderRows:
    def _console(self, monkeypatch, panel_marker="PANEL"):
        printed: list = []
        monkeypatch.setattr(rich_output, "_RICH", True)
        monkeypatch.setattr(
            rich_output, "_CONSOLE",
            type("C", (), {"print": lambda self, *a, _out=printed, **k: _out.append(a)})(),
        )
        monkeypatch.setattr(
            rich_output, "_Panel",
            lambda *a, _m=panel_marker, **k: f"{_m}(title={k.get('title')})",
        )
        return printed

    def test_tells_row_is_rendered_in_the_rich_table(self, monkeypatch):
        """The tells row is added to the score table; capture add_row calls to see its cells."""
        rows: list = []

        class _FakeTable:
            def __init__(self, *a, **k):
                pass

            def add_column(self, *a, **k):
                pass

            def add_row(self, *a, **k):
                rows.append(a)

            @classmethod
            def grid(cls, *a, **k):
                return cls()

        monkeypatch.setattr(rich_output, "_Table", _FakeTable)
        self._console(monkeypatch)
        rich_output.print_humanize_result(
            "orig", "rewritten", {"max": 0.86}, {"max": 0.02}, 2, "passed",
            tells_before=4, tells_after=1,
        )
        assert any(r[0] == "AI tells" and r[1] == "4" and r[2] == "1" for r in rows)
        # The delta is negative (tells fell), so it is styled green, not dim.
        assert any(r[0] == "AI tells" and "green" in r[3] and "-3" in r[3] for r in rows)

    def test_warning_is_panelled_on_the_rich_path(self, monkeypatch):
        printed = self._console(monkeypatch)
        rich_output.print_humanize_result(
            "orig", "rewritten", {"max": 0.86}, {"max": 0.02}, 2, "passed",
            warning="threshold not calibrated",
        )
        blob = "\n".join(str(a) for args in printed for a in args)
        assert "PANEL(title=Warning)" in blob

    @pytest.mark.parametrize(
        "score,color",
        [(85.0, "green"), (55.0, "yellow"), (20.0, "red")],
    )
    def test_humanness_bar_uses_the_right_band_color(self, monkeypatch, score, color):
        printed = self._console(monkeypatch)
        rich_output.print_humanness(score, "a class")
        blob = "\n".join(str(a) for args in printed for a in args)
        assert f"{color}" in blob
        assert "█" in blob  # the bar itself is drawn

    def test_progress_line_with_and_without_a_score(self, monkeypatch):
        printed = self._console(monkeypatch)
        assert rich_output.progress_iteration(1, 3, "full", 0.42) is None
        assert rich_output.progress_iteration(2, 3, "full") is None
        blob = "\n".join(str(a) for args in printed for a in args)
        assert "Iteration 1/3" in blob and "P(AI)=0.42" in blob
        assert "Iteration 2/3" in blob and "P(AI)=0.42" not in blob.split("Iteration 2/3")[1]
