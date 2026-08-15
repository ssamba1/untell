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


def test_aligned_chunks_cover_both_sides_when_nothing_matches():
    """A fully disjoint pair (the 'replaced a whole sentence with unrelated text' case) has NO
    difflib blocks, so every cut mapped through the sentinel to len(b) — the first chunk took the
    source's first window against ALL of the target, dropping the rest of the source. MEASURED
    before the fix: a 300-word source vs a 300-word disjoint target produced ONE chunk of 75
    source words vs 300 target words. Both sides must still be chunked proportionally and fully
    covered."""
    a = " ".join(f"alpha{i}" for i in range(300))
    b = " ".join(f"beta{i}" for i in range(300))
    result = aligned_chunks(a, b)
    assert len(result) > 1, "disjoint pair collapsed to one chunk"
    assert sum(len(x.split()) for x, _ in result) == len(a.split()), "source not fully covered"
    assert sum(len(y.split()) for _, y in result) == len(b.split()), "target not fully covered"
    for x, y in result:
        assert len(x.split()) <= 90 and len(y.split()) <= 90, "a chunk exceeded the token budget"
