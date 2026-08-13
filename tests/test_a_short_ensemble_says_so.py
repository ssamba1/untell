"""One environment variable turned a 1.0 into 0.17, and the verdict from AI into clear.

FOUND by asking the product form of Result 198's question: the test suite now names the ambient
scoring settings, but does a USER see which detectors ran? MEASURED on one paragraph at
`--tier full`, the only difference being a variable the README's own reproduce command sets:

    complete ensemble        5 detectors    max 1.0000    flagged True
    UNTELL_DISABLE_MAGE=1    4 detectors    max 0.1722    flagged False

Same text, same command, definitely-AI to clear. The `detectors` dict does list what ran, so a
careful reader could notice the absence — but `flagged` is the headline and nothing qualified it.

**Three ways to be absent, and only two were covered.** `failed_detectors` names the ones that
loaded and raised. The abstention note covers the ones that loaded and returned None, and says
outright that "a missing detector can only lower `max` — this verdict errs toward NOT flagged". A
detector that was never selected — no model file, no key, or a documented opt-out — took neither
path, because `available()` returning False is not an error anywhere.

The tier-mismatch branch did not fire either: with four of five detectors the effective tier is
still `full`, so nothing was downgraded and nothing was said.

**Opt-in detectors are excluded, and the first version got that wrong.** It reported "ran without
radar" on a COMPLETE ensemble, because `radar` arrives only via `UNTELL_ENABLE_RADAR` and its
absence is the shipped configuration. `mage` is the other kind: it ships enabled and leaves via
`UNTELL_DISABLE_MAGE=1`. Only a member that went missing is news.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import _OPT_IN_DETECTORS, _short_roster_note

TEXT = "Salt lowers the freezing point of water, which is why councils spread it on winter roads."


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_missing_member_is_named(monkeypatch) -> None:
    """`mage` is opt-OUT: it ships enabled, so its absence is a reduced ensemble."""
    import untell.detectors.base as base

    class _Absent:
        name, tier = "mage", "full"

        def available(self) -> bool:
            return False

    monkeypatch.setattr(base, "all_detectors", lambda: [_Absent()])
    note = _short_roster_note("full", "full", {"perplexity_burstiness": 0.4})
    assert note and "mage" in note


def test_it_says_which_way_the_error_runs() -> None:
    """The direction is the point. Fewer members can only lower `max`, so the whole error is toward
    NOT flagged — telling someone their AI text reads as human, which is the expensive direction."""
    import untell.detectors.base as base

    class _Absent:
        name, tier = "mage", "full"

        def available(self) -> bool:
            return False

    original = base.all_detectors
    base.all_detectors = lambda: [_Absent()]
    try:
        note = _short_roster_note("full", "full", {}) or ""
    finally:
        base.all_detectors = original
    assert "make text look MORE human" in note


def test_an_opt_in_detector_is_not_a_missing_member(monkeypatch) -> None:
    """Guards the guard, with the exact false positive the first version shipped: `radar` is absent
    on every default install, so naming it would put this caveat on every full-tier run."""
    import untell.detectors.base as base

    class _OptIn:
        name, tier = "radar", "full"

        def available(self) -> bool:
            return False

    monkeypatch.setattr(base, "all_detectors", lambda: [_OptIn()])
    assert _short_roster_note("full", "full", {}) is None


def test_the_opt_in_set_is_not_empty() -> None:
    """If this ever emptied, the assertion above would pass for the wrong reason."""
    assert "radar" in _OPT_IN_DETECTORS


@pytest.mark.parametrize("tier", ["lite", "commercial"])
def test_lite_says_nothing(tier: str) -> None:
    """On lite, "the others are absent" is the definition of the tier rather than news."""
    assert _short_roster_note(tier, tier, {}) is None


def test_a_detector_that_scored_is_not_missing(monkeypatch) -> None:
    """It is keyed on the scores actually returned, so a detector that ran is never reported absent
    even if `available()` turns false afterwards."""
    import untell.detectors.base as base

    class _Absent:
        name, tier = "mage", "full"

        def available(self) -> bool:
            return False

    monkeypatch.setattr(base, "all_detectors", lambda: [_Absent()])
    assert _short_roster_note("full", "full", {"mage": 0.9}) is None


def test_a_broken_registry_does_not_break_scoring(monkeypatch) -> None:
    """A caveat must never break the score it qualifies."""
    import untell.detectors.base as base

    def _boom():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(base, "all_detectors", _boom)
    assert _short_roster_note("full", "full", {}) is None
