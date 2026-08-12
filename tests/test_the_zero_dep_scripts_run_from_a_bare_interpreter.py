"""The run-as-file bootstrap must come before the package imports, or it is unreachable.

Three entry points had it below::

    from untell.detectors.base import ...      # raises ModuleNotFoundError here
    if __package__ in (None, ""):              # never reached
        ... put the package root on sys.path

so `python .../untell/scripts/score.py` on a machine without untell installed died with
`ModuleNotFoundError: No module named 'untell'` — the zero-dependency path the README leads with
and the skill installer creates.

Every developer machine hides this. An editable install puts `untell` on sys.path, so the import
succeeds and the dead bootstrap is invisible; the same command in a venv passes. It showed up only
on CI's Linux and Windows installer jobs, which run a bare interpreter, and it had been failing
there for hours across commits from more than one session.

This file checks the ORDER statically rather than spawning interpreters: it is the property that
broke, it holds for every script at once, and it costs nothing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = '__package__ in (None, ""'


def _scripts_with_bootstrap() -> list[Path]:
    found = []
    for path in sorted(REPO.glob("untell/**/*.py")):
        if BOOTSTRAP in path.read_text(encoding="utf-8"):
            found.append(path)
    return found


def test_some_scripts_carry_the_bootstrap():
    """Guards the guard: if the pattern were renamed, the sweep below would test nothing."""
    assert len(_scripts_with_bootstrap()) >= 5


@pytest.mark.parametrize("path", _scripts_with_bootstrap(), ids=lambda p: p.name)
def test_the_bootstrap_precedes_every_untell_import(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()

    bootstrap_at = next(i for i, line in enumerate(lines) if BOOTSTRAP in line)
    imports_at = [
        i
        for i, line in enumerate(lines)
        if line.startswith(("from untell.", "from untell ", "import untell"))
    ]
    if not imports_at:
        pytest.skip(f"{path.name} imports nothing from the package")

    first = min(imports_at)
    assert bootstrap_at < first, (
        f"{path.relative_to(REPO)} runs `{lines[first].strip()}` on line {first + 1} before the "
        f"sys.path bootstrap on line {bootstrap_at + 1}. The import raises ModuleNotFoundError "
        "first, so the bootstrap is unreachable and the file cannot run from a bare interpreter — "
        "which is the zero-dependency path the skill installer creates."
    )
