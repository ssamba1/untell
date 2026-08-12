"""A missing document is the largest possible documentation drift, so the audit must name it.

`untell-audit` exists because "a correctness argument decays the moment a number in a document stops
matching the code", and it reports three totals — checked, attributed, unattributed — precisely so it
never claims coverage it does not have.

It had two incompatible answers for "the document is not there". MEASURED by deleting each
`LIVE_DOCS` entry from a copy of the repository:

    checks doing `if not doc.exists(): continue`   findings vanish, run still reports success
    checks calling `read_text` bare               FileNotFoundError traceback, exit 1

Neither is a report. Absence is now a named failing finding and the run continues, so the other
checks still say what they found.

**The measurement that started this was wrong the first time.** A harness that swept documents with
`except Exception: pass` showed README removal as a *silent* loss; the real command was dying with a
traceback. The swallow was in the harness, not the audit. What survived is the `continue` path, which
is silent for real — the two now behave the same way because they call the same reader.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

import untell.scripts.audit as audit

IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", ".pytest_cache", "*.pyc", "node_modules"
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def repo_copy(tmp_path, monkeypatch) -> Path:
    """A real copy, because these checks read real documents and a fixture tree would prove
    nothing about them."""
    dest = tmp_path / "repo"
    shutil.copytree(audit.REPO, dest, ignore=IGNORED)
    monkeypatch.setattr(audit, "REPO", dest)
    return dest


def test_every_live_doc_exists_today() -> None:
    """Premise. If one were already missing, the check below would pass for the wrong reason."""
    assert all((audit.REPO / rel).exists() for rel in audit.LIVE_DOCS), audit.LIVE_DOCS


@pytest.mark.parametrize("rel", audit.LIVE_DOCS)
def test_a_missing_document_is_a_named_failure(repo_copy, rel: str) -> None:
    (repo_copy / rel).unlink()
    report = audit.Report()
    # Every check that reads a LIVE_DOC. MEASURED by deleting each in turn and recording who
    # reported it: `check_derivable` is the only one that reaches all five, `docs/index.md` and
    # `docs/what-would-make-this-the-top-repo.md` are reported by nothing else.
    for check in (
        audit.check_derivable,
        audit.check_named_repo_stars,
        audit.check_largest_repo_claims,
        audit.check_dynamic_env_vars,
    ):
        check(report)
    named = [f for f in report.failures if rel in f.name]
    assert named, f"{rel} vanished without a finding: {[f.name for f in report.findings]}"


def test_the_reader_returns_content_when_the_document_is_there(repo_copy) -> None:
    """Guards the guard. A reader that always reported absence would fail every check equally and
    the parametrised test above would still pass."""
    report = audit.Report()
    body = audit.audited_doc(report, "README.md")
    assert body and "untell" in body
    assert not report.findings, "a present document must not produce a finding"


def test_the_run_continues_past_a_missing_document(repo_copy) -> None:
    """The reason absence is a finding rather than an exception: one missing file must not stop the
    audit from reporting everything else it checked."""
    (repo_copy / "README.md").unlink()
    report = audit.Report()
    audit.check_named_repo_stars(report)  # must not raise
    assert len(report.findings) > 1, "only the absence was reported; the rest of the check stopped"
    assert any(f.ok for f in report.findings), "nothing else got checked"


def test_no_live_doc_is_read_without_going_through_the_reader() -> None:
    """The defect was two call sites answering the question differently. This is the check that
    keeps a third from appearing."""
    import re

    source = (Path(audit.__file__)).read_text(encoding="utf-8")
    body = source.split("def audited_doc", 1)[1].split("\ndef ", 1)[1]
    for rel in audit.LIVE_DOCS:
        for match in re.finditer(re.escape(rel), body):
            line = body[body.rfind("\n", 0, match.start()) + 1 : body.find("\n", match.start())]
            if "read_text" in line:
                pytest.fail(f"{rel} read directly, bypassing audited_doc: {line.strip()}")
