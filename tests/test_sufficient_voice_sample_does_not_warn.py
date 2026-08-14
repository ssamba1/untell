"""A sufficient voice sample must not trigger the thin-sample warning.

voice.py:185: `if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:`
early-returns when the sample is adequate. The mutation or -> and makes the
guard require BOTH already-warned AND sufficient, so an adequate sample falls
through and logs a false "under 150 words" warning — telling the user their
voice sample is too thin when it is not.
"""
import logging

import untell.scripts.voice as voice


def test_sufficient_sample_does_not_warn(monkeypatch):
    monkeypatch.setattr(voice, "_WARNED_THIN_SAMPLE", False)
    records = []

    class _H(logging.Handler):
        def emit(self, rec):
            records.append(rec.getMessage())

    handler = _H()
    logger = logging.getLogger("untell.scripts.voice")
    logger.addHandler(handler)
    try:
        voice._warn_if_sample_is_thin(" ".join(["word"] * 200))
    finally:
        logger.removeHandler(handler)
    assert not records, f"sufficient sample warned: {records}"


def test_thin_sample_warns_once(monkeypatch):
    monkeypatch.setattr(voice, "_WARNED_THIN_SAMPLE", False)
    records = []

    class _H(logging.Handler):
        def emit(self, rec):
            records.append(rec.getMessage())

    handler = _H()
    logger = logging.getLogger("untell.scripts.voice")
    logger.addHandler(handler)
    try:
        voice._warn_if_sample_is_thin("tiny sample")
    finally:
        logger.removeHandler(handler)
    assert records, "thin sample did not warn"
