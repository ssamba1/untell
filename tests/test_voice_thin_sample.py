"""A scalar that drops its own caveat is the recurring shape in this codebase.

`voice_report` returns the thin-sample caveat as a `warning` key. `voice_distance` returns a bare
float and returned it in silence: MEASURED, a 9-word sample against the documented 150-word minimum
answered 2.6543 with nothing to say the number was closer to noise than to a profile.

The loop guards this separately — `untell humanize --voice-sample` warns on stderr — so the gap was
only on the direct-call path. That is the same shape as the `humanness` fix in Result 62 and the
`polarity_kept` gap in Result 73: the rich function carries the limit, the scalar one drops it, and
the scalar one is what a caller reaches for first.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts import voice as V

LONG_SAMPLE = "I write in short sentences. " * 40
DRAFT = "The present analysis demonstrates substantive improvements across the evaluated corpus."


def test_a_thin_sample_is_warned_about(caplog: pytest.LogCaptureFixture) -> None:
    V._WARNED_THIN_SAMPLE = False
    with caplog.at_level(logging.WARNING, logger=V.logger.name):
        V.voice_distance("I write short. Very short.", DRAFT)
    assert "under 150 words" in caplog.text, caplog.text


def test_a_full_sample_is_not(caplog: pytest.LogCaptureFixture) -> None:
    """Guards the guard: warning on every call would be noise, and noise is how a caveat that
    matters gets skipped."""
    V._WARNED_THIN_SAMPLE = False
    assert len(V._WORD.findall(LONG_SAMPLE)) >= V.MIN_SAMPLE_WORDS
    with caplog.at_level(logging.WARNING, logger=V.logger.name):
        V.voice_distance(LONG_SAMPLE, DRAFT)
    assert "under 150 words" not in caplog.text


def test_the_warning_is_said_once(caplog: pytest.LogCaptureFixture) -> None:
    """The loop calls this once per candidate — best-of-3 over 3 iterations is nine calls on one
    unchanged sample, and nine copies of the same sentence is not a caveat, it is a wall."""
    V._WARNED_THIN_SAMPLE = False
    with caplog.at_level(logging.WARNING, logger=V.logger.name):
        for _ in range(5):
            V.voice_distance("Short sample.", DRAFT)
    assert caplog.text.count("under 150 words") == 1


def test_the_number_itself_is_unchanged() -> None:
    """The caveat is added, not substituted. A warning that also altered the value would make every
    measurement in the log depend on whether logging was configured."""
    V._WARNED_THIN_SAMPLE = False
    thin = V.voice_distance("Short sample.", DRAFT)
    V._WARNED_THIN_SAMPLE = True  # suppress the warning path entirely
    assert V.voice_distance("Short sample.", DRAFT) == thin


def test_ordering_still_holds() -> None:
    """The property the distance exists for, kept alongside the caveat."""
    V._WARNED_THIN_SAMPLE = True
    same = V.voice_distance(LONG_SAMPLE, "I write in short sentences. I keep them short.")
    different = V.voice_distance(LONG_SAMPLE, DRAFT)
    assert same < different, f"same-voice {same} should sit below cross-voice {different}"
