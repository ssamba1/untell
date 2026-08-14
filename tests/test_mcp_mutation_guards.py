"""Killing tests for the mcp_server.py mutation survivors (2026-08-14 sweep).

  line 75   boundary: <= -> <     seed range upper bound (2**64 - 1).

Killed here. 246 (rewriter rejection `and` -> `or`) is unkillable by construction:
every observable path converges — free names resolve identically through the
untell_text name-resolution, "auto" is converted to None at run.py:768, and
unknown names error identically. 297 (sandbox default) needs live commercial
API keys. Both recorded as unkillable in survivors.md.
"""

from __future__ import annotations

from untell import mcp_server as M


class TestSeedBoundary:
    """Survivor mcp_server.py:75 — `0 <= int(value) <= 2**64 - 1` mutated to `<`.

    A seed of exactly 2**64 - 1 (the documented upper bound) is valid. The
    mutation would reject it."""

    def test_seed_at_upper_bound_is_valid(self) -> None:
        out = M._bad_args(seed=(2**64 - 1, "seed"))
        assert out is None

    def test_seed_above_upper_bound_is_rejected(self) -> None:
        out = M._bad_args(seed=(2**64, "seed"))
        assert out is not None
        assert "outside" in out["error"]

    def test_negative_seed_is_rejected(self) -> None:
        out = M._bad_args(seed=(-1, "seed"))
        assert out is not None


class TestNonNumericInput:
    """Non-numeric strings must be refused as dicts, not crash with a traceback.

    The conversions in `_bad_args` (float()/int()) are unguarded for the numeric kinds, and the
    docstring's whole point is that an MCP client can send ANYTHING — `tier="fulll"` or
    `threshold=50` were the shapes that motivated this function, and `threshold="abc"` crashed it
    with ValueError instead of refusing. An MCP client then saw a traceback rather than the
    refusal dict every other out-of-range answer returns.
    """

    def test_non_numeric_threshold_is_refused(self) -> None:
        out = M._bad_args(threshold=("abc", "probability"))
        assert out is not None
        assert "not a number" in out["error"]

    def test_non_numeric_count_is_refused(self) -> None:
        out = M._bad_args(max_subs=("many", "count"))
        assert out is not None
        assert "not a number" in out["error"]

    def test_non_numeric_top_is_refused(self) -> None:
        out = M._bad_args(top=("all", "top"))
        assert out is not None
        assert "not a number" in out["error"]

    def test_non_numeric_seed_is_refused(self) -> None:
        out = M._bad_args(seed=("random", "seed"))
        assert out is not None
        assert "not a number" in out["error"]

    def test_none_threshold_is_refused(self) -> None:
        out = M._bad_args(threshold=(None, "probability"))
        assert out is not None

    def test_valid_values_still_pass(self) -> None:
        assert M._bad_args(threshold=(0.3, "probability")) is None
        assert M._bad_args(max_subs=(12, "count")) is None
        assert M._bad_args(seed=(42, "seed")) is None
