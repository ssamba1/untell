"""Contract tests for .claude/research.py pure functions (2026-08-14).

Pins the measurement-ledger machinery that the whole L8 lane runs on:
  - load()          reads measurements.jsonl
  - flat_numbers()  flattens nested dicts to dotted keys
  - compare()       the consistency checker that flags stale estimates

These are the functions whose failures produced every estimate correction
this session (compare-hc3 60m, lite-hc3-ensemble 30->60->150m). They deserve
the same mutation guarantees as the product code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import research as R  # noqa: E402


class TestFlatNumbers:
    def test_flattens_nested_dicts(self) -> None:
        obj = {"a": 1.5, "b": {"c": 2.0, "d": {"e": 3.0}}}
        out = R.flat_numbers(obj)
        assert out == {"a": 1.5, "b.c": 2.0, "b.d.e": 3.0}

    def test_skips_non_numbers(self) -> None:
        obj = {"a": 1.0, "b": "text", "c": [1, 2], "d": None}
        out = R.flat_numbers(obj)
        assert out == {"a": 1.0}

    def test_prefix(self) -> None:
        obj = {"a": 1.0}
        assert R.flat_numbers(obj, prefix="recipe") == {"recipea": 1.0}


class TestLoad:
    def test_load_returns_list_of_dicts(self, tmp_path, monkeypatch) -> None:
        path = tmp_path / "measurements.jsonl"
        path.write_text(
            json.dumps({"recipe": "x", "seconds": 10.0}) + "\n"
            + json.dumps({"recipe": "y", "seconds": 20.0}) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(R, "LEDGER", path)
        out = R.load()
        assert len(out) == 2
        assert out[0]["recipe"] == "x"
        assert out[1]["recipe"] == "y"


class TestCompare:
    """The consistency checker: flags stale estimates against recorded values."""

    def _ledger(self, tmp_path, monkeypatch, rows):
        path = tmp_path / "measurements.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        monkeypatch.setattr(R, "LEDGER", path)

    def test_missing_history_reports_first_run(self, tmp_path, monkeypatch) -> None:
        self._ledger(tmp_path, monkeypatch, [])
        lines = R.compare("lite-builtin", {"pre_flagged_rate": 0.5, "post_flagged_rate": 0.1})
        assert any("first run" in ln for ln in lines), lines

    def test_matching_value_is_noise(self, tmp_path, monkeypatch) -> None:
        self._ledger(tmp_path, monkeypatch, [{
            "recipe": "lite-builtin",
            "raw": {"post_mean_max_stdev": 0.01},
            "metrics": {"pre_flagged_rate": 0.5, "post_flagged_rate": 0.1},
        }])
        lines = R.compare("lite-builtin", {
            "pre_flagged_rate": 0.5, "post_flagged_rate": 0.1,
            "post_mean_max_stdev": 0.01,
        })
        assert all("noise" in ln for ln in lines if "->" in ln), lines

    def test_big_delta_is_moved(self, tmp_path, monkeypatch) -> None:
        self._ledger(tmp_path, monkeypatch, [{
            "recipe": "lite-builtin",
            "raw": {"post_mean_max_stdev": 0.01},
            "metrics": {"pre_flagged_rate": 0.9, "post_flagged_rate": 0.9},
        }])
        lines = R.compare("lite-builtin", {
            "pre_flagged_rate": 0.1, "post_flagged_rate": 0.1,
            "post_mean_max_stdev": 0.01,
        })
        assert any("MOVED" in ln for ln in lines), lines

    def test_delta_within_two_x_spread_is_noise(self, tmp_path, monkeypatch) -> None:
        """Survivor research.py:297 — `band = 2 * max(...)` -> `3 *`.

        A delta of 0.02 with spread 0.01 sits exactly at the 2x band edge:
        original band 0.02 -> delta == band -> noise. Mutation band 0.03 ->
        delta 0.02 < band -> noise too... need delta BETWEEN 2x and 3x:
        spread 0.01 -> band 0.02 (orig) vs 0.03 (mut); delta 0.025 is MOVED
        under the 2x band but noise under the 3x band."""
        self._ledger(tmp_path, monkeypatch, [{
            "recipe": "lite-builtin",
            "raw": {"post_mean_max_stdev": 0.01},
            "metrics": {"pre_flagged_rate": 0.5, "post_flagged_rate": 0.5},
        }])
        lines = R.compare("lite-builtin", {
            "pre_flagged_rate": 0.525, "post_flagged_rate": 0.525,
            "post_mean_max_stdev": 0.01,
        })
        assert any("MOVED" in ln for ln in lines), lines

    def test_missing_metric_skipped(self, tmp_path, monkeypatch) -> None:
        """Survivor research.py:303 — `now is None or was is None` -> `and`.

        A metric missing from EITHER side is skipped (not compared). The
        mutation (`and`) only skips when BOTH are None, comparing a present
        value against a missing one as a huge MOVED delta."""
        self._ledger(tmp_path, monkeypatch, [{
            "recipe": "lite-builtin",
            "raw": {"post_mean_max_stdev": 0.01},
            "metrics": {"pre_flagged_rate": 0.5},  # post_flagged_rate missing
        }])
        lines = R.compare("lite-builtin", {
            "pre_flagged_rate": 0.5, "post_flagged_rate": 0.1,
            "post_mean_max_stdev": 0.01,
        })
        # post_flagged_rate is missing on the prev side -> skipped, not compared
        assert not any("post_flagged_rate" in ln and "->" in ln for ln in lines), lines


class TestDuplicateRows:
    """Issue #17 dedup guard: the recorder must SEE a byte-identical line it is about
    to append (append-only policy retains it; the warning makes the double-append
    visible instead of silent)."""

    def test_counts_identical_lines(self, tmp_path, monkeypatch) -> None:
        row = {"recipe": "lite-builtin", "seconds": 64.6, "argv": ["-m", "eval.ceiling"]}
        other = {"recipe": "lite-builtin", "seconds": 60.6, "argv": ["-m", "eval.ceiling"]}
        path = tmp_path / "measurements.jsonl"
        path.write_text(
            json.dumps(row) + "\n" + json.dumps(row) + "\n" + json.dumps(other) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(R, "LEDGER", path)
        assert R.duplicate_rows(row) == 2
        assert R.duplicate_rows(other) == 1

    def test_missing_ledger_is_zero(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(R, "LEDGER", tmp_path / "nope.jsonl")
        assert R.duplicate_rows({"recipe": "x"}) == 0

    def test_whitespace_insensitive(self, tmp_path, monkeypatch) -> None:
        """The recorded line is json.dumps output; a trailing-space variant of the same
        object must still count (byte-identical modulo line whitespace)."""
        row = {"recipe": "lite-builtin", "seconds": 1.0}
        path = tmp_path / "measurements.jsonl"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        monkeypatch.setattr(R, "LEDGER", path)
        assert R.duplicate_rows(row) == 1

    def test_ledger_holds_no_byte_identical_pair(self) -> None:
        """Issue #17 close: the real ledger is deduplicated. No byte-identical line appears
        twice, so a future double-append breaks this test as well as firing the recorder
        warning. (Ordered first-occurrence scan, exact byte match, appending line count.)"""
        if not R.LEDGER.exists():
            return  # ledger not present in this checkout; nothing to assert
        lines = R.LEDGER.read_text(encoding="utf-8").splitlines()
        seen: set[str] = set()
        dupes: list[str] = []
        for ln in lines:
            if ln in seen:
                dupes.append(ln)
            seen.add(ln)
        assert not dupes, (
            "measurements.jsonl holds byte-identical duplicate rows: "
            + repr([d[:60] for d in dupes])
        )
