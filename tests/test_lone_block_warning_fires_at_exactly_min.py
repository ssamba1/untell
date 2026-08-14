"""The lone-block warning fires AT the minimum block count, not only above it.

score.py:1203: `if len(prose) < _MIN_BLOCKS_FOR_LONE_NOTE: return None` — the
warning is suppressed only when there are FEWER than 3 blocks. The mutation
< -> <= suppresses it at exactly 3 blocks, silently dropping the honest
"one sentence per paragraph" note at the boundary where the shape is exactly
as described.
"""
from untell.scripts.score import _line_per_sentence_warning


def test_lone_block_warning_fires_at_exactly_min_blocks():
    text = "One sentence here.\nTwo sentence here.\nThree sentence here."
    out = _line_per_sentence_warning(text)
    assert out is not None
    assert "one sentence per paragraph" in out


def test_lone_block_warning_suppressed_below_min_blocks():
    text = "One sentence here.\nTwo sentence here."
    out = _line_per_sentence_warning(text)
    assert out is None
