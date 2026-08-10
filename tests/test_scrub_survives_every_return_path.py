"""`scrub=True` must hold on every way out of `untell_text`, including the error returns.

Two of them answered before the scrub ran, so `final` carried the payload straight back. One is
"no rewriter configured" — the single most likely error in the function, and what every new user
without an API key hits — so the DEFAULT was silently skipped on the most common path there is.

The hazard is the one the `scrub=False` branch already documents: 701 zero-width characters
surviving into `final`, and those flip an AI verdict to clean on 14 of 20 texts (Result 62). A
caller who ignores `error` and ships `final` was shipping an evasion payload. The PDF case is worse
because nobody chose it: soft hyphens from a justified PDF make an unhardened detector read 0.0002
where untell reports 0.9869 on the same string.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import untell_text

_TEXT = (
    "I spent five days in Lisbon last October and still have mixed feelings about it. The hills "
    "are the whole story and somehow never make the brochures. My hotel was up in Alfama, which "
    "photographs beautifully and translates to climbing a six-story staircase for coffee."
)

INVISIBLES = {
    "soft hyphen": "­",
    "zero-width space": "​",
    "zero-width joiner": "⁠",
}


def _count(text: str) -> int:
    return sum(1 for c in text if ord(c) in (0xAD, 0x200B, 0x200C, 0x200D, 0x2060))


def _dirty(ch: str) -> str:
    return "".join(c + ch for c in _TEXT)


@pytest.mark.parametrize("name,ch", INVISIBLES.items(), ids=list(INVISIBLES))
def test_no_rewriter_error_path_still_scrubs(name: str, ch: str) -> None:
    """The most common error in the function, and the one that used to ship the payload."""
    result = untell_text(_dirty(ch), rewriter="definitely-not-a-rewriter")
    assert "error" in result
    assert _count(result["final"]) == 0, f"{name} survived the error return"


def test_unknown_rewriter_error_path_still_scrubs() -> None:
    result = untell_text(_dirty("​"), rewriter="no-such-rewriter")
    assert "error" in result
    assert _count(result["final"]) == 0


def test_scrub_false_is_still_honoured_on_the_error_path() -> None:
    """The flag must keep working in BOTH directions — this is a request, not a safety rail.

    Moving the scrub earlier could just as easily have made `scrub=False` stop being respected.
    """
    dirty = _dirty("​")
    result = untell_text(dirty, rewriter="no-such-rewriter", scrub=False)
    assert "error" in result
    assert _count(result["final"]) == _count(dirty)


def test_the_error_path_does_not_rewrite() -> None:
    """Scrubbing is not licence to change the words: only the invisible characters may go."""
    result = untell_text(_dirty("­"), rewriter="no-such-rewriter")
    assert result["final"] == _TEXT
