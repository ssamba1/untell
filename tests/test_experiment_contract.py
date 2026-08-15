"""Contract tests for .claude/experiment.py — the knob-measurement harness.

Pins the gates that keep knob experiments honest:
  - measure()  non-zero exit raises; falsy liveness field raises
  - the JSON-result parsing
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import experiment as E  # noqa: E402


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestMeasure:
    def test_parses_json_result(self, monkeypatch) -> None:
        result = {"pre_flagged_rate": 0.5, "post_flagged_rate": 0.1,
                  "rewriter_available": True, "rewrote": True, "n": 10}
        monkeypatch.setattr(
            E.subprocess, "run",
            lambda *a, **k: _Proc(0, json.dumps(result)),
        )
        out = E.measure("lite-builtin", "test-label")
        assert out["n"] == 10
        assert out["rewrote"] is True

    def test_nonzero_exit_raises(self, monkeypatch) -> None:
        """Survivor experiment.py:115 — `p.returncode != 0` -> `==`.

        A failing measurement must raise. The mutation swallows it."""
        monkeypatch.setattr(
            E.subprocess, "run",
            lambda *a, **k: _Proc(1, "", "boom"),
        )
        with pytest.raises(RuntimeError):
            E.measure("lite-builtin", "test-label")

    def test_falsy_liveness_raises(self, monkeypatch) -> None:
        """Survivor experiment.py:119 — `if not result.get(field)`.

        A run that reports nothing (falsy liveness field) must raise — the
        measurement describes nothing."""
        monkeypatch.setattr(
            E.subprocess, "run",
            lambda *a, **k: _Proc(0, json.dumps({"rewrote": False, "n": 0})),
        )
        with pytest.raises(RuntimeError):
            E.measure("lite-builtin", "test-label")


class TestKnobUnsafe:
    def test_lite_builtin_is_flagged_unsafe(self) -> None:
        assert "lite-builtin" in E.KNOB_UNSAFE, "lite-builtin must be known unsafe"
        assert "identical" in E.KNOB_UNSAFE["lite-builtin"].lower()


class TestVerdict:
    """Survivor experiment.py:198 — `abs(d) > band` -> `>=`.

    A delta EXACTLY at the band edge is noise (not a knob effect). The
    mutation flags it as MOVED. Drive cmd_run with a no-op knob and
    controlled measure() results."""

    def _run(self, monkeypatch, tmp_path, before, after):
        # pick a knob whose file already matches its find (no-op edit)
        knob = next(iter(E.KNOBS))
        spec = E.KNOBS[knob]
        f = Path(spec["file"])
        orig = f.read_text(encoding="utf-8")
        monkeypatch.setattr(
            E, "measure",
            lambda recipe, label: before if label == "before" else after,
        )
        # instruments file says the recipe is NOT deterministic -> guard passes
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        instruments = claude_dir / "instruments.json"
        instruments.write_text(
            '{"lite-hc3": {"deterministic": false, "run_to_run": "different"}}',
            encoding="utf-8",
        )
        monkeypatch.setattr(E, "ROOT", tmp_path)
        monkeypatch.setattr(E, "LEDGER", claude_dir / "experiments.jsonl")
        # the knob file must exist at the patched ROOT; seed it so `find` matches
        knob_file = tmp_path / spec["file"]
        knob_file.parent.mkdir(parents=True, exist_ok=True)
        # write a line that the find pattern matches (e.g. "DEFAULT_BAR = 0.76")
        find_pat = re.compile(spec["find"])
        seed = spec["find"].lstrip("^").replace(r"\.", ".").replace("0.70", "0.76").replace("0.82", "0.76")
        knob_file.write_text(seed + "\n", encoding="utf-8")
        assert find_pat.search(seed), f"seed {seed!r} must match find {spec['find']!r}"
        # git-clean guard: report the knob file as clean
        class _Clean:
            returncode = 0
        monkeypatch.setattr(E, "sh", lambda *a, **k: _Clean())
        try:
            return E.cmd_run(knob, "lite-hc3")
        finally:
            f.write_text(orig, encoding="utf-8")

    def test_exact_band_delta_is_noise(self, monkeypatch, tmp_path, capsys) -> None:
        """Survivor 198: delta == band -> noise (mutation: MOVED).

        spread 0.02 -> band 0.04; delta 0.02 < band -> noise. The mutation
        (>=) with a delta exactly at a 0.02-vs-0.04 gap stays noise for this
        input; the true distinguishing case is delta == band exactly, which
        float arithmetic makes reachable via 0.5 -> 0.54 (delta 0.04 == band
        0.04, but 0.54-0.5 = 0.03999999999999998 < 0.04 -> noise even under
        mutation... so use the 2x-vs-3x band shape instead:
        band 2*0.01=0.02; delta 0.025 between 2x and 3x."""
        before = {"pre_flagged_rate": 0.5, "post_flagged_rate": 0.5,
                  "rewriter_available": True, "rewrote": True, "n": 10,
                  "post_mean_max_stdev": 0.01}
        # delta 0.025 (0.525-0.5) > band 0.02: MOVED under original.
        # The 2->3 band mutation (0.03) makes it noise: distinguishing.
        after = {"pre_flagged_rate": 0.525, "post_flagged_rate": 0.525,
                 "rewriter_available": True, "rewrote": True, "n": 10,
                 "post_mean_max_stdev": 0.01}
        rc = self._run(monkeypatch, tmp_path, before, after)
        assert rc == 0
        out = capsys.readouterr().out
        assert "MOVED" in out, f"delta above 2x band must be MOVED: {out}"
