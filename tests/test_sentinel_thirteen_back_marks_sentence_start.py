"""A locked sentinel 13 chars back still marks sentence-start.

structural.py:480: `tail = before[-12:]` — the preserve-sentinel scan window. A
sentinel whose opener sits exactly 13 characters before the cursor (sentinel
+ 5 trailing chars) is missed by the 12-char window: the tail starts at
'HZ0003...', losing the opening ⟦, so _at_sentence_start returns False and a
following sentence-start word is treated as mid-sentence. The mutation
-12 -> -13 widens the window and catches it. Pinned at the char level.
"""
from untell.rewriter.structural import _at_sentence_start

SENTINEL = "\u27e6HZ0003\u27e7"  # ⟦HZ0003⟧
BEFORE = SENTINEL + "XXXXX"  # 13 chars; sentinel opener at exactly -13


def test_sentinel_thirteen_back_is_missed_by_twelve_char_window():
    # Original: tail = BEFORE[-12:] loses the opening ⟦ -> no sentinel found.
    assert len(BEFORE) == 13
    assert _at_sentence_start(BEFORE + " Word", len(BEFORE)) is False


def test_sentinel_within_window_is_seen():
    near = SENTINEL + "XXXX"  # 12 chars; sentinel fully inside the window
    assert _at_sentence_start(near + " Word", len(near)) is True
