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


class TestNextPassNumber:
    """Issue #16: the recorder counts passes, not rows.

    The log is marked, not pruned, when a fleet collision reuses a number, so the row
    count can run behind the highest pass number (2729 rows ended at pass 2730 after the
    55 duplicate rows were marked). Numbering from the row count would reissue pass 2676
    on the very next record; numbering from the highest recorded pass keeps every pass
    unique.
    """

    def test_empty_history_starts_at_one(self) -> None:
        assert A.next_pass_number([]) == 1

    def test_contiguous_history(self) -> None:
        history = [{"n": str(i)} for i in range(1, 5)]
        assert A.next_pass_number(history) == 5

    def test_counts_passes_not_rows_after_dedup(self) -> None:
        # Four rows whose numbers run to 2730 (the pre-dedup shape of the real log):
        # the next number is 2731, not 5.
        history = [{"n": "1"}, {"n": "2"}, {"n": "3"}, {"n": "2730"}]
        assert A.next_pass_number(history) == 2731

    def test_assign_offset_continues_from_max(self) -> None:
        def row(n: str) -> dict:
            return {"n": n, "lane": "L1", "target": "T01", "verdict": "clean",
                    "before": "0", "after": "0", "commit": "-", "note": "x" * 20}
        history = [row("1"), row("2"), row("2730")]
        # Each simulated offset step numbers from the appended copy, so the third
        # simulated pass is 2733, not 2731 - the fleet never reissues a number.
        n, _, _ = A.assign(history, offset=2)
        assert n == 2733


class TestByteIdentical:
    """Issue #16's named defect class: the same pass recorded twice."""

    def test_byte_identical_helper(self, tmp_path, monkeypatch) -> None:
        log = tmp_path / "audit-log.md"
        row = "| 2 | L2 | untell/layout.py | clean | 3 | 3 | - | same note |"
        log.write_text("# Audit log\n\n" + row + "\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        assert A.byte_identical(row + "\n")
        assert not A.byte_identical("| 3 | L2 | untell/layout.py | clean | 3 | 3 | - | other |\n")

    def test_missing_log_is_not_identical(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(A, "LOG", tmp_path / "nope.md")
        assert not A.byte_identical("| 1 | L1 | T01 | clean | 0 | 0 | - | x |\n")

    def test_recording_an_identical_row_is_refused(self, tmp_path, monkeypatch) -> None:
        """A worker row computed against a stale log can collide on number AND content;
        the recorder must refuse it instead of appending the same pass twice."""
        log = tmp_path / "audit-log.md"
        existing = "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |"
        log.write_text("# Audit log\n\n" + existing + "\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        # Force the same (n, lane, target) a stale worker would compute.
        monkeypatch.setattr(A, "assign", lambda history, offset=0: (5, "L1", "T12"))
        monkeypatch.setattr(
            sys, "argv",
            ["audit_next", "record", "--verdict", "clean",
             "--tests-before", "3", "--tests-after", "3",
             "--note", "probed X, invariant held"],
        )
        with pytest.raises(SystemExit) as ei:
            A.main()
        assert "REFUSED" in str(ei.value)
        assert log.read_text(encoding="utf-8").count(existing) == 1  # nothing appended

    def test_recording_a_distinct_row_still_works(self, tmp_path, monkeypatch) -> None:
        """The refusal is byte-identical text, not same pass number - a distinct note
        for the same n is a different pass and must be recorded."""
        log = tmp_path / "audit-log.md"
        existing = "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |"
        log.write_text("# Audit log\n\n" + existing + "\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        monkeypatch.setattr(A, "assign", lambda history, offset=0: (5, "L1", "T12"))
        monkeypatch.setattr(
            sys, "argv",
            ["audit_next", "record", "--verdict", "clean",
             "--tests-before", "3", "--tests-after", "3",
             "--note", "probed Y, different numbers surfaced"],
        )
        assert A.main() == 0
        text = log.read_text(encoding="utf-8")
        assert text.count(existing) == 1
        assert "probed Y" in text


class TestLogHygiene:
    """The live log stays deduped: pins issue #16's 'duplicates removed or marked'."""

    LOG = Path(__file__).resolve().parent.parent / ".claude" / "audit-log.md"

    def test_no_unmarked_duplicate_pass_numbers(self) -> None:
        text = self.LOG.read_text(encoding="utf-8")
        by_n: dict[str, list[dict]] = {}
        for line in text.splitlines():
            m = A.ROW.match(line.strip())
            if m:
                by_n.setdefault(m.group("n"), []).append(m.groupdict())
        extras = 0
        for n, rows in sorted(by_n.items()):
            if len(rows) == 1:
                continue
            marked = [r for r in rows if "dup" in r["note"]]
            unmarked = [r for r in rows if "dup" not in r["note"]]
            assert len(unmarked) == 1, (
                f"pass {n} has {len(rows)} rows but {len(unmarked)} unmarked canonical "
                "rows - every extra must carry a [dup pass# N] marker"
            )
            assert len(marked) == len(rows) - 1
            extras += len(marked)
        assert extras >= 55, f"expected the 55 issue-16 duplicates to stay marked, saw {extras}"
        assert extras == sum(len(rs) - 1 for rs in by_n.values() if len(rs) > 1)
