"""A score on very short text must say it is not a verdict.

The API answered `"a"` with P(AI) = 0.9987 and `flagged: True` — a maximally confident AI verdict
on one letter. `humanness()` already refuses to answer below five words, so the repo agreed the
quantity is unmeasurable there; the primary scoring path did not, and it is the one behind
`/score`, `/tells` and the CLI.

MEASURED on 40 HC3 pairs at the 0.30 default, full tier, truncating both halves to the first N
words and asking what fraction of the HUMAN half flags:

    words   human flagged   AI flagged
        5             98%         100%
       10             62%          95%
       20             40%         100%
       40             28%         100%
       80             17%         100%

At five words the two are indistinguishable. The fix is the one the lite-tier stdlib path already
uses: keep the number, and say with the measured rate that this configuration is not one to trust.
`max` is deliberately unchanged — callers store and compare it, and silently zeroing it would break
them for a reason they could not see.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import _MIN_WORDS_FOR_A_VERDICT, _short_text_warning, score_text
from untell.scripts.tells import _MIN_WORDS_FOR_A_RATE, score_tells


def _words(n: int) -> str:
    return " ".join(["word"] * n)


@pytest.mark.parametrize("n", [1, 2, 4, 9, 19, 39])
def test_short_text_is_warned_about(n: int) -> None:
    warning = score_text(_words(n), tier="lite").get("warning") or ""
    assert "too short for a reliable verdict" in warning, (
        f"{n} words scored with no length caveat: {warning!r}"
    )


@pytest.mark.parametrize("n", [40, 60, 200])
def test_long_enough_text_is_not_warned_about(n: int) -> None:
    """Guards the guard: a warning on everything would pass the test above and mean nothing."""
    warning = score_text(_words(n), tier="lite").get("warning") or ""
    assert "too short" not in warning, f"{n} words should be long enough: {warning!r}"


def test_the_warning_carries_the_measured_rate() -> None:
    """A caveat without a number is advice; with one it is evidence the reader can weigh."""
    warning = _short_text_warning(_words(5)) or ""
    assert "98%" in warning, warning
    assert "HUMAN" in warning, warning
    assert _short_text_warning(_words(30)) and "28%" in _short_text_warning(_words(30))


def test_one_word_is_singular() -> None:
    assert "1 word:" in (_short_text_warning("a") or "")


def test_a_tier_warning_is_not_displaced_by_the_length_one() -> None:
    """Length and tier are independent problems, and short text on a downgraded tier has both.

    The surrounding code picks a tier warning with an if/elif chain, so appending was the only way
    to avoid reporting whichever was checked first and hiding the other.
    """
    warning = score_text(_words(3), tier="lite").get("warning") or ""
    assert "too short" in warning
    assert "Also:" in warning, f"length warning replaced the tier warning: {warning!r}"


def test_the_threshold_is_the_documented_one() -> None:
    """If someone moves the bar, the docstring table above stops describing the behaviour."""
    assert _MIN_WORDS_FOR_A_VERDICT == 40


# --- the same defect in the tells metric -------------------------------------------------------
# `tells_per_100w` from a handful of words is quantised, not estimated: the smallest non-zero value
# a text of N words can report is 100/N. `Moreover.` is one word and one tell and reports 100.0,
# against measured corpus means of 0.551 human and 7.335 AI (Result 45).

def _quantisation_warned(text: str) -> bool:
    return "quantised" in (score_tells(text).get("warning") or "")


@pytest.mark.parametrize("text", ["Moreover.", "Furthermore, indeed.", "In conclusion, moreover."])
def test_a_rate_from_too_few_words_is_caveated(text: str) -> None:
    assert _quantisation_warned(text), f"{text!r} reported a rate with no caveat"


def test_no_caveat_when_the_rate_is_zero() -> None:
    """Short text usually produces no tells at all — measured over 60 HC3 pairs truncated to five
    words, the mean rate is 0.00 human and 0.67 AI. A caveat on a harmless 0.0 is noise, and noise
    is how readers learn to skip warnings."""
    assert not _quantisation_warned("word " * 13)


def test_no_caveat_once_there_are_enough_words() -> None:
    """Guards the guard: warning on everything would pass the parametrised test above."""
    long_enough = "Moreover the delve into a rich tapestry is worth noting here now and also again"
    assert len(long_enough.split()) >= _MIN_WORDS_FOR_A_RATE
    assert score_tells(long_enough)["tells"] > 0, "fixture no longer produces a tell"
    assert not _quantisation_warned(long_enough)


def test_the_caveat_points_at_the_count_not_the_rate() -> None:
    """The actionable part. A caveat that only says "unreliable" leaves the reader with nothing.

    The corpus means are pinned EXACTLY, deliberately, even though that means a re-measurement
    breaks this test. That is the point: it broke once already, when the figures were re-derived
    from 0.551/7.335 to 0.642/7.320 on 100 HC3 pairs at >=60 words, and the failure is what forced
    the update to be conscious rather than silent. A structural assertion — "quotes two numbers" —
    would survive any drift, including drift into being wrong.
    """
    warning = score_tells("Moreover.").get("warning") or ""
    assert "COUNT" in warning, warning
    assert "0.642" in warning and "7.320" in warning, warning
    assert "HC3" in warning, "a corpus-bound number has to name its corpus"


def test_the_rate_bar_is_derived_not_chosen() -> None:
    """14 is where 100/N drops below the AI corpus mean. If either number moves, so must the other."""
    assert _MIN_WORDS_FOR_A_RATE == 14
    assert 100 / _MIN_WORDS_FOR_A_RATE < 7.335
    assert 100 / (_MIN_WORDS_FOR_A_RATE - 1) > 7.335
