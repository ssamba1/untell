"""The too-short warning fires once, not on every call.

humanness.py:75: `_WARNED_TOO_SHORT = True` — the flag latches after the first
too-short warning. The mutation True -> False never sets the flag, so every
subsequent too-short text warns again, spamming the log. Prior 'warning latch,
no observable output change' note wrong — the latch IS the observable, same
class as the voice.py:187 warn-once kill.
"""
import logging

import untell.humanness as humanness


def test_too_short_warns_only_once(monkeypatch):
    monkeypatch.setattr(humanness, "_WARNED_TOO_SHORT", False)
    records = []

    class _H(logging.Handler):
        def emit(self, rec):
            records.append(rec.getMessage())

    handler = _H()
    logger = logging.getLogger("untell.humanness")
    logger.addHandler(handler)
    try:
        humanness._warn_too_short()
        humanness._warn_too_short()
    finally:
        logger.removeHandler(handler)
    assert len(records) == 1, f"expected one warning, got {len(records)}"
