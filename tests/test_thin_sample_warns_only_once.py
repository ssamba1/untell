"""The thin-sample warning fires once, not on every call.

voice.py:187: `_WARNED_THIN_SAMPLE = True` — the flag latches after the first
thin-sample warning. The mutation True -> False never sets the flag, so every
subsequent thin sample warns again, spamming the log. Pinned by calling the
guard twice with a thin sample and asserting only the first call warns.
"""
import logging

import untell.scripts.voice as voice


def test_thin_sample_warns_only_once(monkeypatch):
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
        voice._warn_if_sample_is_thin("another tiny sample")
    finally:
        logger.removeHandler(handler)
    assert len(records) == 1, f"expected one warning, got {len(records)}"
