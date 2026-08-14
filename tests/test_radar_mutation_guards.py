"""Killing tests for radar.py mutation survivors (2026-08-14 sweep).

  line 59  logic: or -> and      available/text guard — the opt-out must prevent
                                 the 7B model load entirely.

Killed here. The other 8 survivors (35/38/39/44/45/66/73 x2) are env/model-
dependent — annotated in survivors.md.

MEASURED: with the mutation applied, score("some real text here") with
UNTELL_ENABLE_RADAR unset LOADED the 7B model and returned 0.993 — a 5GB model
load on a machine where the detector is opted out. The original guard returns
None before any load. This is the "opt-in means opt-in" invariant.
"""

from __future__ import annotations

from untell.detectors.radar import RadarDetector


class TestOptInGuard:
    """Survivor radar.py:59 — `not available() or not text.strip()` mutated to `and`.

    With radar NOT enabled (available() False) and a non-empty text, score() must
    return None WITHOUT attempting a model load. The mutation (`and`) makes the
    guard False and falls through to _load() — a 5GB download/load on every call
    on a machine where the detector is opted out."""

    def test_opted_out_returns_none_without_loading(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_ENABLE_RADAR", raising=False)
        monkeypatch.delenv("HUMANIZE_ENABLE_RADAR", raising=False)
        d = RadarDetector()
        assert d.available() is False

        loaded = []

        def _boom(*a, **k):
            loaded.append(True)
            raise AssertionError("model load must not run when radar is opted out")

        monkeypatch.setattr(RadarDetector, "_load", _boom)
        assert d.score("some real text that is long enough to matter") is None
        assert not loaded, "opt-out must never reach _load()"
