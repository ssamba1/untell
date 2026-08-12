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


# Files SKILL.md tells Claude to run BY PATH. On the zero-dependency tier nothing is installed, so
# each one is executed by a bare interpreter and needs the bootstrap to import its own package.
#
# The first version of this file checked only the ORDER, among files that already had a bootstrap.
# That silently exempted every file with no bootstrap at all — and three of them, preserve.py,
# quality.py and entailment.py, died with ModuleNotFoundError when run that way. A sweep whose
# membership test is "already does the thing" cannot find anything that does not.
_SKILL = (REPO / "untell" / "SKILL.md").read_text(encoding="utf-8")
SKILL_SCRIPTS = sorted(
    {
        name
        for name in (
            line.split("scripts/", 1)[1].split(".py", 1)[0] + ".py"
            for line in _SKILL.splitlines()
            if "scripts/" in line and ".py" in line.split("scripts/", 1)[1]
        )
        if (REPO / "untell" / "scripts" / name).exists()
    }
)


def test_the_skill_references_scripts_by_path():
    """If SKILL.md stopped naming scripts, the sweep below would silently cover nothing."""
    assert len(SKILL_SCRIPTS) >= 8, SKILL_SCRIPTS


@pytest.mark.parametrize("name", SKILL_SCRIPTS)
def test_every_script_the_skill_runs_can_import_its_own_package(name: str):
    path = REPO / "untell" / "scripts" / name
    source = path.read_text(encoding="utf-8")
    if not any(
        line.startswith(("from untell.", "from untell ", "import untell"))
        for line in source.splitlines()
    ):
        pytest.skip(f"{name} imports nothing from the package, so it needs no bootstrap")

    assert BOOTSTRAP in source, (
        f"SKILL.md tells Claude to run untell/scripts/{name} by path, and on the zero-dependency "
        "tier that is a bare interpreter with nothing installed. Without the sys.path bootstrap "
        "the file dies on its first `from untell...` import."
    )


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
