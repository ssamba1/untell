"""`untell explain` reading from piped stdin: the one input path the CLI tests did not
reach (they cover argv, --file, and the no-input refusal)."""

from __future__ import annotations

import untell.scripts.io_utils as io_utils
from untell.scripts.explain import main


def test_piped_stdin_text_is_explained(monkeypatch, capsys) -> None:
    monkeypatch.setattr(io_utils, "read_stdin_or_none", lambda: "See Smith (2020); it cost $500.")
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "citation" in out
    assert "number" in out
    assert "Smith (2020)" in out


def test_piped_stdin_with_no_spans_says_so(monkeypatch, capsys) -> None:
    monkeypatch.setattr(io_utils, "read_stdin_or_none", lambda: "plain prose with no facts")
    assert main([]) == 0
    assert "No spans locked" in capsys.readouterr().out
