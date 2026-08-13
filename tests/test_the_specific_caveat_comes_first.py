"""Every run carries a warning, so the note that matters was arriving 500 characters in.

FOUND by checking whether the caveats added across this session compose or mask each other. They
compose — up to three fire together on one document and none is dropped. The measurement that
mattered was the other one.

MEASURED over 120 corpus texts (HC3 and RAID, both halves) at `tier=lite`:

    texts with an EMPTY warning        0 / 120
    warning length                     median 503, p90 882, max 882
    tier caveat                      120 / 120
    human-false-positive note         46 / 120
    every other caveat                 0 / 120

The four caveats added this session fire on none of the corpus, which is what their bars were
calibrated for. The tier caveat fires on every single run. It is correct and it is wallpaper, and it
was in front — so a reader who stops after the first sentence, which is what people do with a note
they have seen a hundred times, never reached the one specific to their input.

The worst case was the threshold caveat: it says the caller's setting passes everything, and it was
arriving behind "Also:", 500 characters in.

**The first attempt at this fixed nothing and would have shipped a false comment.** Reordering the
merge tuple changed no output, because the tier notes were assigned straight to `result["warning"]`
in an if/elif chain BEFORE the loop ran — so they held first place whatever the tuple said. The chain
is now a value that takes its turn in the order like everything else.

Ordering is the whole change: nothing is dropped, shortened or conditioned.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import score_text

PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead. "
    "The grit itself does a second job once the ice has gone soft, which matters more on a hill "
    "than it does on the flat, and councils plan their routes around exactly that difference."
)
CODE = "```python\n" + "\n".join(f"def f{i}(a, b):\n    return a + b * {i}" for i in range(20)) + "\n```"
TIER_MARK = "lite tier on the stdlib path"


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_tier_caveat_fires_on_ordinary_text() -> None:
    """The premise. If the standing note stopped firing, the ordering below would be vacuous — and
    the note itself is load-bearing, so its disappearance would be a separate defect."""
    assert TIER_MARK in (score_text(PROSE, tier="lite", threshold=0.3).get("warning") or "")


def test_a_situational_caveat_comes_before_the_standing_one() -> None:
    """The fix. Both are present; the specific one is what a reader meets first."""
    warning = score_text(PROSE, tier="lite", threshold=45.0).get("warning") or ""
    assert warning.startswith("the threshold 45.0 is above 1.0"), warning[:80]
    assert TIER_MARK in warning


def test_the_standing_caveat_is_not_lost() -> None:
    """Ordering, not suppression. The tier note is the reason `flagged` can be trusted at all on
    this path, and demoting it must not delete it."""
    warning = score_text(CODE, tier="lite", threshold=45.0).get("warning") or ""
    assert TIER_MARK in warning
    assert "probabilities in [0, 1]" in warning


def test_an_unknown_tier_still_says_so() -> None:
    """The tier chain has three branches and only one is the lite caveat. Converting it from a
    direct assignment to a value had to keep all three reachable."""
    warning = score_text(PROSE, tier="lyte", threshold=0.3).get("warning") or ""
    assert "unknown tier 'lyte'" in warning


def test_ordinary_prose_still_gets_exactly_one_note() -> None:
    """Guards the guard from the noise side: the reorder must not have started stacking caveats on
    text that only ever earned one. 0 of 120 corpus texts trigger any situational caveat."""
    warning = score_text(PROSE, tier="lite", threshold=0.3).get("warning") or ""
    assert warning.startswith(TIER_MARK), warning[:80]
    assert " Also: " not in warning


def test_several_caveats_still_compose() -> None:
    """The question this loop opened with. Up to three fire together on one document, and the
    answer was that none masks another — recorded so a future ordering change cannot quietly
    reintroduce the masking this file was written to rule out."""
    warning = score_text(CODE, tier="lite", threshold=45.0).get("warning") or ""
    present = [
        mark
        for mark in ("probabilities in [0, 1]", "no prose lines", "preserved material", TIER_MARK)
        if mark in warning
    ]
    assert len(present) >= 3, present
