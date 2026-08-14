"""Killing tests for audit.py mutation survivors (2026-08-14 sweep).

  line 227  logic: == -> !=       registry-count comparison in check_derivable.
  line 1551 logic: and -> or      main() exit code with failures + no unattributed.

Killed here. The other 14 survivors are docstring/comment prose mutations or
cosmetic constants (619/623/715/720/724/759/859/878/882/1154/1193/1312/1346/1474)
— annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from untell.scripts import audit as A


class TestRegistryCountComparison:
    """Survivor audit.py:227 — `int(found) == expected` mutated to `!=`.

    A document claiming a LOCAL detector count that does not match the registry
    must FAIL the check. The mutation would pass exactly the wrong counts."""

    def test_wrong_local_count_fails(self, monkeypatch) -> None:
        report = A.Report()
        # registry has N local detectors; the doc claims N+1
        local, commercial = A._detector_counts()
        monkeypatch.setattr(A, "audited_doc", lambda r, rel: f"claims {local + 1} local")
        monkeypatch.setattr(
            A,
            "LIVE_DOCS",
            ("docs/why-best-open-repo.md",),
        )
        # avoid the 16s rewriter-model load later in check_derivable
        monkeypatch.setattr("untell.rewriter.get_rewriter", lambda *a, **k: None)
        # avoid importing every console-script module (heavy detector imports)
        monkeypatch.setattr("importlib.import_module", lambda name: type("M", (), {"main": lambda: None})())
        A.check_derivable(report)
        reg = [f for f in report.findings if "matches the registry" in f.name]
        assert reg, "registry check must run"
        assert not reg[0].ok, f"wrong count must fail: {reg[0].detail}"


class TestExitCodeWithFailures:
    """Survivor audit.py:1551 — `not failures and not unattributed` mutated to `or`.

    A report with failures but no unattributed entries exits 1 (failure). The
    mutation (`or`) would return 0 — a red audit reported as success."""

    def test_failures_without_unattributed_exit_one(self, monkeypatch) -> None:
        failing = A.Report()
        failing.check("a failing check", False, "red")
        assert failing.failures and not failing.unattributed
        monkeypatch.setattr(A, "run", lambda: failing)
        monkeypatch.setattr(A, "_render", lambda report, as_json: "")
        assert A.main([]) == 1

    def test_clean_report_exits_zero(self, monkeypatch) -> None:
        clean = A.Report()
        clean.check("ok", True)
        monkeypatch.setattr(A, "run", lambda: clean)
        monkeypatch.setattr(A, "_render", lambda report, as_json: "")
        assert A.main([]) == 0
