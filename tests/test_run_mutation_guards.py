"""Killing tests for the run.py mutation survivors (2026-08-14 sweep).

  line 1614  logic: or -> and      env-config numeric range check.
  line 1676  boundary: <= -> <     argparse bounded-value range check.
  line 1883  logic: == -> !=       `--rewriter base` CLI dispatch.

1614 and 1676 are killed here via exact-boundary values. 1883 requires a torch
install (the base path needs transformers) — recorded as environment-dependent.
The other seven survivors (196 saturation guard, 910 no-signal pass, 1115 near-pool
objective, 1196 browser-tier, 1305/1308 warning composition, 1886 adapter flag) are
loop-internal branches that need a live rewrite cycle or a model runtime to reach —
recorded as unkillable-by-construction in survivors.md.
"""

from __future__ import annotations

from untell.scripts import run as R


class TestEnvConfigRangeBoundaries:
    """Survivor run.py:1614 — `if numeric is None or not (low <= numeric <= high)`
    mutated to `and`.

    A configured value EXACTLY at the range boundary must be accepted. The `or -> and`
    mutation makes the guard require BOTH `numeric is None` AND out-of-range, so an
    out-of-range value would sail through — and an exactly-boundary value must still
    be accepted (the `<=` on both sides is the contract)."""

    def test_threshold_at_high_boundary_is_accepted(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_THRESHOLD", "1.0")  # exactly the [0.0, 1.0] high edge
        out = R._config_defaults()
        assert out["threshold"] == 1.0

    def test_threshold_at_low_boundary_is_accepted(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_THRESHOLD", "0.0")  # exactly the low edge
        out = R._config_defaults()
        assert out["threshold"] == 0.0

    def test_threshold_below_range_is_rejected(self, monkeypatch, capsys) -> None:
        monkeypatch.setenv("UNTELL_THRESHOLD", "-0.5")
        out = R._config_defaults()
        assert out["threshold"] == R._CLI_DEFAULTS["threshold"]  # fell back to shipped
        assert "ignoring configured" in capsys.readouterr().err


class TestArgparseBoundary:
    """Survivor run.py:1676 — `if not (low <= value <= high)` mutated to `<`.

    A CLI value exactly at the boundary is valid. The mutation would reject it."""

    def test_parser_accepts_boundary_value(self) -> None:
        parser = R.build_parser()
        # threshold=1.0 is the exact high edge of [0.0, 1.0]
        ns = parser.parse_args(["--threshold", "1.0", "some text"])
        assert ns.threshold == 1.0
