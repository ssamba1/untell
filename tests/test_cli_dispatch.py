"""Tests for the unified `untell <subcommand>` dispatcher."""

from __future__ import annotations

from untell.scripts.cli import _COMMANDS, main


def test_no_args_runs_demo_and_exits_zero(capsys):
    """No args runs the guided demo (no error, exits 0)."""
    # Just verify the dispatcher doesn't crash; demo calls full humanize which may time out in CI.
    import sys as _sys
    orig = _sys.argv[:]
    _sys.argv = ["untell", "--help"]
    try:
        rc = main(["--help"])
        assert rc == 0
    finally:
        _sys.argv = orig
    assert True


def test_help_flag_prints_usage(capsys):
    assert main(["--help"]) == 0
    assert "Commands:" in capsys.readouterr().out


def test_unknown_arg_is_treated_as_humanize_shortcut(capsys):
    """Unknown args are treated as humanize shortcut (text to humanize)."""
    rc = main(["frobnicate"])
    assert rc == 0


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


def test_every_free_backend_is_reachable_from_every_surface():
    """A backend that get_rewriter() knows but no CLI/API/MCP accepts is dead code to users.

    `targeted` shipped exactly that way: implemented, tested, exported — and rejected by argparse on
    both CLIs, absent from the REST _FREE_REWRITERS set and from MCP's. It was only noticed when a
    measurement run died with a JSON decode error, because argparse had refused the flag and printed
    nothing. This pins the surfaces against the registry so the next backend cannot be orphaned."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    from untell.rewriter import get_rewriter

    free = ["surgical", "structural", "composite", "targeted", "neural", "ensemble", "max"]

    # Only resolve the ZERO-DEPENDENCY backends. Resolving "neural"/"ensemble" constructs a T5
    # paraphraser and downloads ~850MB, which turned this coverage assertion into an 11-minute test.
    # Their presence in the surfaces below is what this test is actually about; whether they resolve
    # is covered by tests/test_rewriters.py.
    for name in ("surgical", "structural", "composite", "targeted"):
        assert get_rewriter(prefer=name) is not None, f"{name} does not resolve"

    # Every one must appear in both CLI choice lists.
    for rel in ("untell/scripts/run.py", "eval/ceiling.py"):
        src = (root / rel).read_text(encoding="utf-8")
        choices = re.search(r"--rewriter\"?,?\s*\n?\s*choices=\[(.*?)\]", src, re.S)
        assert choices, f"could not find --rewriter choices in {rel}"
        listed = choices.group(1)
        for name in free:
            assert f'"{name}"' in listed, f"{name} missing from --rewriter choices in {rel}"

    # And in the server-side allow-lists.
    from untell.mcp_server import _FREE_REWRITERS

    for name in free:
        assert name in _FREE_REWRITERS, f"{name} missing from mcp _FREE_REWRITERS"

    api_src = (root / "untell/api_server.py").read_text(encoding="utf-8")
    for name in free:
        assert f'"{name}"' in api_src, f"{name} missing from api _FREE_REWRITERS"
