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
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
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


def _ignored_but_tracked() -> list[str]:
    """Tracked paths that git itself considers ignored.

    `--no-index` is the whole point: without it `git check-ignore` reports nothing for a tracked
    file, because tracking wins over the ignore rules — which is the very situation being hunted.
    """
    out = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=REPO, input="\n".join(TRACKED), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    # Exit 0 = some path matched, 1 = none matched, anything else is a real failure.
    assert out.returncode in (0, 1), f"git check-ignore failed: {out.stderr.strip()}"
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def test_nothing_is_tracked_from_an_ignored_directory():
    """A file already tracked stays tracked even after its directory is gitignored, so the ignore
    rule silently does nothing. This is how `.venv` or a scratch directory quietly persists.

    ASKS GIT, rather than re-deriving the ignore rules from a hand-written list of directories.
    The list version flagged all thirty files under `eval/data/` — every one of which git considers
    perfectly tracked, because `.gitignore` ignores `data/` and then un-ignores `!eval/data/` on the
    very next rule. A prefix match cannot see a negation.

    That is not a hypothetical drift. `.gitignore` carries a comment at that exact line recording
    that `data/` swallowing `eval/data/` already cost this repository EIGHT ROUNDS of documenting
    files as committed while none was tracked. The list-based check then reproduced the same
    misreading from the other side, and its own docstring had promised the list "must contain
    exactly what `.gitignore` actually ignores" — a promise nothing enforced, about a file that had
    already changed underneath it.

    `git check-ignore` implements the real semantics, including negations, precedence and the
    per-directory `.gitignore` files a prefix list cannot know about.
    """
    assert not _ignored_but_tracked(), (
        f"tracked despite being ignored: {_ignored_but_tracked()}")


def test_the_ignore_check_can_actually_find_an_offender(tmp_path):
    """Positive control. A check that consults git and misreads its exit code, or passes an empty
    list, reports a clean repository forever — which is what the assertion above would look like if
    it were broken."""
    scratch = tmp_path / "repo"
    (scratch / "site").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=scratch, check=True, timeout=60)
    (scratch / ".gitignore").write_text("site/\n", encoding="utf-8")
    (scratch / "site" / "index.html").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "site/index.html", ".gitignore"],
                   cwd=scratch, check=True, timeout=60)

    tracked = subprocess.run(["git", "ls-files"], cwd=scratch, capture_output=True,
                             text=True, timeout=60).stdout.split()
    found = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"], cwd=scratch,
        input="\n".join(tracked), capture_output=True, text=True, timeout=60)
    assert "site/index.html" in found.stdout, (
        "a force-added file under an ignored directory must be reported")


def test_a_negated_rule_is_not_reported_as_ignored(tmp_path):
    """The other half, and the case the old list got wrong.

    Shaped exactly like the real `.gitignore`: `data/` matches the DIRECTORY `eval/data`, and
    `!eval/data/` un-excludes that same directory. A first draft of this fixture used `data/` then
    `!data/keep/`, which does not work at all — git cannot re-include a path whose parent directory
    is excluded, and `.gitignore`'s own comment says so. The negation has to lift the exclusion off
    the directory that was excluded, not off something beneath it.
    """
    scratch = tmp_path / "repo"
    (scratch / "eval" / "data").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=scratch, check=True, timeout=60)
    (scratch / ".gitignore").write_text("data/\n!eval/data/\n", encoding="utf-8")
    (scratch / "eval" / "data" / "evidence.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "eval/data/evidence.json", ".gitignore"],
                   cwd=scratch, check=True, timeout=60)

    tracked = subprocess.run(["git", "ls-files"], cwd=scratch, capture_output=True,
                             text=True, timeout=60).stdout.split()
    found = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"], cwd=scratch,
        input="\n".join(tracked), capture_output=True, text=True, timeout=60)
    assert "evidence.json" not in found.stdout, (
        "a path re-included by a negation is not ignored, and flagging it is how thirty files of "
        "committed evidence got reported as debris")


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
