"""The local gate must refuse what CI refuses, and must not be silently uninstallable.

A round of this work was committed and pushed while `untell-audit` was failing. The audit and the
commit ran in one shell sequence that did not gate on the audit's exit code, so an unattributed
figure went out and was corrected in a follow-up commit. CI would have caught it — after the push, in
a public failure, on a branch somebody else might have pulled.

`.githooks/pre-commit` closes that gap locally. It is versioned rather than left in `.git/hooks`,
which is not tracked and so cannot be reviewed, and it is scoped by what changed because a gate slow
enough to skip is a gate nobody runs.

These tests check the hook's *content*, not its behaviour: exercising a real hook needs a repository
and a commit, and a test that shells out to `git commit` would be slower and more fragile than the
thing it guards. What can drift silently is the list of checks — a gate that stops running the audit
is indistinguishable from a gate that passes.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".githooks" / "pre-commit"


def test_the_hook_is_versioned():
    """In `.git/hooks` it would be untracked, unreviewable, and absent from every fresh clone."""
    assert HOOK.exists(), "the pre-commit hook must live in .githooks/ so it is version-controlled"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_the_hook_is_executable():
    """A non-executable hook is skipped by git in silence, which looks exactly like a passing gate."""
    assert HOOK.stat().st_mode & stat.S_IXUSR, "git will silently ignore a non-executable hook"


@pytest.mark.parametrize("check", ["ruff check", "untell.scripts.audit",
                                   "test_docs_claims", "test_roadmap_status",
                                   "test_retracted_claims_do_not_survive_elsewhere",
                                   # Added in round 53. This is the guard that notices a document
                                   # stating a count next to a noun the audit tracks, and it was
                                   # absent from the hook for fifty-two rounds. Four ledger entries
                                   # DESCRIBING a count-drift defect reproduced the literal string
                                   # they warned about, re-triggered the check, and reached the
                                   # remote — because the hook ran the other three doc guards and
                                   # not this one.
                                   "test_every_audit_check_can_fail",
                                   # Added in round 54. CI runs `mkdocs build --strict` as a LINK
                                   # CHECKER — its first run there found 47 broken cross-references
                                   # — and this hook's author ran it by hand every round for
                                   # fifty-three rounds, which is the clearest possible sign it
                                   # belonged in the gate. A dead link is invisible to every other
                                   # guard: the audit reads claims, the doc tests read counts, and
                                   # neither follows a href.
                                   "mkdocs build --strict"])
def test_the_hook_still_runs_every_gate_ci_runs(check):
    """The drift that matters. Dropping a check from this script makes the hook faster and makes it
    stop protecting the thing it was written for, with no visible difference."""
    assert check in HOOK.read_text(encoding="utf-8"), f"the pre-commit hook no longer runs {check}"


def test_the_hook_fails_the_commit_rather_than_warning():
    """`set -e` is absent on purpose — the script checks exit codes itself — so the failure path has
    to end in a non-zero exit. A hook that prints a warning and exits 0 is decoration."""
    body = HOOK.read_text(encoding="utf-8")
    assert "exit 1" in body, "the hook must fail the commit, not just print"


def test_the_hook_documents_its_own_bypass():
    """A gate with no escape hatch gets uninstalled the first time someone needs a WIP commit, and
    then protects nothing. The escape has to be documented in the file that imposes the gate."""
    assert "--no-verify" in HOOK.read_text(encoding="utf-8")


def test_installation_is_documented_where_a_contributor_will_look():
    """`core.hooksPath` is not set by cloning. An uninstalled hook is the default state, so the
    instruction has to be somewhere a contributor reads before their first commit."""
    contributing = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "core.hooksPath" in contributing, (
        "CONTRIBUTING.md must say how to install the hook — it does nothing until configured"
    )


# --- the sabotage guard ---------------------------------------------------------------------------


def test_the_hook_refuses_a_staged_sabotaged_file():
    """`scripts/mutation_sweep.py` rewrites source files in place and restores them when it
    finishes. While it runs, `git status` reports the module under test as modified — and a
    `git add -A` would commit a file whose every public function raises.

    This happened twice during round forty-six: the stop-hook reported uncommitted changes, and both
    times the "change" was a module the sweep was holding. Neither was committed, but only because
    each was checked by hand first. The sweep refuses to START on a dirty tree; nothing stopped a
    commit landing mid-sweep.
    """
    body = HOOK.read_text(encoding="utf-8")
    assert 'raise AssertionError("sabotaged")' in body, (
        "the hook must refuse a staged file carrying the sabotage marker"
    )
    assert 'git show ":$f"' in body, "it has to inspect what is STAGED, not the working tree"


def test_the_guard_is_scoped_to_the_directories_the_sweep_rewrites():
    """The first version grepped the whole staged diff and refused the commit that ADDED it: this
    hook and this test file both contain the marker as a literal, which is not sabotage. A guard
    that cannot tell a broken module from a file discussing broken modules is a guard that gets
    bypassed with --no-verify — which here would commit the sabotaged file it exists to stop."""
    body = HOOK.read_text(encoding="utf-8")
    assert "^(untell|eval)/" in body, (
        "the sabotage check must be scoped to the directories mutation_sweep rewrites, or it fires "
        "on its own source"
    )


def test_the_guard_keys_on_the_marker_the_sweep_actually_writes():
    """If the two drifted apart the guard would pass every sabotaged file. The marker is a literal
    in both places, so this is the only thing holding them together."""
    import inspect

    import scripts.mutation_sweep as sweep

    marker = 'raise AssertionError("sabotaged")'
    assert marker in inspect.getsource(sweep.sabotage), "the sweep no longer writes this marker"
    assert marker in HOOK.read_text(encoding="utf-8"), "the hook no longer looks for it"


def test_the_guard_explains_how_to_recover():
    """A refusal that does not say what to do gets bypassed with --no-verify, which in this case
    would commit the sabotaged file."""
    body = HOOK.read_text(encoding="utf-8")
    assert "git checkout" in body, "the message must say how to restore the file"


def test_the_hook_degrades_when_an_optional_tool_is_absent():
    """`ruff` and `mkdocs` are dev dependencies, not guarantees. A hook that fails hard when one is
    missing gets uninstalled by the first contributor who has not run `pip install -e .[dev]`, and
    then guards nothing at all. Both are guarded by `command -v`."""
    body = HOOK.read_text(encoding="utf-8")
    assert body.count("command -v") >= 2, (
        "every optional tool the hook invokes must be probed before it is run"
    )


def test_the_hook_checks_links_only_when_documentation_changed():
    """Scoping is what keeps the gate fast enough to survive. A link check on every Python commit
    would add seconds to changes that cannot break a link."""
    lines = HOOK.read_text(encoding="utf-8").splitlines()
    # The COMMAND, not the comment above it explaining what the command is for. The first version of
    # this test matched the comment — which mentions `mkdocs build --strict` while describing it —
    # and then checked the wrong three lines. Prose matched instead of the thing, in a test written
    # for a hook added because prose kept matching instead of the thing.
    command_lines = [i for i, line in enumerate(lines)
                     if line.strip().startswith("mkdocs build")]
    assert command_lines, "the hook does not actually invoke mkdocs"
    for i in command_lines:
        preceding = "\n".join(lines[max(0, i - 3):i + 1])
        assert "docs_changed" in preceding, (
            f"the link check on line {i + 1} is not gated on a Markdown change"
        )
