"""Two documents in eight scored every sentence at exactly 0.9992, and "the worst third" was a sort.

The near-chance targeting caveat fires when the only scorer is the stdlib heuristic. That asks
whether the DETECTOR is any good. The question a caller actually needs answered is whether THIS
document's sentences can be ordered at all, and those come apart.

MEASURED at tier=full, spread of per-sentence `max` within one AI document, 10 documents per corpus:

    corpus   mean spread   median   below 0.05   distinct values / sentences
    HC3        0.0088      0.0022      9 / 10            0.36
    RAID       0.6595      0.6855      0 / 10            0.99

Same tier, same detectors, opposite answers. On HC3 two documents in eight returned **one distinct
value across eight sentences**; on RAID the ranking is almost perfect. The difference is
`hc3_roberta`, fine-tuned on HC3 and therefore at its ceiling on every sentence of it.

So tier is the wrong condition in both directions, and the document's own spread is the right one:
corpus-independent, needing no knowledge of what any detector was trained on, and firing exactly when
the order cannot be trusted. 0.05 sits in the empty gap — HC3's worst document reaches 0.0610 and
every RAID document exceeds 0.5.

Verified on the corpora after wiring: fired on 7/8 HC3 documents and 0/8 RAID.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.sentences import (
    _MIN_SENTENCES_FOR_SPREAD,
    _TARGETING_SPREAD_BAR,
    _targeting_is_unrankable,
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _rows(*scores: float) -> list[dict]:
    return [{"ai": s, "text": f"sentence {i}", "flagged": False} for i, s in enumerate(scores)]


def test_identical_scores_are_unrankable() -> None:
    """The measured case: eight sentences, one distinct value."""
    assert _targeting_is_unrankable(_rows(*[0.9992] * 8))


def test_a_negligible_spread_is_unrankable() -> None:
    """HC3's typical shape — everything at the ceiling, differing in the fourth decimal."""
    assert _targeting_is_unrankable(_rows(0.9992, 0.9969, 0.9971, 0.9954, 0.9992))


def test_a_real_spread_is_rankable() -> None:
    """RAID's shape. Guards the guard: a check that always fired would make the caveat worthless."""
    assert not _targeting_is_unrankable(_rows(0.95, 0.62, 0.31, 0.08, 0.77))


def test_the_bar_sits_between_the_two_measured_populations() -> None:
    """HC3's worst document spreads 0.0610; every RAID document exceeds 0.5. A bar outside that gap
    either stops warning on unrankable text or starts warning on rankable text."""
    assert 0.0 < _TARGETING_SPREAD_BAR < 0.5


def test_too_few_sentences_to_judge_is_not_a_claim() -> None:
    """Two sentences always have a spread; calling that rankable or not is noise either way, and a
    caveat fired on every two-sentence input is a caveat nobody reads."""
    assert not _targeting_is_unrankable(_rows(0.9992, 0.9992))
    assert _MIN_SENTENCES_FOR_SPREAD >= 3


def test_the_result_carries_it(monkeypatch) -> None:
    """Wired in, not merely defined. Driven through `score_sentences` with a stub scorer so it needs
    no models — the numbers are the measured HC3 shape."""
    import untell.scripts.sentences as mod

    pinned = [{"max": 0.9992, "flagged": True, "detector_modes": {"hc3_roberta": "model"}}] * 4
    monkeypatch.setattr(mod, "batch_score_texts", lambda texts, **kw: pinned[: len(texts)])
    monkeypatch.setattr(mod, "_targeting_is_uninformative", lambda tier, modes=None: False)
    result = mod.score_sentences(
        "One sentence here. Another sentence here. A third one here. And a fourth one.",
        tier="full",
    )
    assert result.get("unrankable") is True
    assert "not rankable" in (result.get("warning") or "")


def test_a_rankable_document_says_nothing(monkeypatch) -> None:
    import untell.scripts.sentences as mod

    spread = [
        {"max": v, "flagged": v >= 0.3, "detector_modes": {"hc3_roberta": "model"}}
        for v in (0.95, 0.60, 0.20, 0.05)
    ]
    monkeypatch.setattr(mod, "batch_score_texts", lambda texts, **kw: spread[: len(texts)])
    monkeypatch.setattr(mod, "_targeting_is_uninformative", lambda tier, modes=None: False)
    result = mod.score_sentences(
        "One sentence here. Another sentence here. A third one here. And a fourth one.",
        tier="full",
    )
    assert "unrankable" not in result
    assert not result.get("warning")
