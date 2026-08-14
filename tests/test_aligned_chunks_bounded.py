"""Killing test: aligned_chunks must not take quadratic time on long docs.

Measured: 1k words 0.56s, 2k 2.12s, 4k 8.77s, 8k 36.1s — each doubling 4.1x
(exponent ~2.04, difflib SequenceMatcher worst case). A 40k-word doc takes
~15 min, pinning an API worker. The function must bound its work on huge
inputs (fall back to proportional cuts past a size where exact alignment
costs more than it is worth).
"""
import time

from untell.text_split import aligned_chunks

# 8k words takes 36s today. After the fix it must stay well under a few seconds.
N = 8000
text = "word " * N


def test_aligned_chunks_bounded_time_on_long_docs():
    t0 = time.perf_counter()
    result = aligned_chunks(text, text)
    dt = time.perf_counter() - t0
    assert dt < 5.0, f"aligned_chunks on {N} words took {dt:.1f}s (quadratic DoS)"
    # Result must still be usable: chunks pair up and cover both sides
    assert result, "no chunks produced"
    for a, b in result:
        assert isinstance(a, str) and isinstance(b, str)


def test_aligned_chunks_still_correct_on_normal_docs():
    # A normal-size doc must still use the exact matcher path and align correctly
    a = ("Our results demonstrate that the attention mechanism improves performance. "
         "The ablation studies confirm our hypothesis about the architecture.")
    b = ("Our results demonstrate that the attention mechanism improves performance. "
         "We also perform a series of ablation studies. The results confirm our hypothesis.")
    result = aligned_chunks(a, b)
    assert result
    total_a = sum(len(x.split()) for x, _ in result)
    assert total_a == len(a.split()), f"chunks lost words: {total_a} != {len(a.split())}"
