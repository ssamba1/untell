"""Identical long pairs skip the difflib matcher entirely.

``aligned_chunks(a, a)`` on a long document is a real call path — the meaning gates score
(original, rewrite) and also (doc, doc): ``contradiction_score(doc, doc)`` is measured at
0.6091 on a 301-word RAID abstract in entailment.py, and ``similarity(t, t)`` recurses into
identical chunk pairs. On identical input the difflib result is ONE full matching block, so
``map_index`` is the identity and the output is exactly the proportional cuts — but only
after paying O(n*m). MEASURED before the fast path, on identical input:

    words   1000    2000    4000    6000
    time    0.42s   1.81s   7.44s   20.06s

After: ~1ms at every size, with byte-identical output (verified against the difflib path on
181/500/1000/3000-word identical pairs, both single-word and varied vocabulary).

The threshold keeps the mutation guards (100/181-word identical fixtures) on the difflib
path; below 1000 words the exact matcher is under half a second and the guard coverage is
worth it.
"""
import time
from unittest.mock import patch

from untell.text_split import aligned_chunks


def test_identical_long_pair_is_fast():
    """A 6000-word doc scored against itself must not take 20 seconds of alignment."""
    text = "word " * 6000
    t0 = time.perf_counter()
    result = aligned_chunks(text, text)
    dt = time.perf_counter() - t0
    assert dt < 2.0, f"identical 6000w took {dt:.2f}s (quadratic difflib path)"
    assert result, "no chunks produced"


def test_identical_long_pair_never_constructs_the_matcher():
    """The fast path must not touch difflib at all.

    If a future edit routes identical pairs back through SequenceMatcher, the quadratic cost
    returns AND this pin fails — difflib would raise here instead of being skipped.
    """
    text = " ".join(f"w{i % 250}" for i in range(2000))
    with patch("difflib.SequenceMatcher", side_effect=AssertionError("difflib called")):
        result = aligned_chunks(text, text)
    assert result


def test_identical_long_pair_chunks_match_the_difflib_shape():
    """The fast path must produce the same chunk structure the difflib path produced.

    Coverage and the CHUNK_WORDS bound are the contract the gates depend on; chunk count
    matches ceil(n / CHUNK_WORDS), the same k the difflib path computes.
    """
    n = 4000
    text = " ".join(f"w{i % 250}" for i in range(n))
    result = aligned_chunks(text, text)
    assert len(result) == -(-n // 90), f"expected {-(-n // 90)} chunks, got {len(result)}"
    assert sum(len(a.split()) for a, _ in result) == n, "source words lost"
    assert sum(len(b.split()) for _, b in result) == n, "target words lost"
    assert all(len(a.split()) <= 90 and len(b.split()) <= 90 for a, b in result)


def test_identical_short_pair_still_uses_the_exact_path():
    """Below the threshold the difflib path must be untouched (mutation guards depend on it)."""
    text = " ".join(f"w{i}" for i in range(100))
    with patch("difflib.SequenceMatcher") as fake:
        aligned_chunks(text, text)
    assert fake.called, "sub-1000-word identical pair should still construct the matcher"
