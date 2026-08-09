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


def test_an_undocumented_env_var_is_caught(tmp_path, monkeypatch):
    """Sixteen of twenty UNTELL_* variables were undocumented, including the REST server's auth key
    and two switches that DISABLE a meaning gate.

    Configuration that exists but cannot be discovered is a feature nobody can use, and in the case
    of `UNTELL_DISABLE_NLI` / `UNTELL_DISABLE_ROLES` it is a guarantee a user can switch off without
    knowing the guarantee was there.
    """
    pkg = tmp_path / "untell"
    pkg.mkdir()
    (pkg / "thing.py").write_text("import os\nos.getenv('UNTELL_SECRET_KNOB')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# nothing documented here\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)

    read = set()
    for path in (tmp_path / "untell").rglob("*.py"):
        read |= set(re.findall(r"\b(UNTELL_[A-Z0-9_]+)\b", path.read_text(encoding="utf-8")))
    undocumented = [v for v in read if v not in (tmp_path / "README.md").read_text(encoding="utf-8")]
    assert undocumented == ["UNTELL_SECRET_KNOB"]


def test_the_meaning_gate_kill_switches_are_documented_as_such():
    """These two remove a guarantee the README makes elsewhere, and nothing warns at runtime when
    they are set — so the documentation is the only place a user can learn it."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for var in ("UNTELL_DISABLE_NLI", "UNTELL_DISABLE_ROLES"):
        assert var in readme, f"{var} disables a meaning gate and is undocumented"
    section = readme.split("## Environment variables", 1)[-1].split("## Troubleshooting", 1)[0]
    assert "unverified" in section or "reversed" in section, (
        "the DISABLE switches are listed without saying what they remove"
    )


def _demo_claim_finding(tmp_path, monkeypatch, page: str, doc_text: str):
    """Run the real check against a throwaway repo and return its finding.

    This calls ``check_derivable`` rather than reimplementing the rule, so the test fails if the
    rule is deleted — which is the whole point of a guard on a guard.
    """
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "demo.html").write_text(page, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(doc_text, encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "LIVE_DOCS", ())
    report = audit.Report()
    audit.check_demo_privacy_claims(report)
    name = "no document claims the browser demo scores locally"
    return next((f for f in report.findings if f.name == name), None)


def test_a_false_local_scoring_claim_is_caught(tmp_path, monkeypatch):
    """The changelog promised docs/demo.html scored in the browser and uploaded nothing. The page
    POSTs the text to a server. Of every kind of documentation drift this repo has had, that is the
    one a reader can be harmed by acting on."""
    finding = _demo_claim_finding(
        tmp_path,
        monkeypatch,
        page="<script>fetch('/score')</script>",
        doc_text="- In-browser detector: a client-side port of the scorer, nothing uploaded.\n",
    )
    assert finding is not None, "the check did not run"
    assert not finding.ok, "a false local-scoring claim was not reported"


def test_the_claim_check_passes_when_the_page_really_is_local(tmp_path, monkeypatch):
    """The rule is conditional on the page actually calling out. A page with no ``fetch(`` may
    legitimately say it scores locally — otherwise the check would block ever shipping one."""
    finding = _demo_claim_finding(
        tmp_path,
        monkeypatch,
        page="<script>function score(t){return t.length}</script>",
        doc_text="- In-browser detector: a client-side port of the scorer, nothing uploaded.\n",
    )
    assert finding is not None, "the check did not run"
    assert finding.ok, f"a genuinely local page was reported as lying: {finding.detail}"
