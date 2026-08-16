"""humanness() branches the scoring tests do not reach: the public type contracts,
the invisible-character caveat pass-through, and the erratic-burstiness penalty."""

from __future__ import annotations

import logging

import pytest

from untell import humanness as hum

LONG = (
    "The committee reviewed the proposal and approved the funding for the new project. "
    "Several members raised questions about the timeline before the vote. "
    "The final decision was recorded in the minutes. "
) * 4  # 60+ words, above the 40-word band floor


def test_bytes_text_is_refused_by_name() -> None:
    with pytest.raises(TypeError, match="text must be str, got bytes"):
        hum.humanness(b"hello world" * 5)


def test_a_non_str_tier_is_refused_by_name() -> None:
    with pytest.raises(TypeError, match="tier must be str, got list"):
        hum.humanness(LONG, tier=["lite"])


def test_invisible_character_caveat_is_forwarded(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        hum, "score_text",
        lambda text, tier="full": {"warning": "text contains invisible characters",
                                    "scored": True, "max": 0.1, "tier": tier},
    )
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        hum.humanness(LONG, tier="lite")
    assert any("invisible characters" in r.message for r in caplog.records)


def test_erratic_burstiness_costs_exactly_the_documented_penalty(monkeypatch) -> None:
    """cv > 1.0 applies the fixed 0.5 * _MAX_BURSTY_PENALTY term; cv in the ideal band
    applies nothing. The difference is 0.20 * 0.15 * 100 = 3.0 points."""

    def make(cv: float):
        monkeypatch.setattr(
            hum, "score_tells",
            lambda text, include_matches=False: {
                "language_supported": True,
                "tells_per_100w": 0.0,
                "burstiness_cv": cv,
                "by_category": {},
            },
        )
        monkeypatch.setattr(
            hum, "score_text",
            lambda text, tier="full": {"max": 0.0, "scored": True, "tier": tier},
        )
        return hum.humanness(LONG, tier="lite")

    erratic = make(1.2)
    ideal = make(0.9)
    assert erratic == round(ideal - 3.0, 1)
