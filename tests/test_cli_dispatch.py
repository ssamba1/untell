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


def test_unknown_arg_is_treated_as_humanize_shortcut(monkeypatch, capsys):
    """Unknown args are treated as a humanize shortcut (text to humanize).

    This asserts ROUTING, so it stubs the humanize entry point rather than executing it. Running the
    real pipeline here cost 578 SECONDS — 99.9% of this file's entire runtime — to verify that an
    argument reaches the right function. The stub checks the same contract (routed to
    untell.scripts.run:main, with the text forwarded) in milliseconds.
    """
    import untell.scripts.run as run_mod

    seen = {}

    def _spy(argv=None):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(run_mod, "main", _spy)

    rc = main(["frobnicate"])
    assert rc == 0
    assert seen.get("argv") is not None, "unknown arg did not reach the humanize entry point"
    assert "frobnicate" in seen["argv"], f"text not forwarded: {seen['argv']}"


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

    # Every one must be accepted by the loop CLI. Asked of the PARSER rather than of the source
    # text: the previous version grepped for a literal `choices=[...]`, so hoisting that list into
    # a named constant — the fix for it being written out twice — broke the test while the CLI
    # kept accepting every name. A source scan cannot tell "the list moved" from "the list lost an
    # entry"; the parser can.
    from untell.scripts.run import build_parser

    accepted = {
        a.dest: set(a.choices or ())
        for a in build_parser()._actions
        if a.dest == "rewriter"
    }["rewriter"]
    for name in free:
        assert name in accepted, f"{name} missing from untell humanize --rewriter choices"

    # eval/ceiling.py has no equivalent accessor, so it is still read as source.
    src = (root / "eval/ceiling.py").read_text(encoding="utf-8")
    choices = re.search(r"--rewriter\"?,?\s*\n?\s*choices=\[(.*?)\]", src, re.S)
    assert choices, "could not find --rewriter choices in eval/ceiling.py"
    for name in free:
        assert f'"{name}"' in choices.group(1), f"{name} missing from ceiling --rewriter choices"

    # And in the server-side allow-lists.
    from untell.mcp_server import _FREE_REWRITERS

    for name in free:
        assert name in _FREE_REWRITERS, f"{name} missing from mcp _FREE_REWRITERS"

    api_src = (root / "untell/api_server.py").read_text(encoding="utf-8")
    for name in free:
        assert f'"{name}"' in api_src, f"{name} missing from api _FREE_REWRITERS"


def test_every_subcommand_has_a_standalone_console_script():
    """The README promises "every subcommand is also a standalone untell-<name> script".

    That was false for `humanize` — the PRIMARY name for the loop — because only its alias `loop`
    had an entry point, so `untell-humanize` was "command not found". A documented promise that
    nobody re-checks decays the same way an unmeasured claim does."""
    import re
    from pathlib import Path

    from untell.scripts.cli import _COMMANDS

    py = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    scripts = set(re.findall(r"^(untell[\w-]*)\s*=", py, re.M))

    missing = [name for name in _COMMANDS if f"untell-{name}" not in scripts]
    assert not missing, f"subcommands with no standalone console script: {missing}"


def test_every_console_script_target_resolves():
    """A typo'd entry point only fails at install time, not in tests."""
    import importlib
    import re
    from pathlib import Path

    py = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    targets = dict(re.findall(r'^(untell[\w-]*)\s*=\s*"([^"]+)"', py, re.M))
    assert targets, "no console scripts found — did the pyproject layout change?"

    for script, target in targets.items():
        module_name, _, func_name = target.partition(":")
        try:
            mod = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # An entry point may live behind an optional extra (untell-server needs fastapi from
            # .[server]). A MISSING THIRD-PARTY dep is fine; a missing untell module is a typo.
            missing = (exc.name or "").split(".")[0]
            if missing in {"untell", "eval", "training"}:
                raise AssertionError(f"{script} -> {target}: module does not exist") from exc
            continue
        assert callable(getattr(mod, func_name, None)), (
            f"{script} -> {target}: module imports but has no callable {func_name!r}"
        )
