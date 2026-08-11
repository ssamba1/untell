"""Text with no letters was reported as English the catalogue could read.

`_language_supported` compared Latin letters against non-Latin ones and returned True when there
were no non-Latin ones — which is exactly the case for digits, punctuation and emoji, none of which
is either. MEASURED on a punctuation-only string:

    tells 7   by_category {'rule_of_three': 1, 'semicolon_crutch': 6}   words 0

Six "semicolon crutches" counted in `;;; ;;;`. A semicolon crutch is a prose habit, and there is no
prose here — the finding is the catalogue matching its punctuation patterns against punctuation, in
text with zero words.

`humanness` already abstained on the same inputs and returned 50.0. The two surfaces were reading
the same text and disagreeing about whether it could be read at all.

The message matters as much as the verdict. "mostly non-Latin script" is true of a Chinese paragraph
and false of `;;; ...`, which has no script — the same distinction `humanness` draws between "too
short" and "not English", and for the same reason: the message is what a reader acts on.
"""

from __future__ import annotations

import pytest

from untell.humanness import humanness
from untell.scripts.tells import _language_supported, score_tells

LETTERLESS = {
    "digits": "123 456 789 1011 1213 1415 1617 1819 2021",
    "punctuation": "... --- !!! ??? ;;; ::: ,,, ... --- !!!",
    "emoji": "🎉 😀 👍 🔥 🚀 🎯 💡 🌟",
    "symbols": "+ - * / = < > % & @ # ^ ~ | \\",
}
ENGLISH = "The committee met on Tuesday and nobody could agree about the budget today."
CHINESE = "此外，该框架利用强大的方法在规模上提供成果。"


@pytest.mark.parametrize("name", sorted(LETTERLESS), ids=lambda n: n)
def test_letterless_text_is_not_supported(name: str) -> None:
    assert _language_supported(LETTERLESS[name]) is False


@pytest.mark.parametrize("name", sorted(LETTERLESS), ids=lambda n: n)
def test_the_warning_says_there_are_no_letters(name: str) -> None:
    warning = score_tells(LETTERLESS[name]).get("warning") or ""
    assert "no letters" in warning, warning
    assert "non-Latin script" not in warning, "wrong reason: there is no script here to be non-Latin"


def test_a_non_latin_script_still_says_script() -> None:
    """Guards the guard: routing everything to the new message would also satisfy the test above."""
    warning = score_tells(CHINESE).get("warning") or ""
    assert "non-Latin script" in warning, warning
    assert "no letters" not in warning


@pytest.mark.parametrize("text", [ENGLISH, "Hi there.", "The report quotes 框架 once, in English."])
def test_english_is_still_supported(text: str) -> None:
    """The transform is load-bearing — a mostly-English passage quoting another script must keep
    its catalogue, which is what the Latin-vs-non-Latin comparison exists for."""
    assert _language_supported(text) is True
    assert score_tells(text).get("warning") is None


def test_the_two_surfaces_now_agree() -> None:
    """`humanness` returned 50.0 — undetermined — on exactly these inputs while `score_tells`
    claimed it could read them. One text cannot be both readable and unreadable."""
    for name, text in LETTERLESS.items():
        assert humanness(text, tier="lite") == 50.0, name
        assert score_tells(text)["language_supported"] is False, name


def test_the_punctuation_count_is_still_reported_not_hidden() -> None:
    """The tells are not suppressed — they are caveated. Hiding them would be a second wrong
    answer, and a caller that wants the raw pattern count can still have it."""
    result = score_tells(LETTERLESS["punctuation"])
    assert result["words"] == 0
    assert result["tells"] >= 0
    assert result["language_supported"] is False
    assert result.get("warning")


def test_the_empty_string_is_undetermined_too() -> None:
    """Moved here from `test_tells.py`'s "English stays supported" fixtures, where it never
    belonged. An empty string is not an example of English, and calling it supported is the same
    claim that let a punctuation-only string report six semicolon crutches."""
    assert _language_supported("") is False
