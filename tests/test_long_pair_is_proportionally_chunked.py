"""The proportional-cut fallback returns the chunks, not the whole pair.

text_split.py:175: for documents past _EXACT_ALIGN_LIMIT, aligned_chunks cuts both
sides proportionally and returns the pieces — `return out or [(a, b)]` returns
out whenever it has chunks, and only falls back to the whole pair when every
piece is empty. The mutation or -> and makes a NON-empty out return [(a, b)]
(the entire undivided document), which defeats the CHUNK_WORDS bound the
proportional path exists to enforce: a 7000-word pair -> 78 chunks of 90 words
under the original, 1 chunk of 7000 under the mutant.
"""
from untell.text_split import aligned_chunks

LONG = " ".join(["word"] * 7000)


def test_long_pair_is_proportionally_chunked():
    result = aligned_chunks(LONG, LONG)
    assert len(result) > 1, f"expected multiple chunks, got {len(result)}"
    assert all(len(a.split()) <= 90 for a, _ in result), "chunk exceeds CHUNK_WORDS"
