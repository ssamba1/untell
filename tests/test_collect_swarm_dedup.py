"""Contract tests for .claude/collect_swarm.py — the fleet collector's dedupe.

Issue #16's defect class was fleet-collection collisions: worker rows computed
against a stale log got appended as the same pass recorded twice. audit_next.py
refuses byte-identical rows at record time; the collector (classify_row) is the
last line of defence for rows queued by workers against a stale log. These tests
pin that decision so removing it — which would silently let duplicates back in —
fails loudly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import collect_swarm as C  # noqa: E402


def _log(tmp_path: Path, lines: list[str]) -> Path:
    log = tmp_path / "audit-log.md"
    log.write_text(
        "# Audit log\n\n"
        "| # | lane | target | verdict | before | after | commit | note |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return log


class TestTakenLines:
    """Pins C.taken_lines() — the set of row lines already in the log."""

    def test_returns_stripped_row_lines(self, tmp_path, monkeypatch) -> None:
        log = _log(tmp_path, [
            "| 1 | L1 | T01 | clean | 1 | 1 | - | first note |",
            "| 2 | L2 | T02 | clean | 1 | 1 | - | second note |",
        ])
        monkeypatch.setattr(C, "LOG", log)
        out = C.taken_lines()
        assert "| 1 | L1 | T01 | clean | 1 | 1 | - | first note |" in out
        assert "| 2 | L2 | T02 | clean | 1 | 1 | - | second note |" in out
        # header/separator lines are not rows
        assert len(out) == 2

    def test_missing_log_returns_empty(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(C, "LOG", tmp_path / "nope.md")
        assert C.taken_lines() == set()


class TestClassifyRow:
    """The collector's per-row dedupe decision (issue #16 last line of defence)."""

    def test_byte_identical_row_is_rejected(self, tmp_path, monkeypatch) -> None:
        log = _log(tmp_path, [
            "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |",
        ])
        monkeypatch.setattr(C, "LOG", log)
        taken = C.taken_numbers()
        seen = C.taken_lines()
        dup = "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |"
        new, ok = C.classify_row(dup, taken, seen)
        assert ok is False  # REFUSED, never appended
        assert new == dup
        assert len(taken) == 1  # no extra number claimed
        assert len(seen) == 1

    def test_bad_row_is_rejected(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(C, "LOG", _log(tmp_path, []))
        taken, seen = set(), set()
        new, ok = C.classify_row("this is not a row", taken, seen)
        assert ok is False
        assert not taken and not seen

    def test_fresh_row_is_accepted_with_its_number(self, tmp_path, monkeypatch) -> None:
        log = _log(tmp_path, [
            "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |",
        ])
        monkeypatch.setattr(C, "LOG", log)
        taken = C.taken_numbers()
        seen = C.taken_lines()
        fresh = "| 6 | L1 | T12 | clean | 3 | 3 | - | probed Y, new data |"
        new, ok = C.classify_row(fresh, taken, seen)
        assert ok is True
        assert new == fresh  # number 6 is free, unchanged
        assert 6 in taken
        assert new in seen
        assert 5 in taken  # existing preserved

    def test_number_collision_is_renumbered(self, tmp_path, monkeypatch) -> None:
        log = _log(tmp_path, [
            "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |",
        ])
        monkeypatch.setattr(C, "LOG", log)
        taken = C.taken_numbers()
        seen = C.taken_lines()
        # worker computed pass 5 against a stale log; must be renumbered, not dup
        colliding = "| 5 | L9 | experiment/RECIPE | clean | 4 | 4 | - | different pass |"
        new, ok = C.classify_row(colliding, taken, seen)
        assert ok is True
        assert new.startswith("| 6 |")  # 5 taken -> next free 6
        assert 6 in taken
        assert 5 in taken

    def test_fresh_row_not_seen_nor_number_taken(self, tmp_path, monkeypatch) -> None:
        log = _log(tmp_path, [
            "| 5 | L1 | T12 | clean | 3 | 3 | - | probed X, invariant held |",
        ])
        monkeypatch.setattr(C, "LOG", log)
        seen = C.taken_lines()
        fresh = "| 6 | L1 | T12 | clean | 3 | 3 | - | probed Y, new data |"
        assert fresh not in seen
        assert int(C.ROW.match(fresh).group(1)) not in C.taken_numbers()
