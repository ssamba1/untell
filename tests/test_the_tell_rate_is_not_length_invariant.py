"""Two halves that are each perfectly clean become a flagged document when you paste them together.

`tells_per_100w` divides by words, which reads as a rate and is not scale-free. Both repetition
categories only fire above a share threshold, and a longer text crosses those thresholds on prose
that was under them in every part. So the same writing scores differently depending on how much of
it you hand over.

The halves below are 66 and 67 words, six sentences each, three of them opening with "The" — 33%
duplicate openers, under the detector's 40% bar. Together they are 41.7%, and 5 tells appear that
neither half contains.

This is what moves `humanness` with paste length. Decomposed over 24 corpus texts truncated to a
60-word and a 220-word window, in points of the final score:

                     tells term   burstiness term   detector term
    AI text             -5.4          -0.7             0.0
    human text          -0.9          +0.3             0.0

The detector contributes nothing because it is already saturated at P(AI) = 1.000 on every AI
window and flat near 0.38 on human ones — MEASURED, 13 and 11 texts. **The tells term is the whole
effect**, rising 0.036 -> 0.215 across those windows on identical prose.

Not a defect to fix here. The two repetition categories are the strongest in the catalogue and a
threshold is what makes them precise; removing it to buy scale-freedom would cost the signal. What
was missing is the caveat, which now sits on `humanness` beside the tier one it mirrors.
"""

from __future__ import annotations

import logging

import pytest

from untell.humanness import _MAX_TELLS_PER_100W, _W_TELLS
from untell.scripts.tells import _MIN_WORDS_FOR_REPETITION, score_tells

FIRST = (
    "The system reads the file before anything else happens on the node. "
    "The parser splits it into records and hands each one onward. "
    "The loader writes every record to the store without pausing. "
    "Records that fail validation are set aside for a later pass. "
    "Each acknowledgement from the replica set is logged with a timestamp. "
    "Waiting for that acknowledgement is what makes the first stage slow."
)

SECOND = (
    "The index is rebuilt once every record has landed on disk. "
    "The checksums are compared against the manifest line by line. "
    "The report lists what changed during the run and what did not. "
    "Checks that fail are retried twice before anyone is paged about them. "
    "Reports go out by email once the queue has drained completely. "
    "Queues are closed only after the writer has released its lock."
)

BOTH = f"{FIRST} {SECOND}"


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("half", [FIRST, SECOND], ids=["first", "second"])
def test_each_half_is_long_enough_to_be_judged(half: str) -> None:
    """The premise, and the reason this file is not just demonstrating an abstention. Both halves
    clear the word floor the repetition tells need and carry more than the four sentences the
    opener tell needs, so their clean score is a verdict rather than a shrug."""
    result = score_tells(half)
    assert result["words"] >= _MIN_WORDS_FOR_REPETITION
    assert half.count(".") > 4
    assert result["language_supported"] is True


@pytest.mark.parametrize("half", [FIRST, SECOND], ids=["first", "second"])
def test_each_half_scores_clean(half: str) -> None:
    assert score_tells(half)["tells_per_100w"] == 0.0


def test_the_pair_does_not() -> None:
    """The whole point. Nothing was added between the two assertions above and this one."""
    result = score_tells(BOTH)
    assert result["tells"] > 0
    assert result["by_category"].get("repeated_sentence_openers")
    assert result["tells_per_100w"] > 0.0


def test_a_rate_that_is_not_scale_free_is_not_a_rate() -> None:
    """Stated as the invariant it breaks, so the failure message says what went wrong. Concatenating
    two texts should leave a per-100-word rate between the two inputs' rates; here it exceeds both."""
    rates = [score_tells(t)["tells_per_100w"] for t in (FIRST, SECOND, BOTH)]
    assert rates[2] > max(rates[0], rates[1])


def test_the_humanness_tells_term_moves_with_it() -> None:
    """Ties the catalogue behaviour to the user-facing number. The corpus measurement puts this at
    5.4 points between a 60-word and a 220-word window; the constructed case is smaller because it
    crosses the threshold only just, and the direction is what this pins."""

    def term(text: str) -> float:
        rate = score_tells(text)["tells_per_100w"]
        return min(rate / _MAX_TELLS_PER_100W, 1.0) * _W_TELLS * 100.0

    assert term(FIRST) == 0.0
    assert term(BOTH) > 0.0
