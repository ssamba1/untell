"""Killing tests for the humanness.py mutation survivors (2026-08-14 sweep).

  line 214  logic: or -> and       undetermined_reason empty-text guard.
  line 288  logic: or -> and       humanness empty-text guard.
  line 605  boundary: >= -> >      _dominant_signal detector_max exactly 0.5.

Killed here. The CV band edges (368/370/372) are unkillable: the mid-band formula
`MAX * (0.50 - cv) / 0.15` is continuous with the neighbouring bands at every edge
(0.35 -> MAX*1.0 == MAX; 0.50 -> 0; 1.00 -> no penalty in either band), so no
input distinguishes `<` from `<=`. 75 (_WARNED_TOO_SHORT) is a warning latch with
no observable output change.
"""

from __future__ import annotations

from untell import humanness as H


class TestEmptyTextGuards:
    """Survivors 214/288 — `not text or not text.strip()` mutated to `and`.

    Empty or whitespace-only text must be reported as empty/neutral. The mutation
    requires BOTH conditions, so empty text falls through to the scoring path."""

    def test_undetermined_reason_empty(self) -> None:
        assert H.undetermined_reason("") == "empty"
        assert H.undetermined_reason("   ") == "empty"

    def test_humanness_empty_is_neutral(self) -> None:
        assert H.humanness("", tier="lite") == 50.0
        assert H.humanness("   ", tier="lite") == 50.0


class TestDominantSignalBoundary:
    """Survivor humanness.py:605 — `detector_max >= 0.5` mutated to `>`.

    A detector max exactly 0.5 names the ensemble as the dominant signal. The
    mutation would fall through to None."""

    def test_detector_max_exactly_half_names_the_ensemble(self, monkeypatch) -> None:
        monkeypatch.setattr(H, "score_tells", lambda t, **k: {"tells": 0, "by_evidence": {}})
        monkeypatch.setattr(H, "score_text", lambda t, **k: {"max": 0.5, "flagged": True})
        out = H._dominant_signal("The committee reviewed the findings across every site.", "lite")
        assert out is not None
        assert "detector ensemble" in out
