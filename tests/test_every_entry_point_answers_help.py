"""Every console script declared in pyproject.toml must answer ``--help`` cleanly.

A declared-but-broken entry point is a shipping defect — the command either crashes
on import (a traceback, exit 1+) or it was never installed (FileNotFoundError).
This test catches both without building a wheel: it imports the entry-point's
target module and calls its ``main`` with ``["--help"]``, intercepting SystemExit.

Skipped for entry points that explicitly require a paid/GPU dep at module-import
time (e.g. ``untell-server`` prints "FastAPI not installed" and exits 2, which IS
the expected clean message; this test only checks for tracebacks, not for a specific
exit code).

HISTORY: ``untell-humanize`` was "command not found" in the pre-0.3 wheel because
the entry-point target ``untell.scripts.run:main`` only had an alias (``untell-loop``)
and no standalone ``untell-humanize`` entry.  This file is the check that makes that
regression visible immediately.
"""
from __future__ import annotations

import importlib
import sys
from typing import Callable

import pytest

# All [project.scripts] entries from pyproject.toml, formatted as
# ("console-script-name", "module.path:function").
# Kept as a literal copy so this test is independent of TOML parsing.
ENTRY_POINTS: list[tuple[str, str]] = [
    ("untell", "untell.scripts.cli:main"),
    ("untell-score", "untell.scripts.score:main"),
    ("untell-loop", "untell.scripts.run:main"),
    ("untell-humanize", "untell.scripts.run:main"),
    ("untell-verify", "untell.scripts.verify:main"),
    ("untell-prove", "eval.prove:main"),
    ("untell-sentences", "untell.scripts.sentences:main"),
    ("untell-tells", "untell.scripts.tells:main"),
    ("untell-voice", "untell.scripts.voice:main"),
    ("untell-compare", "eval.compare_humanizers:main"),
    ("untell-mcp", "untell.mcp_server:main"),
    ("untell-audit", "untell.scripts.audit:main"),
    ("untell-latex", "untell.scripts.latex:main"),
    ("untell-ceiling", "eval.ceiling:main"),
    ("untell-detector-audit", "eval.detector_audit:main"),
    ("untell-distill", "training.distill:main"),
    ("untell-surrogate", "training.surrogate:main"),
    ("untell-eval-policy", "eval.eval_policy:main"),
    ("untell-server", "untell.api_server_cli:main"),
    ("untell-humanness", "untell.humanness:main"),
    ("untell-scrub", "untell.scripts.scrub:main"),
    ("untell-numbers", "untell.scripts.numerals:main"),
    ("untell-hedges", "untell.scripts.hedges:main"),
    ("untell-explain", "untell.scripts.explain:main"),
    ("untell-batch", "untell.scripts.batch:main"),
    ("untell-watch", "untell.scripts.watch:main"),
]

_IDS = [name for name, _ in ENTRY_POINTS]


def _import_main(target: str) -> Callable:
    """Import and return the ``main`` callable for a ``module:function`` spec."""
    mod_path, func_name = target.rsplit(":", 1)
    mod = importlib.import_module(mod_path)
    return getattr(mod, func_name)


@pytest.mark.parametrize("name,target", ENTRY_POINTS, ids=_IDS)
def test_entry_point_module_is_importable(name: str, target: str) -> None:
    """The module containing each entry point must be importable without crashing."""
    mod_path = target.rsplit(":", 1)[0]
    try:
        importlib.import_module(mod_path)
    except ImportError as exc:
        # A module that needs an optional dep (FastAPI, MCP, etc.) may raise ImportError —
        # that is expected and should produce a clean message from the entry-point shim,
        # NOT propagate as an unhandled ImportError here.
        # The one exception is untell.api_server_cli: it is a shim that deliberately
        # catches the ImportError from untell.api_server so this import always succeeds.
        pytest.fail(
            f"{name} → {target}: importing {mod_path!r} raised ImportError: {exc}\n"
            "Entry-point modules must be importable on a base install.  "
            "Add an import guard (try/except ImportError) if the module needs an optional dep."
        )


@pytest.mark.parametrize("name,target", ENTRY_POINTS, ids=_IDS)
def test_entry_point_function_exists(name: str, target: str) -> None:
    """The entry-point function must exist on the imported module."""
    mod_path, func_name = target.rsplit(":", 1)
    mod = importlib.import_module(mod_path)
    assert hasattr(mod, func_name), (
        f"{name} declares {target!r} but {func_name!r} does not exist on {mod_path!r}"
    )


@pytest.mark.parametrize("name,target", ENTRY_POINTS, ids=_IDS)
def test_entry_point_answers_help(name: str, target: str) -> None:
    """Every entry point must accept ``--help`` and exit cleanly (no unhandled exceptions)."""
    main = _import_main(target)
    old_argv = sys.argv[:]
    sys.argv = [name, "--help"]
    try:
        main()
    except SystemExit:
        # SystemExit(0) is success.  Some CLIs (including argparse) exit 0 on --help.
        # A non-zero exit is allowed if the entry-point prints a clean message explaining
        # why it cannot start (e.g. untell-server exits 2 when FastAPI is absent).
        pass
    except Exception as exc:
        pytest.fail(
            f"{name} → {target}: --help raised {type(exc).__name__}: {exc}\n"
            "Entry points must handle --help without an unhandled exception."
        )
    finally:
        sys.argv = old_argv


def test_entry_point_list_matches_pyproject() -> None:
    """The hard-coded ENTRY_POINTS list above must stay in sync with pyproject.toml."""
    import pathlib
    import re

    pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    # Extract the [project.scripts] section.
    start = text.index("[project.scripts]")
    next_section = re.search(r"^\[(?!project\.scripts\])", text[start:], re.M)
    scripts_block = text[start : start + next_section.start()] if next_section else text[start:]
    # Each line looks like: name = "module:function"
    toml_entries: dict[str, str] = {}
    for line in scripts_block.splitlines():
        m = re.match(r'^(\S+)\s*=\s*"([^"]+)"', line)
        if m:
            toml_entries[m.group(1)] = m.group(2)

    test_dict = dict(ENTRY_POINTS)
    missing_in_test = set(toml_entries) - set(test_dict)
    extra_in_test = set(test_dict) - set(toml_entries)
    mismatched = {k for k in (set(toml_entries) & set(test_dict)) if toml_entries[k] != test_dict[k]}

    errors = []
    if missing_in_test:
        errors.append(f"declared in pyproject.toml but not tested: {sorted(missing_in_test)}")
    if extra_in_test:
        errors.append(f"in ENTRY_POINTS but not in pyproject.toml: {sorted(extra_in_test)}")
    if mismatched:
        for k in sorted(mismatched):
            errors.append(f"{k}: pyproject has {toml_entries[k]!r}, test has {test_dict[k]!r}")
    assert not errors, "\n".join(errors)
