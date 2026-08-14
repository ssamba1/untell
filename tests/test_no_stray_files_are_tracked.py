"""Nothing that is captured output, scratch, or a mangled path may be tracked.

Fourteen log files were committed to the repository root across five commits before anyone
noticed. The cause was a shell redirect: `> "$T/scratchpad/name_err.log"` where `$T` held a
Windows path with backslashes, which bash takes literally — so instead of writing into the
scratchpad it created one file named `C:UsersAdmin...scratchpadname_err.log` in the repo root,
and the `git add -A` in each commit swept it in.

Every individual step was reasonable and the result was fourteen junk files in a published
repository. That is the shape of mistake a test catches and review does not: nothing was wrong
with any diff line, only with a filename nobody read.

Deliberately checks `git ls-files` rather than the working tree. An ignored file sitting on disk is
fine; a tracked one is the failure.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, timeout=120
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


TRACKED = _tracked()


def test_there_are_tracked_files_to_check():
    """Guards the guard: if `git ls-files` fails, every assertion below passes on an empty list."""
    assert len(TRACKED) >= 100, f"only {len(TRACKED)} tracked files found — is this a git repo?"


def test_no_captured_output_is_tracked():
    """The exact class that got in. A `.log` is never source."""
    offenders = [f for f in TRACKED if f.lower().endswith((".log", ".out", ".err"))]
    assert not offenders, f"captured output is tracked: {offenders}"


def test_no_filename_contains_a_windows_path():
    """`C:UsersAdmin...` as a *filename* means a redirect resolved wrong. It cannot be intentional
    on any platform, and on Linux it is a legal filename, so nothing else complains."""
    offenders = [f for f in TRACKED if "\\" in f or re.match(r"^[A-Za-z]:", f)]
    assert not offenders, f"filenames containing a Windows path: {offenders}"


def test_no_editor_or_tooling_debris_is_tracked():
    offenders = [
        f for f in TRACKED
        if f.endswith((".bak", ".orig", ".rej", ".swp", ".swo", "~", ".pyc", ".pyo"))
        or "/__pycache__/" in f
        or f.startswith("__pycache__/")
    ]
    assert not offenders, f"editor or build debris is tracked: {offenders}"


def test_nothing_is_tracked_from_an_ignored_directory():
    """A file already tracked stays tracked even after its directory is gitignored, so the ignore
    rule silently does nothing. This is how `.venv` or a scratch directory quietly persists.

    `.claude/` is deliberately NOT in this list: the audit loop files (audit-log.md, corpus.py,
    the ps1 fleet runners, the hc3 corpora) are tracked on purpose, with real commit history, and
    `.gitignore` ignores only three subdirectories of it (worktrees/, tasks/, records/). The list
    below must contain exactly what `.gitignore` actually ignores.
    """
    ignored_dirs = (".venv/", ".venv_test/", "build/", "dist/", "out/", "data/",
                    "models/", ".pytest_cache/", "site/")
    offenders = [f for f in TRACKED if any(f.startswith(d) or f"/{d}" in f for d in ignored_dirs)]
    assert not offenders, f"tracked despite being in an ignored directory: {offenders}"


@pytest.mark.parametrize("pattern", [r"\.env$", r"\.pem$", r"\.key$", r"_rsa$", r"\.p12$"])
def test_no_credential_shaped_file_is_tracked(pattern):
    """`.env.example` is fine and must stay; `.env` is not. The distinction is the whole point, so
    the pattern is anchored at the end of the name."""
    offenders = [f for f in TRACKED if re.search(pattern, f)]
    assert not offenders, f"credential-shaped file tracked: {offenders}"


def test_the_repository_has_not_grown_a_huge_binary():
    """A large binary in git history cannot be removed without a rewrite, so the time to notice is
    before it lands. The one legitimate image here is ~80 KB."""
    oversized = []
    for name in TRACKED:
        path = REPO / name
        if path.exists() and path.stat().st_size > 1_000_000:
            oversized.append(f"{name} ({path.stat().st_size // 1024} KB)")
    assert not oversized, f"tracked files over 1 MB: {oversized}"
