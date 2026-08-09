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
