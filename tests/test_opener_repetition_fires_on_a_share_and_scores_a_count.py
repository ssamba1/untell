"""`repeated_sentence_openers` fires on a SHARE and reports a COUNT, and the two can disagree.

FOUND while chasing the largest gap in the category sweep: the tell fires on 47 of 120 corpus texts
and `structural_rewrite` reduces it on 15. Opening the other 32 showed the repeated openers are
"the", "in", "we", "our" — ordinary function words, not the AI markers `_vary_openers` targets. But
the interesting part was in the numbers, not the words.

`_duplicate_sentence_starts` fires when duplicate openers reach 40% of sentences, and then returns
the raw duplicate COUNT. A rewrite that adds sentences grows the denominator, so the share can fall
while the count does not. MEASURED over the 47 texts that fire (sentence count changed on 34):

    share improved, count did not fall     15
    share worsened, count did not rise      0
    the two agree                          32

One example carries it: **share 70.0% -> 53.8%, count 7 -> 7.** A 16-point improvement on the
detector's own criterion, scored as no change at all.

**The error is one-directional, and that is what makes it tolerable.** It hides improvement and
never hides damage, so the loop under-credits a good rewrite but is never fooled by a bad one. That
direction is the invariant this file pins.

**The obvious fix was measured and is worse.** Reporting the excess above the threshold
(`dupes - ceil(0.40 * n)`) compresses the magnitude out of the signal:

    variant                      RAID AUROC   HC3 AUROC   hides improvement   hides DAMAGE
    shipped (raw count)            0.9555      0.8696          15                  0
    excess, floored at 1           0.9381      0.8738          12                  5
    excess, unfloored              0.9336      0.8756           6                  1

Both variants trade a blind spot that only ever hides improvement for one that hides damage, and
both cost RAID AUROC. The unfloored variant is worse than the table shows: a text can be over the
40% bar and report 0, so the detector fires and contributes nothing — the same
criterion-disagrees-with-value defect in a new place.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.tells import _WORD, _duplicate_sentence_starts, _sentences

BODY = (
    "The system reads the file. The parser splits it into records. The loader writes each record. "
    "The index is rebuilt afterwards once every record has landed and the checksums have been "
    "compared against the manifest. The report lists what changed. Errors are collected as they "
    "occur so a single bad record does not stop the run, and the summary prints them at the end "
    "together with the elapsed time and the number of rows that were skipped along the way."
)


def _share(text: str) -> float:
    starts = [_WORD.findall(s)[0].lower() for s in _sentences(text) if _WORD.findall(s)]
    return (len(starts) - len(set(starts))) / len(starts) * 100


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_detector_fires_on_this_body() -> None:
    """Premise for everything below."""
    assert _duplicate_sentence_starts(BODY) > 0
    assert _share(BODY) >= 40.0


def test_more_repetition_never_scores_lower() -> None:
    """The invariant. The count may fail to notice an improvement; it must never fail to notice
    damage, because the loop treats a lower number as a better rewrite."""
    worse = BODY + " The queue is drained last. The log is closed."
    assert _share(worse) > _share(BODY), "premise: this really is more repetitive"
    assert _duplicate_sentence_starts(worse) >= _duplicate_sentence_starts(BODY)


def test_added_variety_can_go_unnoticed_but_never_backwards() -> None:
    """The measured blind spot, pinned with its own example rather than left to be rediscovered.
    Appending distinct openers lowers the duplicate SHARE and leaves the duplicate COUNT alone."""
    varied = BODY + " Salt melts ice. Grit adds traction. Councils mix both."
    assert _share(varied) < _share(BODY), "premise: the share must actually improve"
    assert _duplicate_sentence_starts(varied) == _duplicate_sentence_starts(BODY)


def test_the_reported_value_is_the_raw_duplicate_count() -> None:
    """Guards the rejected fix directly, because the near-miss taught the lesson. My first version
    of this guard compared a repetitive text against a sparse one and passed under BOTH rejected
    variants — the sparse text was under the 60-word floor and scored 0 either way, so the
    comparison was vacuous.

    The design decision is that the magnitude reported is the duplicate count itself, not a
    residual above the firing threshold. Subtracting the threshold is what compressed every firing
    text toward 1 and cost RAID AUROC 0.9555 -> 0.9381 (floored) / 0.9336 (unfloored)."""
    for text in (BODY, BODY + " The queue is drained last. The log is closed."):
        starts = [_WORD.findall(s)[0].lower() for s in _sentences(text) if _WORD.findall(s)]
        assert _duplicate_sentence_starts(text) == len(starts) - len(set(starts))


def test_a_text_that_fires_always_reports_something() -> None:
    """The unfloored variant broke this: over the 40% bar and returning 0, so the firing rule and
    the reported value disagreed outright."""
    for text in (BODY, BODY + " The queue is drained last."):
        if _share(text) >= 40.0:
            assert _duplicate_sentence_starts(text) >= 1
