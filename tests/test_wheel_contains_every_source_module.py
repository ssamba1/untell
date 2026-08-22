"""Every .py in the shipped packages must be in the built wheel.

The defect this guards: ``untell/inspect_report.py`` was added after the
``untell.egg-info/SOURCES.txt`` cache was last generated.  setuptools reads
the existing SOURCES.txt and, when the cache is stale, silently skips the new
file.  The result is a wheel where ``untell.inspect_report`` is missing but
``run.py`` imports it on the ``--inspect`` path — a ``ModuleNotFoundError``
that only surfaces at runtime.

The fix is to delete ``untell.egg-info/`` before building (the directory is
already in ``.gitignore``; it must not be committed).  This test catches any
future recurrence WITHOUT building the wheel itself — it reads the source tree
directly and compares it against the declared packages list in pyproject.toml,
so it runs instantly in CI.

What this checks:
  - Every .py file under each declared package directory is discoverable
    (no file silently locked out by a stale SOURCES.txt)
  - The documented package-data files are present on disk
    (SKILL.md, references/*.md)
  - untell.egg-info/ is NOT committed to the repo (it would go stale again)
"""
from __future__ import annotations

import pathlib
import re
import zipfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = (REPO / "pyproject.toml").read_text(encoding="utf-8")

# Extract ONLY the packages list from [tool.setuptools], stopping at the next [section].
# A naive slice from "[tool.setuptools]" to EOF also captures [tool.pytest.ini_options] whose
# ``markers`` list looks identical — "slow: ..." in a quoted string on its own line.
def _extract_packages(toml_text: str) -> list[str]:
    # Find the [tool.setuptools] section and cut it off at the next TOML section header.
    start = toml_text.index("[tool.setuptools]")
    rest = toml_text[start:]
    next_section = re.search(r"^\[(?!tool\.setuptools\])", rest, re.M)
    section = rest[: next_section.start()] if next_section else rest
    return re.findall(r'^\s*"([^"]+)"\s*,?$', section, re.M)


DECLARED_PACKAGES: list[str] = _extract_packages(PYPROJECT)


@pytest.fixture(scope="module")
def all_source_py_files() -> set[str]:
    """All .py files under declared package directories, relative to repo root."""
    result: set[str] = set()
    for pkg in DECLARED_PACKAGES:
        pkg_dir = REPO / pkg.replace(".", "/")
        if pkg_dir.is_dir():
            for f in pkg_dir.rglob("*.py"):
                result.add(str(f.relative_to(REPO)).replace("\\", "/"))
    return result


# ---------------------------------------------------------------------------
# 1. Every declared package directory exists.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg", DECLARED_PACKAGES)
def test_declared_package_directory_exists(pkg: str) -> None:
    pkg_dir = REPO / pkg.replace(".", "/")
    assert pkg_dir.is_dir(), (
        f"Package '{pkg}' is declared in pyproject.toml but the directory "
        f"'{pkg_dir}' does not exist; pip install will fail"
    )


# ---------------------------------------------------------------------------
# 2. Package-data files are present on disk.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rel", [
    "untell/SKILL.md",
    "untell/references/ai-tells.md",
    "untell/references/prompt-rubric.md",
    "untell/references/thresholds.md",
])
def test_documented_package_data_exists_on_disk(rel: str) -> None:
    assert (REPO / rel).is_file(), (
        f"{rel} is declared as package-data in pyproject.toml but the file is missing from disk"
    )


# ---------------------------------------------------------------------------
# 3. No stale egg-info is committed (or present as a build artifact that
#    would cause setuptools to skip newly-added files).
# ---------------------------------------------------------------------------


def test_egg_info_is_not_committed_to_git() -> None:
    """A committed SOURCES.txt goes stale the first time a new .py file is added."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "untell.egg-info/"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=REPO,
    )
    tracked = result.stdout.strip()
    assert not tracked, (
        "untell.egg-info/ is tracked by git; when SOURCES.txt goes stale it silently "
        "excludes new .py files from the wheel.  Remove it from git: "
        f"git rm -r --cached untell.egg-info/\n  Found: {tracked[:200]}"
    )


def test_egg_info_sources_txt_is_not_stale() -> None:
    """If a local egg-info exists, its SOURCES.txt must list every package .py.

    This is the fastest way to catch the bug before a build: the local SOURCES.txt
    must not be missing any file that currently sits in a declared package dir.
    If SOURCES.txt is absent (egg-info was deleted, as it should be), the test
    passes trivially — there is nothing stale to complain about.
    """
    sources_txt = REPO / "untell.egg-info" / "SOURCES.txt"
    if not sources_txt.exists():
        return  # clean state — no stale cache to complain about

    recorded = set(sources_txt.read_text(encoding="utf-8").splitlines())
    # Only check files under the declared source packages.
    for pkg in DECLARED_PACKAGES:
        pkg_dir = REPO / pkg.replace(".", "/")
        if not pkg_dir.is_dir():
            continue
        for f in pkg_dir.rglob("*.py"):
            rel = str(f.relative_to(REPO)).replace("\\", "/")
            assert rel in recorded, (
                f"{rel} exists in the source tree but is absent from "
                f"untell.egg-info/SOURCES.txt; delete the egg-info directory before "
                f"building to force a fresh manifest: rm -rf untell.egg-info/"
            )


# ---------------------------------------------------------------------------
# 4. If a built wheel is present in dist/, it must contain every source module.
#    (This is a post-build sanity check, not a substitute for building.)
# ---------------------------------------------------------------------------


def _latest_wheel() -> pathlib.Path | None:
    """Return the most-recently-modified wheel in dist/, or None."""
    wheels = sorted((REPO / "dist").glob("untell-*.whl"), key=lambda p: p.stat().st_mtime)
    return wheels[-1] if wheels else None


def test_built_wheel_contains_every_source_module(all_source_py_files) -> None:
    """Every .py under a declared package must be in the wheel.

    Skipped when no wheel exists in dist/ (CI build step hasn't run yet).
    Run ``python -m build --wheel`` first to exercise the full check.
    """
    wheel_path = _latest_wheel()
    if wheel_path is None:
        pytest.skip("no wheel found in dist/ — run python -m build --wheel first")

    with zipfile.ZipFile(wheel_path) as whl:
        wheel_names = set(whl.namelist())

    missing = []
    for src_rel in sorted(all_source_py_files):
        # Wheels use forward slashes.  dist-info entries use the wheel's own paths.
        if src_rel not in wheel_names:
            missing.append(src_rel)

    assert not missing, (
        f"The following source files are absent from {wheel_path.name}:\n"
        + "\n".join(f"  {m}" for m in missing)
        + "\n\nRoot cause: stale untell.egg-info/SOURCES.txt.  Fix: delete it before "
        + "building: rm -rf untell.egg-info/ && python -m build --wheel"
    )
