"""Run-as-file support: every CLI module that ships the direct-run sys.path block must
actually run when executed by path on a bare interpreter.

Several modules carry this preamble::

    if __package__ in (None, ""):
        ... insert the repo root on sys.path ...

so the SKILL.md zero-dependency workflow (`python untell/scripts/<name>.py ...`) works
from any cwd. It is only reachable when the file is executed as ``__main__`` — an import
never hits it. ``runpy.run_path(..., run_name="__main__")`` executes the real file in
that exact mode (``__package__`` is empty, so the block runs), and the module's own
``if __name__ == "__main__": raise SystemExit(main())`` guard calls the real CLI with the
real ``sys.argv``. ``--help`` is the probe because it is the one invocation every CLI
shares and it must succeed without touching models, keys or files.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# (module path, a line that must be present in --help output)
RUN_AS_FILE = [
    ("untell/scripts/voice.py", "untell-voice"),
    ("untell/scripts/latex.py", "untell-latex"),
    ("untell/scripts/entailment.py", "usage: entailment.py"),
    ("untell/scripts/roles.py", "usage: roles.py"),
    ("untell/scripts/tells.py", "untell-tells"),
    ("untell/scripts/verify.py", "untell-verify"),
    ("untell/scripts/audit.py", "untell-audit"),
    ("untell/scripts/explain.py", "untell-explain"),
    ("untell/humanness.py", "untell-humanness"),
]


@pytest.mark.parametrize(("rel", "needle"), RUN_AS_FILE, ids=[r[0].split("/")[-1] for r in RUN_AS_FILE])
def test_cli_runs_as_main_and_answers_help(rel: str, needle: str, capsys, monkeypatch) -> None:
    """Executing the file as __main__ (the documented bare-interpreter path) works."""
    script = REPO / rel
    assert script.is_file(), f"{script} moved?"
    monkeypatch.setattr(sys, "argv", ["prog", "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")
    assert exc.value.code == 0, f"{rel} --help exited {exc.value.code}"
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert needle in out, f"{rel} --help output did not contain {needle!r}:\n{out}"
