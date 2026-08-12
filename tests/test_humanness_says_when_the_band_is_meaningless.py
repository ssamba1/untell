"""`humanness` answered confidently in a band where it cannot separate the classes.

At 12 words it returned 99.7 and called it "human", while `score_text` on the identical text warned
"too short for a reliable verdict". One tool, one text, two answers about whether a verdict is even
possible — the gates were 5 words and 40.

MEASURED on 30 HC3 pairs truncated to N words, full tier:

    words   human mean   AI mean   AUROC   human texts called human
       10      60.3        49.8    0.792         10/30
       20      56.8        48.6    0.732          7/30
       40      47.3        45.3    0.694          0/30
      220      75.7        37.4    0.978         20/30

Two failures at once, and the second is worse: separation collapses, AND the whole distribution
slides down, so at 40 words not one of thirty genuine human texts lands in a human band. The score
is biased against the human writer exactly where it is least reliable.
"""

from __future__ import annotations

import logging

import pytest

import untell.humanness as humanness_mod
from untell.humanness import _MIN_WORDS_FOR_A_BAND, humanness

SHORT = "The committee reviewed the proposal and found it broadly acceptable this year."
LONG = SHORT + (
    " Costs had risen steadily since the spring and nobody expected the throughput to double "
    "within a single quarter, least of all the engineers who had built the original system. "
    "Attendance was steady and the catering contract was renewed without discussion."
)


@pytest.fixture(autouse=True)
def _reset_warning_flags():
    humanness_mod._WARNED_SHORT_BAND = False
    humanness_mod._WARNED_TOO_SHORT = False
    yield
    humanness_mod._WARNED_SHORT_BAND = False
    humanness_mod._WARNED_TOO_SHORT = False


def test_a_short_text_still_gets_a_number(caplog: pytest.LogCaptureFixture):
    """The number is not withheld. Callers store and compare it, and silently changing it would
    break them for a reason they cannot see — the same rule `score_text` follows for `max`."""
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        score = humanness(SHORT, tier="lite")
    assert 0.0 <= score <= 100.0


def test_but_it_says_the_band_does_not_separate(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        humanness(SHORT, tier="lite")
    assert "does not separate" in caplog.text, caplog.text
    assert "0.694" in caplog.text, "the caveat must carry the measured number, not just advice"


def test_long_enough_text_says_nothing(caplog: pytest.LogCaptureFixture):
    """Guards the guard: a caveat on every call is noise, and noise is how a real one is missed."""
    assert len(LONG.split()) >= _MIN_WORDS_FOR_A_BAND, "premise: the fixture must clear the bar"
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        humanness(LONG, tier="lite")
    assert "does not separate" not in caplog.text


def test_it_warns_once_per_process(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        for _ in range(3):
            humanness(SHORT, tier="lite")
    assert caplog.text.count("does not separate") == 1


def test_the_bar_matches_the_scorer(caplog: pytest.LogCaptureFixture):
    """The defect was two surfaces disagreeing about whether a verdict is possible. Same bar now."""
    from untell.scripts.score import _MIN_WORDS_FOR_A_VERDICT

    assert _MIN_WORDS_FOR_A_BAND == _MIN_WORDS_FOR_A_VERDICT


def test_the_abstention_path_is_unchanged(caplog: pytest.LogCaptureFixture):
    """Below five words humanness still abstains at 50.0 rather than reporting a band caveat."""
    with caplog.at_level(logging.WARNING, logger="untell.humanness"):
        assert humanness("two words", tier="lite") == 50.0
    assert "shorter than" in caplog.text
