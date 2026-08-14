"""Empty-vs-nonempty similarity is 0, not a spurious embedding cosine.

quality.py:174: `if a_empty or b_empty: return 1.0 if (a_empty and b_empty) else
0.0` — the comment documents why: "Without this the embedding path returns a
spurious non-zero cosine for '' vs 'something'". The mutation or -> and drops
the one-empty case, so similarity('', 'hello') falls through to the embedding
path and returns ~0.51 (measured) — an empty string reads as half-similar to
real text, defeating the gate.
"""
from untell.scripts.quality import similarity


def test_empty_vs_text_is_zero():
    assert similarity("", "hello") == 0.0


def test_empty_vs_empty_is_one():
    assert similarity("", "") == 1.0
