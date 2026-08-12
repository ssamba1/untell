"""Eighteen PASS lines are worth what their failure paths are worth.

`untell-audit` is what makes this repository's correctness argument checkable, and it reports
eighteen checks green. MEASURED by cross-referencing every `check_*` against the suite for a
known-negative — a test that constructs a failing input and asserts the check reports FAIL:

    has a known-negative test          2 of 18
    referenced from tests at all       6 of 18

Twelve were not mentioned anywhere in 4949 tests. That is the shape of the defect that once left
three regexes matching nothing across 2526 tests: **a check nobody has watched fail is a check nobody
has watched.**

So each check gets a mutation that breaks the thing it guards, applied to a real copy of the
repository, and has to report a failure. A mutation that does NOT trip its check is the finding — it
means the check cannot see the defect it is named for.

The copy is real rather than a fixture tree because these checks read real documents, real
`pyproject.toml`, real census data; a synthetic repo would prove something about the fixture.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

import pytest

import untell.scripts.audit as audit

IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", ".pytest_cache", "*.pyc", "node_modules", "htmlcov"
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def pristine(tmp_path_factory) -> Path:
    """One copy for the module. Copying per test costs minutes; each test restores what it edits."""
    dest = tmp_path_factory.mktemp("audit") / "repo"
    shutil.copytree(Path(audit.__file__).resolve().parent.parent.parent, dest, ignore=IGNORED)
    return dest


@pytest.fixture
def repo(pristine, monkeypatch) -> Path:
    monkeypatch.setattr(audit, "REPO", pristine)
    return pristine


def _restore(path: Path, original: bytes | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(original)


def run_check(name: str) -> audit.Report:
    report = audit.Report()
    getattr(audit, name)(report)
    return report


def assert_fails(name: str, note: str) -> None:
    report = run_check(name)
    assert report.failures, f"{name} passed after {note}: {[f.name for f in report.findings]}"


def assert_passes(name: str) -> None:
    """Guards the guard for every case below. If a check failed on the UNMUTATED copy, the
    corresponding mutation test would pass without the mutation doing anything."""
    report = run_check(name)
    assert not report.failures, [f"{f.name}: {f.detail}" for f in report.failures]


def mutate(path: Path, edit) -> None:
    """Apply `edit` to a file's text, asserting it actually changed something."""
    before = path.read_text(encoding="utf-8", errors="replace")
    after = edit(before)
    assert after != before, f"the mutation did not change {path.name}; the pattern has moved"
    path.write_text(after, encoding="utf-8")


# --- one mutation per check --------------------------------------------------------------------
#
# `check_derivable` and the missing-document path are covered by
# `test_the_audit_reports_a_document_it_could_not_read.py`; the rest are here.


def test_control_characters_without_git(repo) -> None:
    """The copy has no `.git`, so `git ls-files` lists nothing. This check used to scan zero files
    and report "clean" — MEASURED with a BEL byte in `docs/index.md` it never saw. Zero files
    inspected is an unperformed check, not a clean repository."""
    assert_fails("check_no_control_characters", "running where git lists no files")
    assert "nothing was scanned" in run_check("check_no_control_characters").failures[0].detail


def test_control_characters_with_a_real_file_list(repo, monkeypatch) -> None:
    """And given a file list, the scanner itself still has to see the byte."""
    victim = repo / "docs" / "index.md"
    original = victim.read_bytes()
    monkeypatch.setattr(audit, "_tracked_text_files", lambda: ["docs/index.md"])
    try:
        assert_passes("check_no_control_characters")
        victim.write_bytes(original + b"\x07 bell\n")
        assert_fails("check_no_control_characters", "adding a BEL byte to docs/index.md")
    finally:
        _restore(victim, original)


def test_shadowed_definition(repo) -> None:
    assert_passes("check_no_shadowed_definitions")
    victim = repo / "untell" / "layout.py"
    original = victim.read_bytes()
    try:
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\ndef restore_layout_lines():\n    pass\n",
            encoding="utf-8",
        )
        assert_fails("check_no_shadowed_definitions", "redefining restore_layout_lines")
    finally:
        _restore(victim, original)


def test_dead_function(repo) -> None:
    assert_passes("check_no_dead_functions")
    victim = repo / "untell" / "layout.py"
    original = victim.read_bytes()
    # Assembled at runtime. Spelled out literally, the name appears in THIS file, `tests/` is part
    # of the corpus the check searches, and it correctly reported the function as referenced — the
    # probe had put its own subject into the haystack.
    name = "_never" + "_called" + "_from_anywhere"
    try:
        victim.write_text(
            victim.read_text(encoding="utf-8") + f"\n\ndef {name}():\n    return 1\n",
            encoding="utf-8",
        )
        assert_fails("check_no_dead_functions", "adding an unreferenced function")
    finally:
        _restore(victim, original)


def test_version_consistency(repo) -> None:
    assert_passes("check_version_consistency")
    victim = repo / "pyproject.toml"
    original = victim.read_bytes()
    try:
        mutate(victim, lambda t: re.sub(r'(?m)^version = "[^"]+"', 'version = "99.99.99"', t, count=1))
        assert_fails("check_version_consistency", "changing the version in pyproject.toml only")
    finally:
        _restore(victim, original)


def test_optional_extras(repo) -> None:
    assert_passes("check_optional_extras")
    victim = repo / "README.md"
    original = victim.read_bytes()
    try:
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\npip install untell[nosuchextra]\n",
            encoding="utf-8",
        )
        assert_fails("check_optional_extras", "advertising an extra that does not exist")
    finally:
        _restore(victim, original)


def test_test_inventory(repo) -> None:
    assert_passes("check_test_inventory")
    victim = repo / "docs" / "why-best-open-repo.md"
    original = victim.read_bytes()
    try:
        # The check's own pattern, not a guess at one. The document says "180 modules", and a first
        # attempt matching "N test modules" changed nothing — `\s+` in the real pattern spans the
        # optional word and a line break, and a literal space does not.
        mutate(victim, lambda t: re.sub(r"\d+(\s+test)?\s+modules\b", "3 modules", t, count=1))
        assert_fails("check_test_inventory", "claiming 3 test modules")
    finally:
        _restore(victim, original)


def test_test_count_claims(repo) -> None:
    assert_passes("check_test_count_claims")
    victim = repo / "docs" / "why-best-open-repo.md"
    original = victim.read_bytes()
    try:
        # The check matches `(\d{3,5})\s+tests`, and this document carries no such phrase at all —
        # the first mutation rewrote a pattern that was not there and changed nothing.
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\nThe suite is 100 tests.\n", encoding="utf-8"
        )
        assert_fails("check_test_count_claims", "claiming 100 tests")
    finally:
        _restore(victim, original)


def test_skill_commands(repo) -> None:
    assert_passes("check_skill_commands")
    skill = next(repo.rglob("SKILL.md"))
    original = skill.read_bytes()
    try:
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\n\nRun `untell-nosuchcommand --now`.\n",
            encoding="utf-8",
        )
        assert_fails("check_skill_commands", "telling Claude to run a command that does not exist")
    finally:
        _restore(skill, original)


def test_dynamic_env_vars(repo) -> None:
    assert_passes("check_dynamic_env_vars")
    # This check covers only the family `untell/config.py` BUILDS as f"UNTELL_{key.upper()}" — the
    # blind spot it was written for. A free-standing `os.environ.get` literal is outside its scope
    # (the first mutation added one and it rightly passed), and so is `UNTELL_API_KEY`, which is
    # written out in the source and caught by the literal scanner instead.
    victim = repo / "README.md"
    original = victim.read_bytes()
    try:
        mutate(victim, lambda t: t.replace("`UNTELL_TIER`", "`UNTELL_RENAMED_AWAY`", 1))
        assert_fails("check_dynamic_env_vars", "undocumenting the constructed UNTELL_TIER")
    finally:
        _restore(victim, original)


def test_demo_privacy_claims(repo) -> None:
    assert_passes("check_demo_privacy_claims")
    victim = repo / "docs" / "index.md"
    original = victim.read_bytes()
    try:
        assert "fetch(" in (repo / "docs" / "demo.html").read_text(
            encoding="utf-8", errors="replace"
        ), "premise: the demo must actually POST, or this check has nothing to contradict"
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\nYour text is never uploaded.\n",
            encoding="utf-8",
        )
        assert_fails("check_demo_privacy_claims", "claiming text is never uploaded")
    finally:
        _restore(victim, original)


def test_corpus_bound_claims(repo) -> None:
    assert_passes("check_corpus_bound_claims")
    victim = repo / "docs" / "index.md"
    original = victim.read_bytes()
    phrase = audit._CORPUS_BOUND_CLAIMS[0][0]
    try:
        victim.write_text(
            victim.read_text(encoding="utf-8") + f"\n\nuntell {phrase}.\n", encoding="utf-8"
        )
        assert_fails("check_corpus_bound_claims", f"stating {phrase!r} with no corpus named")
    finally:
        _restore(victim, original)


def test_attribution(repo) -> None:
    """The failure this repo has already shipped: a number with nowhere it came from."""
    report = audit.Report()
    audit.check_attribution(report)
    assert not report.unattributed, report.unattributed[:3]
    victim = repo / "docs" / "index.md"
    original = victim.read_bytes()
    try:
        # BOLD, and padded clear of the ±12-line attribution window. A plain "87.3%" is invisible
        # to this check by design — it looks for the emphasised headline numbers, which are the
        # ones a reader takes away.
        filler = "\n".join("Padding so no nearby line carries a source." for _ in range(14))
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + f"\n\n## Results\n\n{filler}\n\n**87.3%** of flagged documents are cleared.\n"
            + f"\n{filler}\n",
            encoding="utf-8",
        )
        after = audit.Report()
        audit.check_attribution(after)
        assert after.unattributed, "an unsourced 87.3% went unreported"
    finally:
        _restore(victim, original)


def test_unreleased_changelog_is_current(repo) -> None:
    assert_passes("check_unreleased_changelog_is_current")
    victim = repo / "CHANGELOG.md"
    original = victim.read_bytes()
    try:
        # The check compares the shipped caveat's own numbers against the Unreleased section, and
        # only once that section talks about "corpus means" — an arbitrary invented value is not
        # its subject, and a first mutation adding "AUROC 0.123" passed for that reason.
        mutate(
            victim,
            lambda t: t.replace(
                "## [Unreleased]",
                "## [Unreleased]\n\n- Rewrote the corpus means note; the bar is 9 words.",
                1,
            ),
        )
        assert_fails(
            "check_unreleased_changelog_is_current",
            "describing the corpus means with numbers the caveat does not carry",
        )
    finally:
        _restore(victim, original)


def test_selection_does_not_read_a_bare_max(repo) -> None:
    assert_passes("check_selection_does_not_read_a_bare_max")
    victim = repo / "untell" / "scripts" / "run.py"
    original = victim.read_bytes()
    try:
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + '\n\ndef _pick(cand, best):\n    return cand["max"] < best["max"]\n',
            encoding="utf-8",
        )
        assert_fails("check_selection_does_not_read_a_bare_max", "comparing bare max values")
    finally:
        _restore(victim, original)
