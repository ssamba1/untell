"""`untell tells` dropped its caveat whenever it found anything to report.

The warning sat on an `elif` against the category list, so it printed ONLY when no tell fired. Any
text that both matched a pattern and warranted a caveat showed the categories and swallowed the
caveat.

MEASURED on a 9-word input:

    AI-tells: 2  (22.22 per 100 words, 9 words)
    by category:
      formulaic_transition   1
      ai_vocab               1

and the warning that never appeared:

    9 words: `tells_per_100w` is 22.22, but a rate per 100 words from 9 words is quantised — one
    tell alone reports 11. Compare the COUNT (2), not the rate; the corpus means it would be read
    against are 0.642 human and 7.320 AI

So a reader saw a rate three times the AI corpus mean, presented without qualification, computed
from nine words.

The `elif` was not careless: it existed to stop "no catalogued tells found" printing on non-Latin
input, where that sentence reports the catalogue's blindness as the text's virtue. That suppression
still holds — it now hangs off the warning rather than replacing it.
"""
from __future__ import annotations

import pytest

from untell.scripts.tells import _render, score_tells

SHORT_AI = "Moreover, the framework leverages robust methodologies to deliver outcomes."
JAPANESE = "これは日本語の文章です。もう一つの文です。"


def test_the_short_input_produces_both_a_tell_and_a_warning():
    """The premise. Without both, the bug cannot appear."""
    result = score_tells(SHORT_AI)
    assert result["by_category"], "no tells fired, so the elif branch would have shown the warning"
    assert result.get("warning"), "no warning, so there is nothing to drop"


def test_the_warning_is_shown_alongside_the_categories():
    out = _render(score_tells(SHORT_AI))
    assert "by category:" in out
    assert "WARNING:" in out, f"caveat dropped when tells fired:\n{out}"
    assert "quantised" in out


def test_the_warning_still_shows_when_nothing_fired():
    """The case the elif was written for. It must not regress in the other direction."""
    out = _render(score_tells(JAPANESE))
    assert "WARNING:" in out
    assert "English-only" in out


def test_no_clean_bill_of_health_when_a_warning_applies():
    """"no catalogued tells found" on non-Latin text reports blindness as virtue."""
    out = _render(score_tells(JAPANESE))
    assert "no catalogued tells found" not in out, out


def test_the_clean_message_still_appears_for_genuinely_clean_text():
    """And the suppression must not swallow the ordinary case."""
    clean = (
        "I walked to the shop on the corner and found it closed for the day, so I turned around "
        "and came home again, mildly annoyed about the wasted trip and the rain that had started."
    )
    result = score_tells(clean)
    if result["by_category"] or result.get("warning"):
        pytest.skip("this fixture is no longer clean enough to exercise the else branch")

    assert "no catalogued tells found" in _render(result)
