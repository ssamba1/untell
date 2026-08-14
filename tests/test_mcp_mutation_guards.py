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
