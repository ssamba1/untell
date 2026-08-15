"""Killing tests for eval/ceiling.py mutation survivors (2026-08-14 sweep).

  line 148  logic: or -> and       parallel gate (workers>1 AND len>1 AND name).
  line 239  logic: is-not -> is    scored-flag inclusion (`scored is not False`).

Killed here. Other survivors (148-boundary TIMEOUT = infinite loop on degenerate
input, 254/265 killed by suite, 89 killed by suite) annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from eval.ceiling import _each_text, measure_ceiling


class TestParallelGate:
    """Survivor eval/ceiling.py:148 — `parallel_ok` mutated `and` -> `or`.

    workers=1 must force the serial path (nothing to gain). The mutation makes
    `workers and (workers > 1 or ...)` truthy when workers=1, starting a pool
    that would raise (fake pool). The serial path must yield per-text results."""

    def test_serial_path_used_when_workers_one(self, monkeypatch) -> None:
        started = {"pool": False}

        class _FakePool:
            def __init__(self, **kw):
                started["pool"] = True
                raise AssertionError("pool must not start for workers=1")

        monkeypatch.setattr(
            "concurrent.futures.ProcessPoolExecutor", _FakePool
        )
        # workers=1, 2 texts, name present: original -> serial; mutation -> pool
        gen = _each_text(["a", "b"], "lite", 0.5, 1, "structural", 3, 1)
        try:
            next(gen)
        except StopIteration:
            pass
        assert not started["pool"]


class TestScoredFlagInclusion:
    """Survivor eval/ceiling.py:239 — `post.get("scored") is not False` -> `is not True`.

    A result with `scored=True` must be INCLUDED in post_max/run_posts. The
    mutation (`is not True`) excludes it, undercounting the mean."""

    def test_scored_true_included_in_mean(self, monkeypatch) -> None:
        # Drive measure_ceiling's aggregation with a stubbed _each_text whose
        # result carries scored=True; run_post_means must reflect the 0.3 post.
        from eval import ceiling as C

        res = {
            "pre": {"max": 0.5, "mean": 0.5},
            "post": {"max": 0.3, "mean": 0.3, "scored": True},
            "rewrites": 1,
            "final": "changed text",
            "similarity": 0.9,
        }

        def _fake_each(*a, **k):
            return iter([("text", {"max": 0.5, "mean": 0.5}, res)])

        monkeypatch.setattr(C, "_each_text", _fake_each)
        out = C.measure_ceiling(["some text"], tier="lite", threshold=0.5)
        # post max 0.3 with scored=True must be included -> run_post_means = [0.3]
        assert out["run_post_means"] == [0.3], out
