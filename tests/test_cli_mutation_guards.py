"""Killing tests for the cli.py mutation survivors (2026-08-14 sweep).

  line 127  logic: != -> ==       torch-notice gate (env var check).
  line 131  identity: is not -> is  torch-presence check.
  line 353  constant: 2 -> 3      standalone-command exit code.
  line 364  constant: False -> True  top-level parser add_help=False.

Killed here. 212 (`len(...) or 1`) and 260 (`rw and rw.available()`) are
display-only branches in the --demo flow that need a live rewriter registry to
distinguish — recorded as unkillable in survivors.md.
"""

from __future__ import annotations

import contextlib
import io

from untell.scripts import cli


class TestTorchNotice:
    """Survivor cli.py:127 — `os.environ.get("UNTELL_LITE_NO_TORCH") != "1"` mutated to `==`.

    The notice about the GPT-2 upgrade prints when the opt-out is NOT set. The
    mutation prints it only when the opt-out IS set — inverted."""

    def test_notice_prints_without_the_opt_out(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
        monkeypatch.setattr(cli, "_run_check", lambda *a, **k: 0)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            cli._run_demo("some text")
        assert "GPT-2" in buf.getvalue()

    def test_no_notice_with_the_opt_out(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        monkeypatch.setattr(cli, "_run_check", lambda *a, **k: 0)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            cli._run_demo("some text")
        assert "GPT-2" not in buf.getvalue()


class TestStandaloneCommandExit:
    """Survivor cli.py:353 — `return 2` mutated to `return 3`.

    A project console-script name typed as a subcommand exits 2 with guidance."""

    def test_voice_exits_two(self, capsys) -> None:
        assert cli.main(["voice"]) == 2
        assert "untell-voice" in capsys.readouterr().err

    def test_mcp_exits_two(self, capsys) -> None:
        assert cli.main(["mcp"]) == 2
        assert "untell-mcp" in capsys.readouterr().err


class TestParserHelpFlag:
    """Survivor cli.py:364 — `add_help=False` mutated to `add_help=True`.

    The top-level parser disables its own help so `--help` routes to the subcommand
    handling. The mutation would make argparse intercept it."""

    def test_parser_has_help_disabled(self) -> None:
        assert cli._build_parser().add_help is False
