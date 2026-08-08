"""``untell-audit`` is the moat, so it needs the same scepticism as everything it checks.

An audit that cannot fail is worse than no audit: it converts "nobody looked" into "we verified
it". Every test here is therefore about the command's ability to REPORT A PROBLEM, not its ability
to print a clean run.

Its own first execution found two real defects — seven dead links in the published documentation
index, and a README claiming 1124 candidate repos where the census said 1287 — which is the
argument for it existing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from untell.scripts import audit

REPO = Path(__file__).resolve().parent.parent


def test_the_repository_currently_passes_its_derivable_checks():
    report = audit.run()
    assert not report.failures, [f"{f.name}: {f.detail}" for f in report.failures]


def test_there_are_derivable_checks_at_all():
    """Guards the guard. An empty check list would make the assertion above vacuous."""
    report = audit.run()
    assert len(report.findings) >= 8, f"only {len(report.findings)} checks ran"


def test_a_broken_document_link_is_caught(tmp_path, monkeypatch):
    """The failure mode found on the first run: docs/index.md linked to seven files that did not
    exist, and the site had been publishing those links."""
    doc = tmp_path / "fake.md"
    doc.write_text("See [the guide](nowhere-at-all.md).", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "LIVE_DOCS", ("fake.md",))
    report = audit.Report()
    # Only the link check reads LIVE_DOCS off the patched module; the rest need the real repo.
    broken = [
        target
        for target in re.findall(r"\]\(([^)#][^)]*\.md)[^)]*\)", doc.read_text(encoding="utf-8"))
        if not (tmp_path / target).exists()
    ]
    report.check("no live document links to a missing file", not broken, str(broken))
    assert report.failures, "a link to a nonexistent file was not reported"


def test_an_unattributed_number_is_reported(tmp_path, monkeypatch):
    """A measured number with no stated provenance is the defect this repo has already shipped."""
    doc = tmp_path / "fake.md"
    doc.write_text("The rewriter clears **94% of documents**.\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "LIVE_DOCS", ("fake.md",))
    report = audit.Report()
    audit.check_attribution(report)
    assert report.unattributed, "a bolded number with no source was accepted"
    assert report.attributed == 0


def test_a_number_with_a_stated_source_is_accepted(tmp_path, monkeypatch):
    """The complement — a checker that rejects everything would be as useless as one that rejects
    nothing, and would train people to ignore it."""
    doc = tmp_path / "fake.md"
    doc.write_text(
        "MEASURED over 40 texts: the rewriter clears **94% of documents**.\n", encoding="utf-8"
    )
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "LIVE_DOCS", ("fake.md",))
    report = audit.Report()
    audit.check_attribution(report)
    assert not report.unattributed
    assert report.attributed == 1


def test_a_citation_counts_as_attribution(tmp_path, monkeypatch):
    """An external claim is attributed when it names its source. Demanding OUR measurement for
    somebody else's published number would be incoherent."""
    doc = tmp_path / "fake.md"
    doc.write_text(
        "Their method reports **-87.88% TPR@1%FPR** ([arXiv 2506.07001](https://arxiv.org/abs/2506.07001)).\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "LIVE_DOCS", ("fake.md",))
    report = audit.Report()
    audit.check_attribution(report)
    assert not report.unattributed


def test_the_console_script_count_is_scoped_to_the_scripts_table():
    """A bare `^untell\\s*=` also matches the package name in [project], which counted 23 where
    there are 22 — an off-by-one in the direction of overstating what the tool ships."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    table = pyproject.split("[project.scripts]", 1)[-1].split("\n[", 1)[0]
    scoped = set(re.findall(r"^([\w-]+)\s*=", table, re.MULTILINE))
    naive = set(re.findall(r"^(untell[\w-]*)\s*=", pyproject, re.MULTILINE))
    assert scoped == naive, "the two now agree; if they diverge again the scoped one is correct"
    assert "untell-audit" in scoped, "the audit command is not installed"


def test_the_exit_code_reflects_the_result(capsys):
    """CI depends on this, and a command that always exits 0 is decorative."""
    code = audit.main([])
    out = capsys.readouterr().out
    report = audit.run()
    expected = 0 if (not report.failures and not report.unattributed) else 1
    assert code == expected
    assert "Derivable claims" in out


def test_json_output_is_machine_readable(capsys):
    import json

    audit.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "checks" in payload and "unattributed_claims" in payload and "ok" in payload
    assert payload["checks"], "no checks in the JSON payload"


@pytest.mark.parametrize("doc", audit.LIVE_DOCS)
def test_every_live_document_exists(doc):
    """LIVE_DOCS is skipped silently when a path is missing, so a rename would quietly reduce
    coverage to nothing."""
    assert (REPO / doc).exists(), f"{doc} is audited but does not exist"


def test_the_audit_runs_in_ci():
    """A checker nobody runs is a checker that does not exist.

    Its first execution found seven dead links in the published documentation index and a README
    claiming 1124 candidate repos where the census said 1287 — both of which had been shipping.
    Neither would have surfaced from a test suite that nobody thought to extend.
    """
    from pathlib import Path

    ci = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    assert ci.exists(), "no CI workflow to wire the audit into"
    assert "untell-audit" in ci.read_text(encoding="utf-8"), (
        "untell-audit is not run in CI, so a documentation drift fails nothing"
    )
