"""Audit-module branches the doc-state tests do not reach: the missing-census report,
the collection-failure paths, and the skip verdict when pytest cannot be asked."""

from __future__ import annotations

import subprocess

from untell.scripts import audit


def test_missing_census_data_is_a_named_failure(monkeypatch, tmp_path) -> None:
    """A repo tree without docs/humanizer-census.json must fail the census check by name."""
    monkeypatch.setattr(audit, "REPO", tmp_path)
    report = audit.Report()
    audit.check_census_counts(report)
    finding = next(f for f in report.findings if f.name == "census data is readable")
    assert finding.ok is False
    assert "humanizer-census.json missing" in finding.detail


def test_collected_test_count_returns_none_when_pytest_cannot_run(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("pytest missing")

    monkeypatch.setattr(subprocess, "run", boom)
    assert audit._collected_test_count() is None


def test_collected_test_count_returns_none_on_timeout(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=600)

    monkeypatch.setattr(subprocess, "run", boom)
    assert audit._collected_test_count() is None


def test_uncollectable_suite_is_reported_as_skipped_not_failed(monkeypatch) -> None:
    """When pytest cannot collect, the check must say skipped — not pass a real number."""
    monkeypatch.setattr(audit, "_collected_test_count", lambda: None)
    report = audit.Report()
    audit.check_test_count_claims(report)
    finding = next(f for f in report.findings if f.name.startswith("every 'N tests'"))
    assert finding.ok is True
    assert "skipped" in finding.detail
