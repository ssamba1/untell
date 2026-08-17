"""Per-phase budget tracking for the rewrite loop (issue #27).

MEASURED at wave 3 (1MB document, full loop): the rewrite phase took 462.7s of a
467.4s loop — 99.5% of the wall clock — while the initial score and the per-draw
rescore cost ~2s together. A regression in any phase is invisible unless each
phase is reported separately, which is what `untell_text(timings=True)` and the
CLI `--timings` flag exist to surface.

This file pins the SHAPE of the report, not the absolute numbers (those are
machine- and text-dependent):

- the phase split is present and in EXECUTION order — score_pre first, the
  per-iteration phases in the order the loop runs them, total last
- the buckets are complete: the whole-body `total` covers at least the sum of
  the phases (they are disjoint sub-intervals of the body; lock/scrub/restore
  are the un-bucketed rest)
- the rewrite phase dominates — it is the largest single bucket and more than
  half the total, on a text long enough that the fixed per-call overhead
  (locking, sentence split) does not swamp it. If a scoring or targeting
  regression ever makes another phase catch up, that IS the signal the report
  exists to surface, and this test starts failing.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

from untell.scripts.run import untell_text

# The demo sample from cli.py, repeated so the rewrite phase dominates the
# fixed per-call overhead (measured: ~70% rewrite share at this size, ~28% at
# one copy). Scores well above any reasonable threshold at lite tier, so the
# loop is forced to run its single rewrite iteration.
_SAMPLE = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations increasingly leverage these technologies to optimize operational "
    "efficiency and drive innovation. Overall, the transformative impact continues to expand "
    "across various sectors. In addition, researchers emphasize that data-driven decision making "
    "represents a critical advantage for modern enterprises. Consequently, the adoption of these "
    "systems is expected to accelerate in the coming years. "
)
TEXT = _SAMPLE * 3

# threshold=0.001: the sample scores far above it, so the loop cannot declare a
# pass before iterating — the rewrite and rescore phases are guaranteed to run.
KWARGS = dict(
    tier="lite",
    threshold=0.001,
    rewriter="composite",
    best_of=1,
    max_iters=1,
    seed=7,
    timings=True,
)

EXPECTED_KEYS = [
    "score_pre",
    "targeting",
    "rewrite",
    "similarity",
    "rescore",
    "tells",
    "polish",
    "total",
]


def _warm_detectors() -> None:
    """Load the lite detector stack so its one-time cost lands OUTSIDE the run.

    The score cache is cleared per test by conftest's autouse fixture, but the
    detector modules themselves load once per process; warming them on a text
    that is not TEXT keeps the measured run's `score_pre` a real (warm) score.
    """
    from untell.scripts.score import score_text

    score_text("warm the detector stack on a throwaway line.", tier="lite")


def test_timings_key_is_present_in_canonical_order(stdlib_lite) -> None:
    _warm_detectors()
    result = untell_text(TEXT, **KWARGS)
    timings = result.get("timings")
    assert timings is not None, "timings=True must attach the phase report to the result"
    assert list(timings) == EXPECTED_KEYS, (
        "phase order is execution order (score_pre first, total last); got "
        f"{list(timings)}"
    )


def test_phase_values_are_finite_non_negative_and_complete(stdlib_lite) -> None:
    _warm_detectors()
    timings = untell_text(TEXT, **KWARGS)["timings"]
    for name, seconds in timings.items():
        assert isinstance(seconds, float), f"{name}: {seconds!r}"
        assert seconds >= 0 and math.isfinite(seconds), f"{name}: {seconds}"
    assert timings["total"] > 0
    phases = [seconds for name, seconds in timings.items() if name != "total"]
    # The buckets are disjoint sub-intervals of the body, so the whole-body total
    # must cover at least their sum (locking/scrubbing/restore are the rest).
    assert timings["total"] >= sum(phases) - 1e-9, timings


def test_the_loop_actually_ran(stdlib_lite) -> None:
    _warm_detectors()
    result = untell_text(TEXT, **KWARGS)
    timings = result["timings"]
    assert result["rewrites"] >= 1, "the loop must have drawn a rewrite"
    assert timings["rewrite"] > 0, "a rewrite happened but the bucket is empty"
    assert timings["rescore"] > 0, "the candidate was scored but the bucket is empty"


def test_rewrite_dominates_the_phase_split(stdlib_lite) -> None:
    """The split shape the issue measured: rewrite is the cost, by far.

    462.7s of 467.4s (99.5%) at 1MB; on this small text the share is lower but
    still the headline — the largest bucket and more than half the total. If the
    rewrite ever stops dominating, either the rewrite got cheaper (good — but
    re-derive the shape) or another phase regressed (the case this exists to
    catch).
    """
    _warm_detectors()
    timings = untell_text(TEXT, **KWARGS)["timings"]
    assert timings["rewrite"] > timings["score_pre"], timings
    assert timings["rewrite"] > timings["rescore"], timings
    assert timings["rewrite"] == max(
        seconds for name, seconds in timings.items() if name != "total"
    ), timings
    assert timings["rewrite"] > 0.5 * timings["total"], timings


def test_the_cli_flag_emits_the_split_as_json(stdlib_lite) -> None:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["UNTELL_LITE_NO_TORCH"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "untell.scripts.run", "--timings", "--json",
         "--tier", "lite", "--rewriter", "composite", "--best-of", "1",
         "--max-iters", "1", "--threshold", "0.001", TEXT],
        capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == 0, (proc.stdout[:300], proc.stderr[:300])
    payload = json.loads(proc.stdout)
    timings = payload.get("timings")
    assert timings is not None, "untell humanize --timings --json must carry the timings dict"
    assert list(timings) == EXPECTED_KEYS
    assert timings["rewrite"] > 0.5 * timings["total"], timings


def test_the_cli_flag_prints_a_human_summary_without_json(stdlib_lite) -> None:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["UNTELL_LITE_NO_TORCH"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "untell.scripts.run", "--timings",
         "--tier", "lite", "--rewriter", "composite", "--best-of", "1",
         "--max-iters", "1", "--threshold", "0.001", TEXT],
        capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == 0, (proc.stdout[:300], proc.stderr[:300])
    assert "[timings]" in proc.stdout, proc.stdout[-500:]
    assert "rewrite" in proc.stdout and "total" in proc.stdout


def test_without_the_flag_the_payload_is_unchanged(stdlib_lite) -> None:
    """`timings` is opt-in: every existing caller's result stays byte-identical."""
    plain = untell_text(TEXT, tier="lite", threshold=0.3, rewriter="structural", seed=1)
    assert "timings" not in plain, "default run must not carry the timings key"

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["UNTELL_LITE_NO_TORCH"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "untell.scripts.run", "--json",
         "--tier", "lite", "--rewriter", "composite", "--best-of", "1",
         "--max-iters", "1", TEXT],
        capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == 0, (proc.stdout[:300], proc.stderr[:300])
    assert "timings" not in json.loads(proc.stdout)
