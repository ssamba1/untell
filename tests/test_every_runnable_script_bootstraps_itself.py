"""A script run as a file has only its own directory on sys.path.

`python .../untell/scripts/score.py` cannot `import untell` unless a bootstrap first puts the
directory CONTAINING the package on sys.path. Six scripts once had that bootstrap below their
package imports, where it is unreachable code — the import raises `ModuleNotFoundError` first — and
that is exactly the path the skill installer creates and the README leads with.

An editable install hides it completely, on every developer machine and in this test suite, which is
why it survived to CI. It cannot be reproduced here either: `untell` is importable on every
interpreter on this box. So the property is decided statically, which is what the defect actually
is — does the bootstrap appear before the first `untell` import?

CI runs exactly ONE script this way (`score.py`). There are 16 runnable scripts.

FOUND by widening from the 12 SKILL.md names to all 16: `audit.py` had no bootstrap at all. It was
missed because its untell imports are all LAZY, inside the check functions rather than at module
level, so nothing failed at import time and its shape did not resemble the six that were fixed. It
failed later instead, on the first check that needed the package — a worse place to find out.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "untell" / "scripts"


def _runnable() -> list[pathlib.Path]:
    return sorted(
        p for p in _SCRIPTS.glob("*.py")
        if p.stem != "__init__" and "__main__" in p.read_text(encoding="utf-8")
    )


def _first_package_import_line(tree: ast.AST) -> int | None:
    """Line of the earliest import that needs the package on sys.path.

    Relative imports count. An earlier version of this check looked only for a module name starting
    with `untell`, which misses `from ..layout import x` entirely — that has module="layout" and
    level=2, and needs the bootstrap just as much.
    """
    best: int | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        module = node.module if isinstance(node, ast.ImportFrom) else None
        names = [alias.name for alias in node.names]
        level = getattr(node, "level", 0) or 0
        if (module or "").startswith("untell") or any(n.startswith("untell") for n in names) or level:
            if best is None or node.lineno < best:
                best = node.lineno
    return best


def _bootstrap_line(tree: ast.AST) -> int | None:
    best: int | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "__package__" in ast.unparse(node.test):
            if best is None or node.lineno < best:
                best = node.lineno
    return best


@pytest.mark.parametrize("path", _runnable(), ids=lambda p: p.stem)
def test_the_bootstrap_runs_before_the_first_package_import(path: pathlib.Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    first_import = _first_package_import_line(tree)
    if first_import is None:
        return  # genuinely standalone: hedges, latex, roles import nothing from the package
    bootstrap = _bootstrap_line(tree)

    assert bootstrap is not None, (
        f"{path.name} imports the package but has no `if __package__ in (None, ''):` bootstrap, so "
        f"`python .../{path.name}` fails on a zero-dependency install. Note a LAZY import inside a "
        f"function still needs it — it fails when the function runs instead of at import time."
    )
    assert bootstrap < first_import, (
        f"{path.name}: bootstrap at line {bootstrap} is BELOW the first package import at line "
        f"{first_import}, so it is unreachable — the import raises ModuleNotFoundError first"
    )


def test_the_scan_finds_the_scripts_it_is_supposed_to() -> None:
    """Guards the guard. A glob that stopped matching, or a `__main__` filter that excluded
    everything, would make every case above pass while checking nothing."""
    found = {p.stem for p in _runnable()}
    assert len(found) >= 12, f"only {len(found)} runnable scripts found: {sorted(found)}"
    for expected in ("score", "tells", "run", "audit", "cli"):
        assert expected in found, f"{expected}.py is runnable but was not scanned"


def test_at_least_one_script_actually_needs_the_bootstrap() -> None:
    """If nothing imported the package, every case would pass vacuously via the early return."""
    needing = [
        p.stem for p in _runnable()
        if _first_package_import_line(ast.parse(p.read_text(encoding="utf-8"))) is not None
    ]
    assert len(needing) >= 8, f"only {len(needing)} scripts import the package: {needing}"


def test_relative_imports_are_recognised_as_needing_the_bootstrap() -> None:
    """The blind spot in the first version of this check, pinned so it cannot come back."""
    tree = ast.parse("from ..layout import apply_per_block\n")
    assert _first_package_import_line(tree) == 1
