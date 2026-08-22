"""What ships in the wheel, checked without building one.

A data file added under ``untell/`` that nobody adds to ``[tool.setuptools.package-data]`` is
invisible until a user installs from PyPI and the code that reads it raises FileNotFoundError. The
repo checkout always works, because the file is right there — which is exactly why this class of
bug reaches users.

Building a wheel here would be the direct check and takes long enough to make the suite annoying,
so these compare the declaration against the tracked tree instead. A real wheel was built and
installed into a clean virtualenv by hand (2026-08-09): 83 entries, all four declared data files
present, ``import untell`` and ``score_tells`` working.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = (REPO / "pyproject.toml").read_text(encoding="utf-8")


def _tracked(prefix: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", prefix], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _package_data_globs() -> list[str]:
    block = PYPROJECT[PYPROJECT.index("[tool.setuptools.package-data]") :]
    end = block.find("\n[", 1)
    if end != -1:
        block = block[:end]
    return re.findall(r'"([^"]+)"', block)


def test_every_tracked_data_file_under_untell_is_declared() -> None:
    """The check that would have caught SKILL.md or a reference doc silently not shipping."""
    globs = _package_data_globs()
    undeclared = []
    for path in _tracked("untell"):
        if path.endswith(".py"):
            continue
        rel = path[len("untell/") :]
        if not any(Path(rel).match(g) for g in globs):
            undeclared.append(rel)
    assert not undeclared, (
        f"tracked under untell/ but not in [tool.setuptools.package-data]: {undeclared}. "
        f"These exist in a checkout and vanish in a wheel. Declared globs: {globs}"
    )


def test_there_are_data_files_to_check() -> None:
    """Guards the guard: if the tracked-file query broke, the test above passes on nothing."""
    data = [p for p in _tracked("untell") if not p.endswith(".py")]
    assert len(data) >= 4, f"expected several data files under untell/, found {data}"


def test_declared_globs_all_match_something() -> None:
    """A glob matching nothing is either a typo or a file that was deleted without updating this."""
    tracked = [p[len("untell/") :] for p in _tracked("untell") if not p.endswith(".py")]
    for glob in _package_data_globs():
        assert any(Path(p).match(glob) for p in tracked), (
            f"package-data glob {glob!r} matches no tracked file"
        )


def _declared_scripts() -> dict[str, str]:
    block = PYPROJECT[PYPROJECT.index("[project.scripts]") :]
    end = block.find("\n[", 1)
    return dict(
        re.findall(r'^([\w-]+)\s*=\s*"([^"]+)"', block[:end] if end != -1 else block, re.M)
    )


def test_every_console_script_resolves_to_a_callable() -> None:
    """The companion to the test below, which is textual and cannot see this.

    That one checks the module NAME sits inside a declared package. It passes for
    ``untell-voice = "untell.scripts.voice:main"`` after ``main`` is renamed, after the module stops
    importing, and after the attribute becomes a constant — every one of which installs fine and
    then fails the first time a user types the command.

    Importing all 23 is cheap here because the suite has already imported most of the package.
    """
    import importlib

    broken: list[str] = []
    for name, target in sorted(_declared_scripts().items()):
        module, _, attribute = target.partition(":")
        try:
            resolved = importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - the failure mode IS "any import error"
            broken.append(f"{name} -> {target}: import failed, {type(exc).__name__}: {exc}")
            continue
        if not hasattr(resolved, attribute):
            broken.append(f"{name} -> {target}: module has no attribute {attribute!r}")
        elif not callable(getattr(resolved, attribute)):
            broken.append(f"{name} -> {target}: {attribute!r} is not callable")
    assert not broken, "console scripts that would fail at the shell:\n  " + "\n  ".join(broken)


def test_the_script_scan_finds_them_all() -> None:
    """Guards the guard: a parse that returns {} makes the check above vacuous."""
    scripts = _declared_scripts()
    assert len(scripts) >= 20, f"only {len(scripts)} console scripts parsed out of pyproject"
    assert "untell" in scripts and "untell-audit" in scripts


def test_every_console_script_points_into_a_declared_package() -> None:
    """A script whose module lives outside ``packages`` installs and then fails on import.

    This is how ``eval`` and ``training`` came to be shipped as top-level packages: seven console
    scripts point into them, so they have to be declared, so a ``pip install untell`` claims both
    names in site-packages. See ROADMAP — that is a real problem and fixing it is a breaking
    change, so what this test does is make sure the situation stays *coherent* rather than
    silently growing a script that resolves to nothing.
    """
    block = PYPROJECT[PYPROJECT.index("[project.scripts]") :]
    end = block.find("\n[", 1)
    scripts = dict(re.findall(r'^([\w-]+)\s*=\s*"([^"]+)"', block[:end] if end != -1 else block, re.M))

    pkg_block = PYPROJECT[PYPROJECT.index("[tool.setuptools]") :]
    pkg_block = pkg_block[: pkg_block.index("[tool.setuptools.package-data]")]
    packages = set(re.findall(r'"([\w.]+)"', pkg_block))

    orphans = []
    for name, target in scripts.items():
        module = target.split(":")[0]
        if not any(module == p or module.startswith(p + ".") for p in packages):
            orphans.append(f"{name} -> {module}")
    assert not orphans, f"console scripts outside every declared package: {orphans}"
