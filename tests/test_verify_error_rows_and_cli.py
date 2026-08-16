"""verify() and `untell-verify` CLI branches the detector-level tests do not reach:
sandbox mode, per-checker error rows (no signal / NaN / raising browser checker), the
commercial-only threshold caveat, and the CLI input-error paths."""

from __future__ import annotations

import untell.detectors.commercial as commercial
from untell.scripts.verify import _render, main, verify


class _FakeDetector:
    def __init__(self, name, score_result):
        self.name = name
        self._score = score_result
        self.sandbox = False

    def available(self):
        return True

    def score(self, text):
        return self._score(text) if callable(self._score) else self._score


def test_sandbox_flag_is_forwarded_to_copyleaks(monkeypatch) -> None:
    fake = _FakeDetector("copyleaks", 0.9)
    monkeypatch.setattr(commercial, "CopyleaksDetector", _FakeDetector)
    monkeypatch.setattr(commercial, "commercial_detectors", lambda: [fake])
    out = verify("hello world", sandbox=True, tier=None)
    assert fake.sandbox is True
    assert out["results"]["copyleaks"]["ai"] == 0.9


def test_a_commercial_detector_with_no_signal_is_an_error_row(monkeypatch) -> None:
    fake = _FakeDetector("nosignal", None)
    monkeypatch.setattr(commercial, "commercial_detectors", lambda: [fake])
    out = verify("hello world", tier=None)
    row = out["results"]["nosignal"]
    assert row["ai"] is None
    assert row["passes"] is False
    assert "no signal" in row["error"]


def test_a_nan_score_is_an_error_row_not_a_pass(monkeypatch) -> None:
    fake = _FakeDetector("nancheck", float("nan"))
    monkeypatch.setattr(commercial, "commercial_detectors", lambda: [fake])
    out = verify("hello world", tier=None)
    row = out["results"]["nancheck"]
    assert row["ai"] is None
    assert row["passes"] is False
    assert "NaN" in row["error"]


def test_a_raising_browser_checker_is_an_error_row(monkeypatch) -> None:
    class _Boom:
        def available(self):
            return True

        def check(self, text):
            raise RuntimeError("playwright died")

    monkeypatch.setattr(
        "untell.browser_check.get_browser_checker", lambda site: _Boom()
    )
    out = verify("hello world", tier=None, browser=["zerogpt"])
    row = out["results"]["zerogpt(web)"]
    assert row["ai"] is None
    assert row["passes"] is False
    assert "playwright died" in row["error"]


def test_an_unreachable_threshold_is_named_in_commercial_only_mode() -> None:
    out = verify("hello world", threshold=5, tier=None)
    assert "no text can ever reach it" in out["warning"]


def test_render_prints_error_rows_and_marks_the_aggregate(monkeypatch) -> None:
    d = {
        "results": {
            "local:x": {"ai": None, "passes": False, "error": "no local detector produced a score"},
            "local:max (lite)": {"ai": 0.1, "passes": True, "verdict_threshold": 0.3},
        },
        "threshold": 0.3,
        "passes_all": False,
        "n_configured": 1,
        "n_passing": 0,
    }
    text = _render(d)
    assert "ERROR: no local detector produced a score" in text
    assert "aggregate, not counted" in text
    assert "FAILS — 0/1 checkers passed" in text


def test_cli_no_input_exits_two(monkeypatch, capsys) -> None:
    import untell.scripts.io_utils as io_utils

    monkeypatch.setattr(io_utils, "read_stdin_or_none", lambda: None)
    assert main(["--tier", "lite"]) == 2
    assert "no input" in capsys.readouterr().out


def test_cli_empty_input_exits_two(capsys) -> None:
    assert main(["   ", "--tier", "lite"]) == 2
    assert "empty input" in capsys.readouterr().out


def test_cli_file_input_runs_a_lite_verdict(capsys, tmp_path) -> None:
    f = tmp_path / "text.txt"
    f.write_text("The cat sat on the mat.", encoding="utf-8")
    assert main(["--file", str(f), "--tier", "lite"]) in (0, 1)
    out = capsys.readouterr().out
    assert "AI-checker verification" in out
