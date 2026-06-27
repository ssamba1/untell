"""Tests for the unified `untell <subcommand>` dispatcher."""

from __future__ import annotations

from untell.scripts.cli import _COMMANDS, main


def test_no_args_prints_usage_and_exits_zero(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Usage: untell <command>" in out
    for cmd in ("humanize", "score", "tells", "verify", "compare", "ceiling"):
        assert cmd in out


def test_help_flag_prints_usage(capsys):
    assert main(["--help"]) == 0
    assert "Commands:" in capsys.readouterr().out


def test_unknown_command_errors(capsys):
    rc = main(["frobnicate"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown command 'frobnicate'" in err


def test_dispatch_routes_to_subcommand(capsys):
    # `untell tells <text>` must run the tells scorer and produce its output.
    rc = main(["tells", "Furthermore, we leverage robust and seamless solutions throughout today."])
    assert rc == 0
    assert "AI-tells:" in capsys.readouterr().out


def test_dispatch_passes_flags_through(capsys):
    rc = main(["tells", "--json", "We use simple words here in this plain sentence about nothing."])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip().startswith("{")  # --json was forwarded to the tells subcommand


def test_loop_is_alias_for_humanize():
    assert _COMMANDS["loop"] == _COMMANDS["humanize"]


def test_all_command_targets_are_importable():
    # Every registered target "module:func" must resolve — guards against a typo'd route.
    import importlib

    for target in set(_COMMANDS.values()):
        module_name, func_name = target.split(":")
        mod = importlib.import_module(module_name)
        assert callable(getattr(mod, func_name))
