"""A cut EXACTLY at a difflib block start maps through the block.

text_split.py:183: `if blk.a <= i < blk.a + blk.size` — source index i at the
exact start of a matching block maps to blk.b + (i - blk.a). The mutation
<= -> < makes i == blk.a skip the block and anchor to the NEXT block's start,
which for a 100-word pair cut at i=50 (block starts at 50) maps to 100: the
second chunk becomes empty, is filtered, and aligned_chunks falls back to one
chunk of 50 instead of two of 50. Pinned with a fake difflib matcher.
"""
from unittest.mock import patch

from untell.text_split import aligned_chunks


class _FakeMatcher:
    def __init__(self, a, b, autojunk):
        self.a, self.b = a, b

    def get_matching_blocks(self):
        class B:
            def __init__(self, a, b, size):
                self.a, self.b, self.size = a, b, size

        return [B(50, 50, 50), B(100, 100, 0)]


def test_cut_at_block_start_maps_through_the_block():
    a = " ".join(f"x{i}" for i in range(100))
    with patch("difflib.SequenceMatcher", _FakeMatcher):
        result = aligned_chunks(a, a)
    assert len(result) == 2, f"expected 2 chunks, got {len(result)}"
    assert all(len(c[0].split()) == 50 for c in result)
