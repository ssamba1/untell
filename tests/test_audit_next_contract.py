"""Contract tests for .claude/audit_next.py — the pass dispatcher.

Pins the pure functions that decide which target the audit works next:
  - target_ids()   reads T## targets from audit-targets.md
  - rows()         parses the audit-log table rows
  - least_used()   the least-audited-option selection heuristic
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import audit_next as A  # noqa: E402


class TestRows:
    def test_parses_log_rows(self, tmp_path, monkeypatch) -> None:
        log = tmp_path / "audit-log.md"
        log.write_text(
            "| 1 | L1 | T12 | clean | 3 | 3 | abc123 | note here |\n"
            "| 2 | L6 | T16 | defect-fixed | 5 | 2 | def456 | fixed it |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(A, "LOG", log)
        out = A.rows()
        assert len(out) == 2
        assert out[0]["n"] == "1"
        assert out[0]["lane"] == "L1"
        assert out[0]["target"] == "T12"
        assert out[0]["verdict"] == "clean"
        assert out[1]["verdict"] == "defect-fixed"

    def test_missing_log_returns_empty(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(A, "LOG", tmp_path / "nope.md")
        assert A.rows() == []


class TestLeastUsed:
    def test_least_used_wins(self) -> None:
        options = ["T1", "T2", "T3"]
        history = [
            {"target": "T1"}, {"target": "T1"}, {"target": "T2"},
        ]
        assert A.least_used(options, history) == "T3"

    def test_ties_go_to_earliest(self) -> None:
        options = ["T1", "T2", "T3"]
        history = [{"target": "T1"}]
        # T2 and T3 both used 0 times -> earliest listed (T2) wins
        assert A.least_used(options, history) == "T2"

    def test_empty_history_first_option(self) -> None:
        assert A.least_used(["T1", "T2"], []) == "T1"


class TestTargetIds:
    def test_reads_target_headers(self, tmp_path, monkeypatch) -> None:
        targets = tmp_path / "audit-targets.md"
        targets.write_text(
            "## T12 API surface\nbody\n## T16 detector audit\nbody\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(A, "TARGETS", targets)
        assert A.target_ids() == ["T12", "T16"]


class TestSection:
    def test_extracts_section(self, tmp_path, monkeypatch) -> None:
        f = tmp_path / "file.md"
        f.write_text("## L1 intro\nbody one\n## L2 next\nbody two\n", encoding="utf-8")
        assert A.section(f, "L1") == "## L1 intro\nbody one"
        assert A.section(f, "L2") == "## L2 next\nbody two"


class TestEvidenceGate:
    """Survivors audit_next.py:181 — `not commit or commit == "-"` -> `and` / `or`."""

    def test_evidence_verdict_requires_commit(self, tmp_path, monkeypatch) -> None:
        """Survivor 181 (or->and): `--commit -` with an evidence verdict must refuse."""
        log = tmp_path / "audit-log.md"
        log.write_text("# Audit log\n\n| n | lane | target | verdict | before | after | commit | note |\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        targets = tmp_path / "audit-targets.md"
        targets.write_text("## T12 API surface\nbody\n", encoding="utf-8")
        monkeypatch.setattr(A, "TARGETS", targets)
        monkeypatch.setattr(A, "LANES", tmp_path / "audit-lanes.md")
        monkeypatch.setattr(
            sys, "argv",
            ["audit_next", "record", "--verdict", "defect-fixed",
             "--commit", "-", "--tests-before", "5", "--tests-after", "6",
             "--note", "a note that is long enough to pass the minimum"],
        )
        with pytest.raises(SystemExit) as ei:
            A.main()
        assert "REFUSED" in str(ei.value)

    def test_evidence_verdict_requires_test_growth(self, tmp_path, monkeypatch) -> None:
        """Survivor audit_next.py:183 — `tests_after <= tests_before` -> `<`.

        An evidence verdict with EQUAL test counts must refuse (no regression
        test was added). The mutation accepts it."""
        log = tmp_path / "audit-log.md"
        log.write_text("# Audit log\n\n| n | lane | target | verdict | before | after | commit | note |\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        targets = tmp_path / "audit-targets.md"
        targets.write_text("## T12 API surface\nbody\n", encoding="utf-8")
        monkeypatch.setattr(A, "TARGETS", targets)
        monkeypatch.setattr(A, "LANES", tmp_path / "audit-lanes.md")
        monkeypatch.setattr(
            sys, "argv",
            ["audit_next", "record", "--verdict", "defect-fixed",
             "--commit", "abc123", "--tests-before", "5", "--tests-after", "5",
             "--note", "a note that is long enough to pass the minimum"],
        )
        with pytest.raises(SystemExit) as ei:
            A.main()
        assert "REFUSED" in str(ei.value)
