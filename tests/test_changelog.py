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
