"""Every declared console script must answer ``--help``.

``untell-audit`` already checks that each script in ``[project.scripts]`` is declared and that its
entry point resolves to a real callable. Both passed for ``untell-mcp``, which then printed nothing
and exited 0 — because its ``main`` ignored ``argv`` entirely and went straight to serving JSON-RPC
on stdin. Resolving is not the same as running, and "exited 0" is not the same as "did something
sensible": the check that would have caught it is the one a user performs first.

Kept out of ``untell-audit`` deliberately. Spawning 23 subprocesses takes long enough that the
audit would stop being the thing you run casually, and the audit's job is documentation claims
rather than runtime behaviour.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _declared_scripts() -> dict[str, str]:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    block = text[text.index("[project.scripts]") :]
    end = block.find("\n[", 1)
    if end != -1:
        block = block[:end]
    return dict(re.findall(r'^([\w-]+)\s*=\s*"([^"]+)"', block, re.M))


SCRIPTS = sorted(_declared_scripts().items())


def test_there_are_scripts_to_check() -> None:
    """A parsing change that returned {} would make every test below vacuously pass."""
    assert len(SCRIPTS) >= 20, f"only found {len(SCRIPTS)} console scripts"


@pytest.mark.parametrize("name,target", SCRIPTS, ids=[n for n, _ in SCRIPTS])
def test_script_responds_to_help(name: str, target: str) -> None:
    module = target.split(":")[0]
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=300,
        cwd=REPO,
    )
    assert result.returncode == 0, (
        f"{name} (-m {module} --help) exited {result.returncode}: "
        f"{(result.stderr or result.stdout)[-300:]}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "usage" in combined, (
        f"{name} exited 0 but printed no usage line. Silence from --help is "
        f"indistinguishable from a broken install. Output: {combined[:200]!r}"
    )


# Every command that takes --file. A mistyped path is the most common way any of them is used
# wrongly, and it used to produce a Python stack trace from seven of the eight.
FILE_COMMANDS = [
    "untell.scripts.run",
    "untell.scripts.score",
    "untell.scripts.tells",
    "untell.scripts.sentences",
    "untell.scripts.verify",
    "untell.scripts.scrub",
    "untell.humanness",
]


@pytest.mark.parametrize("module", FILE_COMMANDS)
def test_a_missing_file_is_one_line_not_a_traceback(module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--file", "definitely-not-a-real-file.txt"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, cwd=REPO,
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, f"{module} raised instead of reporting:\n{combined[-400:]}"
    assert "no such file" in combined.lower(), combined[-300:]
    assert result.returncode == 2, f"expected exit 2 (usage error), got {result.returncode}"


@pytest.mark.parametrize("module", FILE_COMMANDS)
def test_a_directory_says_directory_not_permission_denied(module):
    """The message that made this worth fixing. Opening a directory raises PermissionError on
    Windows, so every one of these told the user to check file permissions for a problem that has
    nothing to do with permissions."""
    result = subprocess.run(
        [sys.executable, "-m", module, "--file", "docs"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, cwd=REPO,
    )
    combined = (result.stdout + result.stderr).lower()
    assert "Traceback" not in (result.stdout + result.stderr), combined[-400:]
    assert "directory" in combined, combined[-300:]
    assert "permission" not in combined, (
        "still blaming permissions for a directory: " + combined[-200:]
    )
    assert result.returncode == 2


def test_the_file_command_list_is_not_empty():
    """Guards the guard: an empty list would make both parametrised tests vacuous."""
    assert len(FILE_COMMANDS) >= 6
