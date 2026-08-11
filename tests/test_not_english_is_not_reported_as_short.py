""""Too short" and "not English" are different limits with the same symptom.

`str.split()` counts whitespace-delimited runs, so a 46-character Chinese paragraph is **one word**
by that measure. `score_text` reported it as "1 word: too short for a reliable verdict ... Score
longer text" — advice that cannot help, for a limit that is not length.

`humanness` already drew this distinction and recorded why. `score_text` did not, so the two could
say different things about one input.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import score_text

NOT_ENGLISH = {
    "chinese": "此外，该框架利用强大的方法在规模上提供成果。而且，它显著提高了整体效率和准确性。",
    "japanese": "さらに、このフレームワークは強力な手法を活用します。また、全体的な効率が向上します。",
    "arabic": "علاوة على ذلك، يستفيد هذا الإطار من منهجيات قوية لتقديم النتائج على نطاق واسع.",
    "korean": "또한 이 프레임워크는 강력한 접근 방식을 활용하여 대규모로 결과를 제공합니다.",
}

LONG_ENGLISH = (
    "The committee reviewed the proposal and found it broadly acceptable, though several members "
    "raised concerns about the timeline and the budget, which the chair agreed to revisit at the "
    "next meeting before the quarterly planning session began in earnest that autumn."
)


def _warning(text: str) -> str:
    return score_text(text, tier="lite").get("warning") or ""


@pytest.mark.parametrize("name", sorted(NOT_ENGLISH))
def test_unsupported_script_says_so_instead_of_counting_words(name: str):
    warning = _warning(NOT_ENGLISH[name])
    assert "not in a script" in warning, warning
    assert "too short" not in warning, "length is not the limit; saying so misdirects the reader"


@pytest.mark.parametrize("name", sorted(NOT_ENGLISH))
def test_it_does_not_tell_the_user_to_write_more(name: str):
    """The specific harm: advice the reader can follow and that cannot possibly work."""
    assert "Score longer text" not in _warning(NOT_ENGLISH[name])


def test_short_english_still_gets_the_length_warning():
    warning = _warning("Hello there")
    assert "too short" in warning
    assert "not in a script" not in warning


def test_long_english_gets_neither():
    warning = _warning(LONG_ENGLISH)
    assert "too short" not in warning
    assert "not in a script" not in warning


def test_score_and_humanness_agree_about_the_reason():
    """Two modules, one flag. They must not disagree about why an input cannot be judged."""
    from untell.scripts.tells import score_tells

    for text in NOT_ENGLISH.values():
        assert score_tells(text).get("language_supported") is False
    assert score_tells(LONG_ENGLISH).get("language_supported") is True


def test_empty_text_is_not_called_a_language_problem():
    warning = _warning("")
    assert "not in a script" not in warning
