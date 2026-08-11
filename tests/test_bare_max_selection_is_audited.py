"""A new selector reading the bare detector `max` must fail the audit.

The same defect was found twice: `composite._selection_key` was written for it, and `targeted` was
still comparing bare floats months later, discarding 15 of 19 real per-sentence improvements. The
grep that found the second instance is now a check the repository runs every time.

`max` is one detector's number and a saturating member pins it — MEASURED, the ensemble max reaches
>=0.999 on 100% of HC3 AI text and 30% of RAID's, against 0% of human text. A selector reading it
alone is choosing among candidates it cannot distinguish.

The check is an allowlist, not a pattern: acceptance against a threshold, a reported verdict and a
selector with a different measured secondary objective are all legitimate reads of `max`, and each is
listed with its reason. This file checks that the allowlist bites in both directions — a new site
fails, and a listed site that disappears fails too, so the reasons cannot outlive the code.
"""

from __future__ import annotations

import logging

import pytest

import untell.scripts.audit as audit
from untell.scripts.audit import (
    SELECTION_ON_BARE_MAX_ALLOWED,
    Report,
    check_selection_does_not_read_a_bare_max,
)

OFFENDER = '''
def pick_best(candidates, baseline):
    best = baseline
    for cand, score in candidates:
        if score["max"] < best["max"]:
            best = score
    return best
'''

INNOCENT = '''
from untell.rewriter.base import selection_key


def pick_best(candidates, baseline):
    best = baseline
    for cand, score in candidates:
        if selection_key(score) < selection_key(best):
            best = score
    return best
'''


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _run_against(tmp_path, source: str, monkeypatch) -> Report:
    pkg = tmp_path / "untell"
    pkg.mkdir()
    (pkg / "chooser.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "SELECTION_ON_BARE_MAX_ALLOWED", {})
    report = Report()
    check_selection_does_not_read_a_bare_max(report)
    return report


def test_a_new_bare_max_selector_fails(tmp_path, monkeypatch) -> None:
    report = _run_against(tmp_path, OFFENDER, monkeypatch)
    assert report.failures
    assert "untell/chooser.py::pick_best" in report.failures[0].detail


def test_the_shared_selector_passes(tmp_path, monkeypatch) -> None:
    """Guards the guard: if the check fired on any comparison at all it would be useless, because
    the fixed form would fail it too and the only way to pass would be the allowlist."""
    report = _run_against(tmp_path, INNOCENT, monkeypatch)
    assert not report.failures, report.findings[0].detail


def test_a_listed_site_that_disappears_also_fails(tmp_path, monkeypatch) -> None:
    """The reasons must not outlive the code. A stale entry is a claim about a call site that is no
    longer there, which is the failure mode this whole audit exists for."""
    pkg = tmp_path / "untell"
    pkg.mkdir()
    (pkg / "chooser.py").write_text(INNOCENT, encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(
        audit, "SELECTION_ON_BARE_MAX_ALLOWED", {"untell/gone.py::vanished": "a reason"}
    )
    report = Report()
    check_selection_does_not_read_a_bare_max(report)
    assert report.failures
    assert "no longer present" in report.failures[0].detail


def test_every_listed_site_carries_a_reason() -> None:
    """An allowlist without reasons is a suppression file."""
    for site, reason in SELECTION_ON_BARE_MAX_ALLOWED.items():
        assert "::" in site, site
        assert len(reason.split()) >= 6, f"{site}: {reason!r}"
