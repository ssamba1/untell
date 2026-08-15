"""Killing tests for eval/benchmark.py mutation survivors (2026-08-14 sweep).

  line 68   membership: not in -> in   unknown-strategy filter.

Killed here. 42 (--n default) is an unkillable CLI constant.
"""

from __future__ import annotations

import pytest

from eval import benchmark as B


class TestUnknownStrategyFilter:
    """Survivor benchmark.py:68 — `s not in STRATEGIES` -> `s in STRATEGIES`.

    A KNOWN strategy must run the benchmark. The mutation flags every known
    strategy as unknown, exiting with a parser error instead of running."""

    def test_known_strategy_runs(self, monkeypatch, capsys) -> None:
        ran = {"called": False}

        def _run(dataset, n, tier, threshold, strategies):
            ran["called"] = True
            return {"full_loop": []}

        monkeypatch.setattr(B, "run", _run)
        monkeypatch.setattr(
            "eval.benchmark.render",
            lambda by, threshold: "rendered-report",
        )
        rc = B.main(["--dataset", "hc3", "--n", "1", "--tier", "lite", "--strategies", "full_loop"])
        assert rc == 0, f"known strategy must run, not error (rc={rc})"
        assert ran["called"], "run() must be invoked for a known strategy"
