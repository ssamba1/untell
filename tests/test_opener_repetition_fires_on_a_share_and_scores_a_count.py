"""`repeated_sentence_openers` fires on a SHARE and reports a COUNT, and the two can disagree.

FOUND while chasing the largest gap in the category sweep: the tell fires on 47 of 120 corpus texts
and `structural_rewrite` reduces it on 15. Opening the other 32 showed the repeated openers are
"the", "in", "we", "our" — ordinary function words, not the AI markers `_vary_openers` targets. But
the interesting part was in the numbers, not the words.

`_duplicate_sentence_starts` fires when duplicate openers reach 40% of sentences, and then returns
the raw duplicate COUNT. A rewrite that adds sentences grows the denominator, so the share can fall
while the count does not — and **the count is the one to trust.** MEASURED over the 47 texts that
fire, on the 18 where the share fell without the count falling:

    duplicate openers IDENTICAL before and after    14
    duplicate openers actually ROSE                  4

Not one repetition was removed in those 14. The share fell because sentences were added. The
worst case — 14 sentences with 8 duplicate openers becoming 18 with 10 — has the share reporting an
improvement while the repetition got measurably worse.

I read this backwards first, as the detector failing to credit a real improvement, and wrote it up
that way. Reading the incidents beside the share is what corrected it. The count is length-invariant
by design, the same reason `_repeated_trigrams` reports a count: its raw AUROC is roughly 40% length
rather than style.

**The fix I reached for before understanding that was measured and is worse anyway.** Reporting the
excess above the threshold (`dupes - ceil(0.40 * n)`) compresses the magnitude out of the signal:

    variant                      RAID AUROC   HC3 AUROC
    shipped (raw count)            0.9555      0.8696
    excess, floored at 1           0.9381      0.8738
    excess, unfloored              0.9336      0.8756

Both cost RAID AUROC because the residual above a threshold is nearly binary. The unfloored variant
has a second defect: a text can be over the 40% bar and report 0, so the detector fires and
contributes nothing.
"""

from __future__ import annotations

import logging
from collections import Counter

import pytest

from untell.scripts.tells import (
    _WORD,
    _duplicate_sentence_starts,
    _repeated_trigrams,
    _sentences,
)

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


def test_appending_fresh_openers_removes_no_repetition_and_scores_no_credit() -> None:
    """The case I first mistook for a blind spot. Appending distinct openers lowers the duplicate
    SHARE while every existing repetition survives untouched, so the count holding still is correct
    — 14 of the 18 corpus cases are exactly this. Diluting a tell is not removing it."""
    varied = BODY + " Salt melts ice. Grit adds traction. Councils mix both."
    assert _share(varied) < _share(BODY), "premise: the share must fall"
    assert _duplicate_sentence_starts(varied) == _duplicate_sentence_starts(BODY)


def test_the_share_can_call_worse_repetition_an_improvement() -> None:
    """The other 4 of the 18, and the reason the count is the quantity that ships. Adding sentences
    that themselves repeat an opener grows the repetition and shrinks the density at once."""
    worse = BODY + " Salt melts ice. Grit adds traction. The lock is released. The log is closed."
    assert _share(worse) < _share(BODY), "premise: the share must report an improvement"
    assert _duplicate_sentence_starts(worse) > _duplicate_sentence_starts(BODY)


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


def test_the_other_repetition_tell_reports_a_count_too() -> None:
    """`_repeated_trigrams` is built the same way — fires on a 5% share, returns the repeat count —
    and its docstring opened by calling the return "a share of its tokens (percent, floored)",
    contradicting the "counted once per repeat" line below it and the code between them. 150 words
    with 143 repeats returns 143, not 95. Pinned so the description cannot drift off the code
    again."""
    text = "The system reads the file. " * 30
    words = [w.lower() for w in _WORD.findall(text)]
    grams = Counter(tuple(words[i : i + 3]) for i in range(len(words) - 2))
    repeats = sum(c - 1 for c in grams.values() if c > 1)
    assert repeats / len(words) * 100 >= 5.0, "premise: it must fire"
    assert _repeated_trigrams(text) == repeats
    assert _repeated_trigrams(text) > 100, "a percentage could not exceed 100"


def test_a_text_that_fires_always_reports_something() -> None:
    """The unfloored variant broke this: over the 40% bar and returning 0, so the firing rule and
    the reported value disagreed outright."""
    for text in (BODY, BODY + " The queue is drained last."):
        if _share(text) >= 40.0:
            assert _duplicate_sentence_starts(text) >= 1
