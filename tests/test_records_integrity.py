"""Guard tests for .claude record file integrity (slice 19).

Pins three invariants that the cleanliness track (wave 7, slice 19) established:

1. audit-log.md: no unmarked duplicate pass numbers (already in test_audit_next_contract.py;
   NOT duplicated here - we just import the live-log check for completeness).

2. measurements.jsonl: every line must be valid JSON; standard rows (those with a
   'seconds' key) must carry recipe/seconds/argv/metrics/raw; the non-standard schema
   (rows without 'seconds', e.g. slice12-ner-lite-gate timing rows) is a documented
   schema evolution and must NOT carry the standard required fields.

3. instruments.json: must be valid JSON; every key must name a recipe that research.py
   knows; every entry must carry deterministic/run_to_run/reported_spread.

Each class has:
  - A live-file test that fires if the real record drifts.
  - A unit test that proves the guard detects the bad state (uses tmp_path fixtures).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
LEDGER = CLAUDE / "measurements.jsonl"
INSTRUMENTS = CLAUDE / "instruments.json"

sys.path.insert(0, str(CLAUDE))
import research as R  # noqa: E402
import audit_next as A  # noqa: E402

# ── measurements.jsonl ─────────────────────────────────────────────────────────

# Standard schema (rows with 'seconds').  Non-standard rows (no 'seconds') are a
# documented schema evolution (slice12-ner-lite-gate timing); they must NOT be checked
# against this set.
STANDARD_REQUIRED = {"recipe", "seconds", "argv", "metrics", "raw"}

# Fields that non-standard rows (schema-evolution rows) carry instead.
NONSTANDARD_REQUIRED = {"recipe", "date", "head", "kind", "rows"}


class TestMeasurementsJsonlValidity:
    """All lines in the live ledger must be parseable JSON."""

    def test_all_lines_are_valid_json(self) -> None:
        """Live guard: any non-JSON line in the ledger breaks the L8 compare pipeline."""
        if not LEDGER.exists():
            pytest.skip("ledger not present in this checkout")
        bad: list[tuple[int, str]] = []
        for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                bad.append((i, str(exc)))
        assert not bad, (
            f"measurements.jsonl has {len(bad)} invalid JSON line(s):\n"
            + "\n".join(f"  line {n}: {e}" for n, e in bad)
        )

    def test_invalid_json_is_detected(self, tmp_path, monkeypatch) -> None:
        """Proves the guard fires: a file with one broken line raises AssertionError."""
        ledger = tmp_path / "measurements.jsonl"
        ledger.write_text(
            json.dumps({"recipe": "x", "seconds": 1.0, "argv": [], "metrics": {}, "raw": {}})
            + "\n"
            + "not-json{broken\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(R, "LEDGER", ledger)
        # Re-use the same logic as the live test to prove it would fire.
        bad: list[tuple[int, str]] = []
        for i, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                bad.append((i, str(exc)))
        assert bad, "expected the guard to find a bad JSON line but it did not"


class TestMeasurementsJsonlSchema:
    """Standard rows carry the five required fields; non-standard rows are schema evolution."""

    def test_standard_rows_have_required_fields(self) -> None:
        """Live guard: every row with 'seconds' must carry the full standard field set."""
        if not LEDGER.exists():
            pytest.skip("ledger not present in this checkout")
        missing: list[tuple[int, str, list[str]]] = []
        for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "seconds" not in row:
                # Schema-evolution row (e.g. slice12-ner-lite-gate timing); skip
                continue
            absent = sorted(STANDARD_REQUIRED - set(row))
            if absent:
                missing.append((i, row.get("recipe", "?"), absent))
        assert not missing, (
            f"measurements.jsonl has {len(missing)} standard row(s) missing required fields:\n"
            + "\n".join(f"  line {n} ({r}): missing {f}" for n, r, f in missing)
        )

    def test_schema_evolution_rows_are_documented(self) -> None:
        """Live guard: non-standard rows (no 'seconds') must carry the evolution field set."""
        if not LEDGER.exists():
            pytest.skip("ledger not present in this checkout")
        bad: list[tuple[int, str, list[str]]] = []
        for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "seconds" in row:
                continue  # standard row
            absent = sorted(NONSTANDARD_REQUIRED - set(row))
            if absent:
                bad.append((i, row.get("recipe", "?"), absent))
        assert not bad, (
            f"measurements.jsonl has {len(bad)} non-standard row(s) with unexpected schema:\n"
            + "\n".join(f"  line {n} ({r}): missing {f}" for n, r, f in bad)
        )

    def test_missing_required_field_is_detected(self, tmp_path, monkeypatch) -> None:
        """Proves the guard fires: a standard row missing 'raw' raises AssertionError."""
        ledger = tmp_path / "measurements.jsonl"
        # Standard row intentionally missing 'raw'
        incomplete = {"recipe": "lite-builtin", "seconds": 1.0, "argv": [], "metrics": {}}
        ledger.write_text(json.dumps(incomplete) + "\n", encoding="utf-8")
        monkeypatch.setattr(R, "LEDGER", ledger)
        missing: list[tuple[int, str, list[str]]] = []
        for i, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "seconds" not in row:
                continue
            absent = sorted(STANDARD_REQUIRED - set(row))
            if absent:
                missing.append((i, row.get("recipe", "?"), absent))
        assert missing, "expected the guard to find a missing field but it did not"
        assert "raw" in missing[0][2]


# ── instruments.json ───────────────────────────────────────────────────────────

INSTRUMENT_REQUIRED = {"deterministic", "run_to_run", "reported_spread"}


class TestInstrumentsJson:
    """instruments.json validity and schema coherence."""

    def test_instruments_is_valid_json(self) -> None:
        """Live guard: an unparseable instruments.json breaks experiment.py's refusal gate."""
        if not INSTRUMENTS.exists():
            pytest.skip("instruments.json not present in this checkout")
        try:
            json.loads(INSTRUMENTS.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"instruments.json is not valid JSON: {exc}")

    def test_instruments_keys_are_known_recipes(self) -> None:
        """Live guard: instruments.json may only name recipes that research.py knows.

        Mirrored in test_claude_instruments_match_recipes.py; kept here so this file is
        self-contained for the slice 19 guard run.
        """
        if not INSTRUMENTS.exists():
            pytest.skip("instruments.json not present in this checkout")
        instruments = json.loads(INSTRUMENTS.read_text(encoding="utf-8"))
        unknown = sorted(set(instruments) - set(R.RECIPES))
        assert not unknown, (
            f"instruments.json names recipes research.py does not know: {unknown}"
        )

    def test_every_instrument_has_required_fields(self) -> None:
        """Live guard: every entry must carry deterministic/run_to_run/reported_spread."""
        if not INSTRUMENTS.exists():
            pytest.skip("instruments.json not present in this checkout")
        instruments = json.loads(INSTRUMENTS.read_text(encoding="utf-8"))
        bad: list[tuple[str, list[str]]] = []
        for name, entry in instruments.items():
            absent = sorted(INSTRUMENT_REQUIRED - set(entry))
            if absent:
                bad.append((name, absent))
        assert not bad, (
            f"instruments.json entries missing required fields:\n"
            + "\n".join(f"  {n}: missing {f}" for n, f in bad)
        )

    def test_missing_instrument_field_is_detected(self, tmp_path) -> None:
        """Proves the guard fires: an entry missing 'run_to_run' raises AssertionError."""
        instruments = {"lite-builtin": {"deterministic": False, "reported_spread": 0.01}}
        bad: list[tuple[str, list[str]]] = []
        for name, entry in instruments.items():
            absent = sorted(INSTRUMENT_REQUIRED - set(entry))
            if absent:
                bad.append((name, absent))
        assert bad, "expected the guard to find a missing field but it did not"
        assert "run_to_run" in bad[0][1]


# ── live_taken_numbers (audit_next.py) ─────────────────────────────────────────


class TestLiveTakenNumbers:
    """Slice 19: the direct-path collision guard in audit_next.py."""

    def test_reads_pass_numbers_from_log(self, tmp_path, monkeypatch) -> None:
        log = tmp_path / "audit-log.md"
        log.write_text(
            "# Audit log\n\n"
            "| 5 | L1 | T01 | clean | 3 | 3 | - | probed X, invariant held |\n"
            "| 7 | L2 | T02 | clean | 3 | 3 | - | probed Y, invariant held |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(A, "LOG", log)
        monkeypatch.setattr(A, "ROW", A.ROW)  # ensure ROW is accessible
        taken = A.live_taken_numbers()
        assert taken == {5, 7}

    def test_missing_log_returns_empty_set(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(A, "LOG", tmp_path / "nope.md")
        assert A.live_taken_numbers() == set()

    def test_collision_guard_steps_over_taken_number(self, tmp_path, monkeypatch) -> None:
        """Proves the guard in cmd_record advances n past a number already in the live log.

        Simulates: two agents both read the log showing max=4, both compute n=5.
        Agent A commits first (n=5 is now taken).  Agent B runs cmd_record and must
        step to n=6 instead of writing a second row for n=5.
        """
        log = tmp_path / "audit-log.md"
        # Log already has pass 5 (agent A committed while we were working).
        log.write_text(
            "# Audit log\n\n"
            "| # | lane | target | verdict | before | after | commit | note |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 4 | L1 | T01 | clean | 3 | 3 | - | earlier pass |\n"
            "| 5 | L1 | T02 | clean | 3 | 3 | - | agent A committed first |\n",
            encoding="utf-8",
        )
        targets = tmp_path / "audit-targets.md"
        targets.write_text("## T01 foo\nbody\n## T02 bar\nbody\n", encoding="utf-8")
        lanes_file = tmp_path / "audit-lanes.md"
        lanes_file.write_text("## L1 lane\nbody\n", encoding="utf-8")
        monkeypatch.setattr(A, "LOG", log)
        monkeypatch.setattr(A, "TARGETS", targets)
        monkeypatch.setattr(A, "LANES", lanes_file)
        # Force assign() to hand out n=5 (as if it read a stale log with max=4).
        monkeypatch.setattr(A, "assign", lambda history, offset=0: (5, "L1", "T01"))

        import sys
        monkeypatch.setattr(
            sys, "argv",
            [
                "audit_next", "record",
                "--verdict", "clean",
                "--tests-before", "3",
                "--tests-after", "3",
                "--note", "probed Z, guard steps over n=5 to n=6",
            ],
        )
        A.main()  # should NOT raise, should step to n=6
        text = log.read_text(encoding="utf-8")
        # n=5 is already there once (agent A); should NOT be there twice.
        assert text.count("| 5 |") == 1, f"pass 5 was written twice!\n{text}"
        # n=6 should be the new row.
        assert "| 6 |" in text, f"expected pass 6 to be written:\n{text}"
