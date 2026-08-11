"""Every surface that judges "can this text be read" must give the same answer.

`humanness` returned 50.0 — undetermined — on punctuation-only text while `score_tells` reported
`language_supported: True` and counted six semicolon crutches in `;;; ;;;`. One text, two surfaces,
opposite answers, for as long as both have existed. Nothing failed, because nothing compared them.

That is the same shape as the four-surface default comparison in Result 98, asked about the INPUT
instead of about the arguments — and the fix in both cases came from putting the answers side by
side rather than from reading either one.

One distinction this file exists to keep straight, because the first version of the sweep got it
wrong: **"undetermined" and "unsupported language" are different predicates.** `humanness` abstains
for two reasons — too short, and wrong script — so short English is undetermined AND supported, and
that is correct rather than a disagreement. The tests below compare the language question only.
"""

from __future__ import annotations

import logging

import pytest

from untell.humanness import humanness
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

# (name, text, can the English catalogue read it)
INPUTS = [
    ("plain English", "The committee met on Tuesday and nobody could agree about the budget.", True),
    ("AI English", "Moreover, the framework leverages robust methodologies to deliver outcomes.", True),
    ("short English", "Hi there.", True),
    ("English quoting Chinese", "The sign said 你好 which means hello, and the rest is English.", True),
    ("Chinese", "此外，该框架利用强大的方法在规模上提供成果。", False),
    ("Korean", "이 프레임워크는 규모에 따라 결과를 제공합니다.", False),
    ("Russian", "Эта структура обеспечивает результаты в масштабе для всех.", False),
    ("digits", "123 456 789 1011 1213 1415", False),
    ("punctuation", "... --- !!! ??? ;;; ::: ,,,", False),
    ("emoji", "🎉 😀 👍 🔥 🚀", False),
    ("whitespace", "   \t  \n  ", False),
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    """These inputs warn by design; the warnings are the subject of other files."""
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize(("name", "text", "readable"), INPUTS, ids=lambda x: str(x)[:22])
def test_the_catalogue_agrees_with_itself(name: str, text: str, readable: bool) -> None:
    assert score_tells(text)["language_supported"] is readable, name


@pytest.mark.parametrize(("name", "text", "readable"), INPUTS, ids=lambda x: str(x)[:22])
def test_humanness_abstains_on_everything_unreadable(name: str, text: str, readable: bool) -> None:
    """One direction only, and deliberately.

    Unreadable must imply undetermined — a humanness number for text the catalogue cannot parse is
    a verdict drawn from nothing. The converse does NOT hold: "Hi there." is readable English and
    still undetermined, because it is too short. Asserting the biconditional is what made the first
    version of this sweep report a false disagreement.
    """
    if not readable:
        assert humanness(text, tier="lite") == 50.0, name


@pytest.mark.parametrize(("name", "text", "readable"), INPUTS, ids=lambda x: str(x)[:22])
def test_the_scored_result_carries_a_caveat_for_unreadable_text(
    name: str, text: str, readable: bool
) -> None:
    """The third surface. A caller reading only `score_text` must not get a bare verdict on text
    the other two consider unreadable."""
    warning = score_text(text, tier="lite").get("warning") or ""
    if not readable:
        assert warning, f"{name}: scored with no caveat at all"


def test_a_readable_input_is_not_caveated_about_language() -> None:
    """Guards the guard. Warning about everything would satisfy the tests above and mean nothing."""
    warning = score_text(INPUTS[0][1], tier="lite").get("warning") or ""
    for language_words in ("non-Latin script", "no letters", "English-only"):
        assert language_words not in warning, warning


def test_the_fixtures_cover_both_answers() -> None:
    """A list that drifted to all-True or all-False would make three parametrized tests vacuous."""
    answers = {readable for _n, _t, readable in INPUTS}
    assert answers == {True, False}
    assert sum(1 for *_r, readable in INPUTS if not readable) >= 4
