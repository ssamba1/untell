"""`untell voice ...` humanized the word "voice" and exited 0.

The unified CLI treats an unrecognised first argument as text — a documented and useful shortcut,
since `untell "some AI text"` is how the README tells people to start. But it swallowed every
mistyped or misremembered subcommand, because the name simply became the input. MEASURED:

    untell notacommand --json   ->   {"final": "notacommand", ...}   exit 0

The word was rewritten and returned as the answer, with no error and a success exit code. The same
happened for `untell voice`, `untell server`, `untell mcp`, `untell audit`, `untell latex` — real
entry points this project ships as `untell-voice`, `untell-server` and so on, which are NOT
subcommands of the unified command. A user who read `pyproject` or the docs and typed the obvious
thing got their command name humanized.

Guessing in general is not safe: a single word really can be the text someone wants rewritten, and
refusing every unknown first argument would break the shortcut. So the refusal is narrow — only for
names THIS PROJECT ships as a console script. Those are words a user typed because they read
something, not prose they want back with fewer AI tells, and the message names the command that
does exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

STANDALONE = ["voice", "latex", "audit", "mcp", "server", "distill", "surrogate", "eval-policy"]


def _run(*args: str) -> tuple[int, str, str]:
    env = {**os.environ, "UNTELL_LITE_NO_TORCH": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "untell.scripts.cli", *args],
        capture_output=True, text=True, env=env, cwd=str(_ROOT), timeout=300,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


@pytest.mark.parametrize("name", STANDALONE)
def test_a_standalone_command_name_is_refused_not_rewritten(name: str) -> None:
    code, out, err = _run(name, "--json")
    combined = out + err

    assert code == 2, f"`untell {name}` exited {code}, expected 2"
    assert "not an `untell` subcommand" in combined, combined[:200]
    assert f"untell-{name}" in combined, "the error should name the command that does exist"
    assert '"final"' not in out, f"`untell {name}` still humanized the word: {out[:150]}"


@pytest.mark.parametrize("name", STANDALONE)
def test_every_refused_name_really_is_a_shipped_console_script(name: str) -> None:
    """The refusal list must not grow into ordinary vocabulary.

    Each entry has to be a console script this project actually ships, otherwise the guard is
    refusing a word someone might legitimately want humanized.
    """
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f"untell-{name}" in pyproject, (
        f"{name!r} is refused as a standalone command but pyproject declares no `untell-{name}`"
    )


def test_the_humanize_shortcut_still_works() -> None:
    """Guards the guard, and it is the whole risk of this change. The shortcut is documented, so a
    refusal that caught ordinary text would break the first thing the README tells anyone to do."""
    code, out, err = _run(
        "Moreover, the framework leverages robust methods.",
        "--tier", "lite", "--max-iters", "1", "--rewriter", "surgical", "--json",
    )
    assert code == 0, f"the humanize shortcut broke: {(out + err)[-250:]}"
    assert "final" in json.loads(out)


def test_a_single_ordinary_word_is_still_treated_as_text() -> None:
    """The narrowest case the shortcut has to keep: one word that is not a shipped command."""
    code, out, err = _run(
        "robust", "--tier", "lite", "--max-iters", "1", "--rewriter", "surgical", "--json",
    )
    assert code == 0, f"an ordinary word was refused: {(out + err)[-200:]}"
    assert "final" in json.loads(out)


def test_a_real_subcommand_still_dispatches() -> None:
    code, out, err = _run("tells", "Moreover, this is robust.")
    assert code == 0, (out + err)[-200:]
    assert "AI-tells" in out


def test_no_refused_name_is_also_a_subcommand() -> None:
    """If a name were both, the guard would shadow a working subcommand."""
    from untell.scripts.cli import _COMMANDS, _STANDALONE_ONLY

    overlap = _STANDALONE_ONLY & set(_COMMANDS)
    assert not overlap, f"these are refused AND dispatchable: {sorted(overlap)}"
