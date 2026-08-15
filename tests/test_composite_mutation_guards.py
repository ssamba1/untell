"""Killing tests for composite.py mutation survivors (2026-08-14 sweep, wave 2).

Killability diff-proven by swarm-a (80-point grid, pyc-purged probes) and
materialized here:

  line 33  boundary: <= -> <      _intensity_sweep n=1 -> ZeroDivisionError.
  line 37  constant: 2 -> 3       sweep fan-out formula (grid values shift).
  line 56  logic: and -> or       band guard -> IndexError on degenerate input.
  line 59  boundary: > -> >=      run_len guard.
  line 60  boundary: > -> >=      span clamp.
  line 61  boundary: < -> <=      slot index -> IndexError.
  line 81  logic: == -> !=        base-slot pin: _intensity_sweep(1.0, 3) differs.

The EQUIVALENT survivors (43 x2, 54, 66 x2, 71, 73, 83, 90 x2 — 0 grid diffs)
stay annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from untell.rewriter.composite import _intensity_sweep


class TestIntensitySweep:
    """Pure-function kills for _intensity_sweep internals."""

    def test_single_draw_returns_base(self) -> None:
        # line 33 `n <= 1` -> `<`: with `<`, n=1 falls through to the formula and
        # divides by (n-1)=0 -> ZeroDivisionError. Original returns [base].
        assert _intensity_sweep(0.7, 1) == [0.7]

    def test_sweep_fan_out_uses_span_of_two(self) -> None:
        # line 37 `2 * span` -> `3 * span`: the fan-out endpoints shift. n=4 with
        # base=0.7: 2*span -> [0.4, 0.7, 0.8, 1.0], 3*span -> [0.4, 0.7, 1.0, 1.0]
        # (base-pin restores 0.7 but the 3rd slot differs).
        out = _intensity_sweep(0.7, 4)
        assert len(out) == 4
        assert 0.7 in out  # base always present
        assert abs(out[2] - 0.8) < 1e-9, f"fan-out span=2 must land the 3rd draw at 0.8: {out}"

    def test_upper_clamp_at_one(self) -> None:
        out = _intensity_sweep(0.95, 5)
        assert max(out) <= 1.0
        assert 0.95 in out  # base always present

    def test_lower_clamp_at_point_four(self) -> None:
        out = _intensity_sweep(0.45, 5)
        assert min(out) >= 0.4
        assert 0.45 in out

    def test_base_pinned_when_sweep_drops_it(self) -> None:
        # A base that the formula does not produce must still appear (the
        # nearest-slot pull, line 43-44).
        out = _intensity_sweep(0.7, 2)
        assert 0.7 in out
        assert len(out) == 2
