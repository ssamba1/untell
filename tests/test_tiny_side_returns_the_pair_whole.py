"""A tiny side must short-circuit chunking, not re-chunk the long side.

text_split.py:143: `if k == 1 or len(aw) < 2 or len(bw) < 2: return [(a, b)]` —
a pair whose shorter side is under 2 words is returned whole. The mutation
or -> and requires ALL THREE conditions, so a 100-word vs 1-word pair falls
through to chunking, which re-cuts the long side (50-word chunk observed) —
breaking the [(a, b)] whole-pair contract the meaning gates rely on.
"""
from untell.text_split import aligned_chunks


def test_tiny_side_returns_the_pair_whole():
    a = " ".join(f"word{i}" for i in range(100))
    b = "word0"
    chunks = aligned_chunks(a, b)
    assert len(chunks) == 1
    ca, cb = chunks[0]
    assert len(ca.split()) == 100, f"long side re-chunked to {len(ca.split())}"
    assert len(cb.split()) == 1


def test_a_two_word_side_still_chunks_a_long_pair():
    """The tiny-side guard is `len(aw) < 2`, not `<= 2` — a two-word side with a long other side
    must still be chunked, or the long side comes back as ONE chunk over CHUNK_WORDS. The
    boundary mutation `< -> <=` made exactly that: a 2-word vs 200-word pair returned whole."""
    a = "two words"
    b = " ".join(f"word{i}" for i in range(200))
    chunks = aligned_chunks(a, b)
    assert len(chunks) > 1, f"expected the pair to be chunked, got one chunk of {len(b.split())}"
    assert all(len(cb.split()) <= 90 for _, cb in chunks), "chunk exceeds CHUNK_WORDS"
    assert " ".join(ca for ca, _ in chunks) == a, "no word of the tiny side may be dropped"
