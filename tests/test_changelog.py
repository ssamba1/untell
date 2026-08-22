"""The changelog is a document people read to decide whether to upgrade, so it rots in
ways prose review misses: a section appended a second time under the same release, a
bullet filed under the wrong heading, a continuation line whose opening ``- `` was lost
in a merge. Each of those had happened here at once — ``[Unreleased]`` carried seven
section headings where the format allows three, eight Added-items sat under ``Fixed``,
and one entry's first line was gone, leaving its body glued to the bullet above it.

These are all mechanically checkable, which is the only reason they are worth a test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

# Keep a Changelog 1.1.0. We do not use every one, but nothing outside this set is valid.
VALID_SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")


def _releases() -> dict[str, list[str]]:
    """Map each release heading to the section headings that appear under it."""
    releases: dict[str, list[str]] = {}
    current: str | None = None
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            releases[current] = []
        elif line.startswith("### ") and current is not None:
            releases[current].append(line[4:].strip())
    return releases


def test_changelog_exists_and_declares_its_format() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "keepachangelog.com" in text
    assert "## [Unreleased]" in text


def test_no_release_repeats_a_section_heading() -> None:
    """Two ``### Fixed`` blocks under one release means a reader stops at the first."""
    for release, sections in _releases().items():
        duplicates = {s for s in sections if sections.count(s) > 1}
        assert not duplicates, f"{release} repeats section(s): {sorted(duplicates)}"


def test_section_headings_are_from_the_standard_set() -> None:
    for release, sections in _releases().items():
        unknown = [s for s in sections if s not in VALID_SECTIONS]
        assert not unknown, f"{release} has non-standard section(s): {unknown}"


def test_every_release_has_at_least_one_section() -> None:
    for release, sections in _releases().items():
        assert sections, f"{release} has no entries"


def test_no_content_appears_before_the_first_section_of_a_release() -> None:
    """A bullet between ``## [x]`` and its first ``### y`` is an entry with no category —
    which is what a lost heading looks like."""
    orphans: list[str] = []
    in_release = False
    seen_section = False
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_release, seen_section = True, False
        elif line.startswith("### "):
            seen_section = True
        elif in_release and not seen_section and line.strip():
            orphans.append(line)
    assert not orphans, f"entries outside any section: {orphans[:3]}"


def test_continuation_lines_belong_to_a_bullet() -> None:
    """``- `` opens an entry and indented lines continue it. An unindented, non-bullet
    line inside a section is a bullet that lost its opening.

    Scope, honestly: this does not catch the lost-opening case that actually occurred
    here. That bullet's remaining lines were *indented*, so by every mechanical rule
    they are a valid continuation of the entry above — only reading the prose reveals
    that 'OpenAPI docs, API-key auth, CORS...' describes a different feature. Detecting
    that needs a judgement this file cannot make; what it catches is the unindented
    variant."""
    bad: list[tuple[int, str]] = []
    in_section = False
    for n, line in enumerate(CHANGELOG.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("### "):
            in_section = True
            continue
        if line.startswith("## "):
            in_section = False
            continue
        if not in_section or not line.strip():
            continue
        if not (line.startswith("- ") or line.startswith("  ")):
            bad.append((n, line[:70]))
    assert not bad, f"lines that are neither a bullet nor a continuation: {bad}"


def test_no_control_characters() -> None:
    """A NUL or other control byte turns the file 'binary' to grep, git diff and every
    rendering tool. One got in here by way of an escaped sentinel in a doc example."""
    raw = CHANGELOG.read_bytes()
    control = {b for b in raw if b < 0x20 and b not in (0x09, 0x0A, 0x0D)}
    assert not control, f"control bytes present: {sorted(hex(b) for b in control)}"


@pytest.mark.parametrize("marker", ["TODO", "FIXME", "XXX", "TBD", "???"])
def test_no_placeholders(marker: str) -> None:
    assert marker not in CHANGELOG.read_text(encoding="utf-8")


def test_unreleased_covers_the_shipped_headline() -> None:
    """The headline result is the first thing a reader checks. If the changelog does not
    mention the tools the README documents, it is stale — this is the cheapest possible
    check that someone updated it alongside the code."""
    text = CHANGELOG.read_text(encoding="utf-8")
    unreleased = text[text.index("## [Unreleased]") : text.index("## [0.1.0]")]
    for expected in ("untell-audit", "untell-latex"):
        assert expected in unreleased, f"{expected} ships but is not in the changelog"


def test_bullet_count_is_not_silently_shrinking() -> None:
    """A rebuild that drops entries is worse than a messy changelog. Pin a floor."""
    text = CHANGELOG.read_text(encoding="utf-8")
    bullets = re.findall(r"^- ", text, flags=re.MULTILINE)
    assert len(bullets) >= 70, f"only {len(bullets)} entries — did a rewrite lose some?"


def test_the_shipped_version_appears_in_the_changelog() -> None:
    """A user who installs 0.3.0 and opens CHANGELOG.md must find 0.3.0 in it.

    MEASURED at the time of writing: `pyproject`, `untell.__version__`, `plugin.json`,
    `marketplace.json` and `CITATION.cff` all said 0.3.0, and the changelog's newest heading was
    `[0.1.0]`. Neither 0.2.0 nor 0.3.0 appeared anywhere in the file, so two releases shipped with
    their notes still sitting under `[Unreleased]` — 91 bullets of them.

    The existing tests in this file all check the SHAPE of the changelog: standard section names,
    no duplicate headings, no orphaned entries. Every one of them passed. Nothing tied the file to
    the version actually being shipped, which is the thing a reader is checking it against.
    """
    import pathlib
    import re

    import tomllib

    version = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    text = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.M)
    assert version in headings, (
        f"version {version} ships but has no changelog heading; headings are {headings}. "
        f"Either release the notes under [Unreleased] as {version}, or the version was bumped "
        f"without recording what changed."
    )


def test_shipped_version_section_names_its_headline_features() -> None:
    """The section a reader lands on after installing must NAME the headline
    features of that release — not just exist as a heading.

    ``test_the_shipped_version_appears_in_the_changelog`` ties the heading to the
    version; this ties the CONTENT to the version. Each shipped version lists the
    features a reader of its notes is checking for. If the version is bumped and
    the new section does not name them, the changelog is stale in the way a
    reader actually meets it — the cheapest assertion that the file was updated
    alongside the release, mirroring ``test_unreleased_covers_the_shipped_headline``
    for the released side of the file.
    """
    import pathlib
    import re

    import tomllib

    version = tomllib.loads(
        pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    headline = {
        "0.3.0": ("untell humanness", "REST API server", "batch_score_texts", "untell-audit"),
    }
    text = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
    parts = re.split(r"^## \[", text, flags=re.M)
    section = next((p for p in parts if p.startswith(f"{version}]")), "")
    assert section, f"no changelog section for the shipped version {version}"
    missing = [f for f in headline.get(version, ()) if f not in section]
    assert not missing, (
        f"version {version}'s changelog section does not mention headline features: {missing}"
    )


def test_changelog_is_not_stale_relative_to_recent_user_visible_commits() -> None:
    """Fail when many user-visible commits have accumulated since CHANGELOG.md was last updated.

    Without this, the changelog can silently fall behind for hundreds of commits (issue #12
    found ~77 unrecorded user-visible changes since b37cb02). The threshold is intentionally
    low — 20 user-visible commits is enough to motivate updating before the backlog compounds.

    'User-visible' means any commit whose type prefix is feat, fix, or perf and whose scope is
    not one of the internal subsystems (test, lint, queue, survivors, research, docs, instruments,
    training). Audit-loop commits and doc-queue commits do not count; new commands, fixed crashes,
    and visible performance changes do.

    This test requires git; it skips gracefully when git is absent (e.g. in a source tarball).
    """
    import subprocess

    repo = Path(__file__).resolve().parent.parent

    try:
        last_cl = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "CHANGELOG.md"],
            text=True, encoding="utf-8", errors="replace",
            cwd=repo,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git unavailable")

    if not last_cl:
        pytest.skip("CHANGELOG.md has never been committed")

    try:
        log_lines = subprocess.check_output(
            ["git", "log", f"{last_cl}..HEAD", "--oneline", "--no-merges"],
            text=True, encoding="utf-8", errors="replace",
            cwd=repo,
            stderr=subprocess.DEVNULL,
        ).splitlines()
    except subprocess.CalledProcessError:
        pytest.skip("git log failed")

    _INTERNAL_SCOPE = re.compile(
        r"^\w+ (feat|fix|perf)\((test|lint|queue|survivors|research|docs|instruments|training)\)"
    )
    _USER_VISIBLE = re.compile(r"^\w+ (feat|fix|perf)(\(|\: )")

    user_visible = [
        line for line in log_lines
        if _USER_VISIBLE.match(line) and not _INTERNAL_SCOPE.match(line)
    ]

    _THRESHOLD = 20
    assert len(user_visible) <= _THRESHOLD, (
        f"CHANGELOG.md last updated at {last_cl[:8]}, but {len(user_visible)} user-visible "
        f"commits have accumulated since then (threshold {_THRESHOLD}). "
        f"Update CHANGELOG.md. First five: "
        + "; ".join(c[:60] for c in user_visible[:5])
    )


def test_unreleased_is_not_the_only_place_work_accumulates() -> None:
    """`[Unreleased]` growing without bound is how the above happens.

    Not a size limit for its own sake — a large Unreleased section is normal mid-cycle. It is a
    limit relative to the released history: if more has accumulated unreleased than every release
    combined, the file has stopped describing what people are running.
    """
    import pathlib
    import re

    text = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
    parts = re.split(r"^## \[", text, flags=re.M)
    unreleased = next((p for p in parts if p.startswith("Unreleased]")), "")
    released = [p for p in parts if p and not p.startswith("Unreleased]") and "]" in p[:20]]
    n_unreleased = unreleased.count("\n- ")
    n_released = sum(p.count("\n- ") for p in released)
    assert n_released, "no released section has any entries"
    assert n_unreleased <= n_released * 3, (
        f"[Unreleased] holds {n_unreleased} entries against {n_released} across every release. "
        f"Cut a release, or the changelog describes a version nobody has."
    )
