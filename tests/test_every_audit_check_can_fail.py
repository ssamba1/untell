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


def assert_drifts(name: str, note: str) -> None:
    """Assert a check reported COUNT DRIFT, which is deliberately not a failure.

    `2a64a7b` reclassified a stale published count from a structural failure to a DRIFT:
    `Report.drift` appends to `findings` and `count_drifts` but NOT to `failures`, because a
    number that has fallen behind the suite is a repair job (`untell-audit --fix-counts`) and
    not a broken invariant.

    That was the right call and it silently disarmed this file for the two count checks:
    `assert_fails` reads `failures`, so both mutations stopped proving anything, and the file
    whose entire purpose is 'every audit check CAN report a problem' stopped covering two of
    them. Asserting on the channel the check actually writes to restores that.
    """
    report = run_check(name)
    assert report.count_drifts, (
        f"{name} reported no drift after {note}: {[f.name for f in report.findings]}"
    )
    assert not report.failures, (
        f"{name} reported a FAILURE for a count drift, which 2a64a7b made non-fatal: "
        f"{[f.name for f in report.failures]}"
    )


def assert_passes(name: str) -> None:
    """Guards the guard for every case below. If a check failed on the UNMUTATED copy, the
    corresponding mutation test would pass without the mutation doing anything.

    Drift counts here too: a check already drifting before the mutation would make
    `assert_drifts` below vacuous in exactly the same way.
    """
    report = run_check(name)
    assert not report.failures, [f"{f.name}: {f.detail}" for f in report.failures]
    assert not report.count_drifts, (
        "already drifting before the mutation: "
        + str([f"{f.name}: {f.detail}" for f in report.count_drifts])
    )


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
        # DRIFT, not failure -- see `assert_drifts`. This assertion used to read `assert_fails`
        # and stopped proving anything the day count drift became non-fatal.
        assert_drifts("check_test_inventory", "claiming 3 test modules")
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
        assert_drifts("check_test_count_claims", "claiming 100 tests")
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


# --- the four checks that had no known-negative until round sixty-seven -------------------------
#
# This file's docstring records that twelve of eighteen checks were unmentioned anywhere in the
# suite, and it fixed them by hand. It never added the guard that keeps the NEXT check covered, so
# four had accumulated again by round sixty-seven. `test_every_check_has_a_known_negative` is that
# guard, and it is the durable half of this section.
#
# ✗ A first pass at counting them said five, including `check_attribution`. That was wrong: the
# collector looked for the check's name in quotes, and `test_attribution` above calls
# `audit.check_attribution(report)` directly. Searching for the bare name gives four.


def test_source_comment_counts(repo) -> None:
    """`run.py` states three times how many places `structural.py` draws from the global `random`
    module, and sizes the real fix by that number. Adding one draw site must be noticed."""
    assert_passes("check_source_comment_counts")
    victim = repo / "untell" / "rewriter" / "structural.py"
    original = victim.read_bytes()
    try:
        body = victim.read_text(encoding="utf-8")
        assert "random." in body, (
            "premise: structural.py must draw from `random`, or the count describes nothing")
        victim.write_text(body + "\n\n_PROBE = random.random\n", encoding="utf-8")
        assert_fails("check_source_comment_counts", "one more draw site than the comment claims")
    finally:
        _restore(victim, original)


CENSUS_DOC = "docs/humanizer-census.md"


def test_named_repo_stars(repo) -> None:
    """A star count quoted beside a repo name. These only move upward, so a stale one understates a
    competitor — the direction that flatters this project."""
    assert_passes("check_named_repo_stars")
    victim = repo / CENSUS_DOC
    original = victim.read_bytes()
    try:
        body = victim.read_text(encoding="utf-8")
        edited, count = re.subn(r"\d+(?:\.\d+)?k★", "999.9k★", body)
        assert count, "premise: the census page must quote a star count beside a repo"
        victim.write_text(edited, encoding="utf-8")
        assert_fails("check_named_repo_stars", "inflating every quoted star count")
    finally:
        _restore(victim, original)


def test_largest_repo_claims(repo) -> None:
    """"Three of the eight largest" is only worth printing if the repos named are in the top eight.
    Shrinking the claimed N leaves the exhibits outside it."""
    assert_passes("check_largest_repo_claims")
    # The exhibits this check reads are in `why-best-open-repo.md`, in the clause opened by "of the
    # eight largest" — not in the census page, which makes a similar-looking claim the check does
    # not reach. Two earlier mutations edited the census page and the check passed both times,
    # reporting the same three exhibits it had always seen: a mutation aimed at the wrong document
    # is indistinguishable from a check that cannot fail.
    victim = repo / "docs" / "why-best-open-repo.md"
    original = victim.read_bytes()
    try:
        body = victim.read_text(encoding="utf-8")
        # 191 stars, around rank 39, substituted for an exhibit named among the eight largest.
        edited, count = re.subn(r"`op7418/Humanizer-zh` \(14\.7k★",
                                "`ilyautov/humanizer-ru` (0.2k★", body)
        assert count, "premise: that page must name an exhibit among the eight largest"
        victim.write_text(edited, encoding="utf-8")
        assert_fails("check_largest_repo_claims", "narrowing the claimed rank below the exhibits")
    finally:
        _restore(victim, original)


def test_census_counts(repo) -> None:
    assert_passes("check_census_counts")
    victim = repo / CENSUS_DOC
    original = victim.read_bytes()
    try:
        body = victim.read_text(encoding="utf-8")
        edited, count = re.subn(r"\b435\b", "581", body)
        assert count, "premise: the census page must publish the read count"
        victim.write_text(edited, encoding="utf-8")
        assert_fails("check_census_counts", "changing a published census count")
    finally:
        _restore(victim, original)


def test_every_check_has_a_known_negative() -> None:
    """The guard this file never had, and the reason four checks drifted back out of coverage.

    A new `check_*` can otherwise ship with no demonstration that it can fail — the exact defect
    this file exists to prevent, one level up.
    """
    body = Path(__file__).read_text(encoding="utf-8")
    checks = sorted(name for name in dir(audit)
                    if name.startswith("check_") and callable(getattr(audit, name)))
    assert len(checks) > 15, f"only {len(checks)} checks collected; the collector is not collecting"
    uncovered = [name for name in checks if name not in body]
    assert not uncovered, (
        f"{len(uncovered)} audit check(s) have no known-negative in this file: {uncovered}. "
        f"A check nobody has watched fail is a check nobody has watched — add a case that breaks "
        f"what it guards and asserts the check reports it."
    )
