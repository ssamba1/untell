"""CHUNK_WORDS=90 bounds chunk size; 181 words make 3 chunks.

text_split.py:135/155: k = ceil(longest / CHUNK_WORDS). At 90, 181 words make
ceil(181/90) = 3 chunks; the mutation 90 -> 91 makes ceil(181/91) = 2, so the
longest side stays over 90 words per chunk — the bound the constant exists to
enforce is exceeded. Pinned at the module-attribute level (deterministic, no
downloads).
"""
import untell.text_split as text_split


def test_181_words_make_three_chunks():
    assert text_split.CHUNK_WORDS == 90
    a = " ".join(["w"] * 181)
    chunks = text_split.aligned_chunks(a, a)
    assert len(chunks) == 3


def test_180_words_make_two_chunks():
    a = " ".join(["w"] * 180)
    chunks = text_split.aligned_chunks(a, a)
    assert len(chunks) == 2
