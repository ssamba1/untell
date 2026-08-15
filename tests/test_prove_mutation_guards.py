"""Killing tests for eval/prove.py mutation survivors (2026-08-14 sweep).

  line 153  logic: or -> and        failure-detection gate in main's exit code.

Killed here via a monkeypatched prove() that returns an error result with a
configured after-block. Other survivors (34/108/134/140 x2) are CLI constants —
annotated in survivors.md.
"""

from __future__ import annotations

from eval import prove as P


class TestFailureGate:
    """Survivor prove.py:153 — `"error" in v or not after.configured` -> `and`.

    A result carrying an "error" key exits 2 regardless of configuration (the
    check failed). The mutation (`and`) only exits 2 when the error result is
    ALSO unconfigured — an error with configured:True falls through to the
    0/1 verdict on missing passes_all, returning 1 (a FAIL verdict) instead of
    2 (a CONFIG/ERROR verdict)."""

    def test_error_with_configured_after_exits_two(self, monkeypatch) -> None:
        # prove() returns an error but claims the checkers configured
        def _fake_prove(*a, **k):
            return {"error": "checker failed", "before": {}, "after": {"configured": True}}

        monkeypatch.setattr("eval.prove.prove", _fake_prove)
        # drive main() with a minimal argv (text is positional)
        rc = P.main(["sample text"])
        assert rc == 2, f"error result must exit 2 (got {rc})"
