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

# Over 100 words on purpose. This fixture was 66, which round seventy-three's length caveat
# correctly fires on — MEASURED, 28.69% of known-human documents that short are flagged — so
# "ordinary prose earns exactly one note" stopped being true of it. The fixture is now long enough
# to be ordinary in the sense the tests below mean, and `SHORT_PROSE` covers the other case
# explicitly rather than by accident.
PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead. "
    "The grit itself does a second job once the ice has gone soft, which matters more on a hill "
    "than it does on the flat, and councils plan their routes around exactly that difference. "
    "Rock salt is cheaper than the alternatives and is what most authorities buy in bulk each "
    "autumn, stockpiling it in barns near the depots so the lorries can be loaded quickly when a "
    "forecast turns. The stockpile is sized on the previous decade of winters, which is why an "
    "unusually long cold snap empties it and the routes get prioritised down to the main roads."
)
# 66 words: above the 40-word cliff where `_short_text_warning` stops, below the 100 where the
# elevated rate does. That gap is what round seventy-three found empty. This is the fixture `PROSE`
# used to be.
SHORT_PROSE = (
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
    text that only ever earned one."""
    warning = score_text(PROSE, tier="lite", threshold=0.3).get("warning") or ""
    assert warning.startswith(TIER_MARK), warning[:80]
    assert " Also: " not in warning


def test_a_short_paragraph_earns_the_length_note_and_the_tier_note_keeps_the_last_word() -> None:
    """The other side of the same rule, and the case that caught the fixture above.

    A paragraph under 100 words IS the population with a MEASURED 28.69% false-positive rate, so the
    note firing there is the feature. What must hold is the ordering this file exists for: the
    situational note first, the standing tier note last.
    """
    warning = score_text(SHORT_PROSE, tier="lite", threshold=0.3).get("warning") or ""
    assert "of documents this length" in warning, warning[:120]
    assert warning.index("of documents this length") < warning.index(TIER_MARK), (
        "the situational caveat must come before the standing one")
    assert warning.rstrip().endswith(".")


def test_no_caveat_repeats_another() -> None:
    """Caveats are read in combination, and two describing the same situation in different words
    would be the composition defect Result 208 found in a different form.

    MEASURED on the three inputs that fire the most caveats at once — code with a bad threshold,
    quotations with a bad threshold, and code alone: 12 to 14 sentences, **0** near-duplicate pairs,
    where a pair counts as near-duplicate if it shares six consecutive words. The roster note and
    the abstention note were the pair at risk, and they were given distinct wording when the second
    was added.
    """
    import re

    warning = score_text(CODE, tier="lite", threshold=45.0).get("warning") or ""
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", warning) if len(s.strip()) > 25]
    assert len(parts) >= 5, "too few caveats fired to test for repetition"
    for i, first in enumerate(parts):
        words = first.lower().split()
        for second in parts[i + 1:]:
            haystack = " ".join(second.lower().split())
            repeated = [
                " ".join(words[k:k + 6]) for k in range(len(words) - 5)
                if " ".join(words[k:k + 6]) in haystack
            ]
            assert not repeated, repeated[:2]


def test_the_merged_warning_stays_bounded() -> None:
    """Nothing caps how many caveats can stack, and this session added seven.

    MEASURED: corpus warnings run to a median of 503 characters and a maximum of 882 (Result 182,
    120 HC3 and RAID texts). The worst pathological input measured here is 1794 characters across 14
    sentences — code with no prose, mostly locked, on the lite path.

    The bound is set above that and below twice it. It is a regression guard, not a target: the
    ordering fix means a reader meets the specific caveat first, so length is a cost rather than a
    defect, and this exists so the cost cannot grow without someone deciding it should.
    """
    worst = max(
        len(score_text(text, tier="lite", **kwargs).get("warning") or "")
        for text, kwargs in ((CODE, {}), (CODE, {"threshold": 45.0}), (PROSE, {}))
    )
    assert worst < 2500, worst


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
