"""Fast pure-math tests for the per-sentence surprisal grouping (`_per_sentence_means`).

``_full_score`` groups the in-context token surprisals by sentence (character
offsets from the tokenizer vs. sentence spans from ``text.find``) and averages
each group. The original implementation walked every token for every sentence —
O(S*T) — which measured 2.1 s of pure Python on a 3,900-token HC3 document with
149 sentences (see goals/results/20260815_204928-5.md, slice 5). The replacement
uses bisect on the offset arrays (token offsets are emitted in document order, so
each sentence's tokens form one contiguous index range).

This file pins the helper against a naive reference implementation (the exact
predicate the old loop applied) so the two can never drift apart. Runs with zero
model loads and no torch requirement (plain lists are accepted).
"""

from __future__ import annotations

import pytest

from untell.detectors.perplexity_burstiness import _per_sentence_means


def _naive(nll, offsets, bounds, min_tokens=3):
    """Reference: the exact predicate the pre-bisect loop applied."""
    out = []
    for start, end in bounds:
        vals = [float(v) for v, (a, b) in zip(nll, offsets) if a >= start and b <= end and b > a]
        if len(vals) >= min_tokens:
            out.append(sum(vals) / len(vals))
    return out


def _dense_tokens(text_len: int, span: int = 4):
    """Synthetic dense tokenization: T tokens of equal width over the text."""
    offsets = [(i * span, i * span + span) for i in range(text_len)]
    nll = [0.5 + 0.1 * (i % 7) for i in range(text_len)]  # deterministic non-trivial values
    return nll, offsets


def test_matches_naive_on_contiguous_sentences():
    nll, offsets = _dense_tokens(100)
    bounds = [(0, 20), (20, 44), (44, 100)]
    assert _per_sentence_means(nll, offsets, bounds) == _naive(nll, offsets, bounds)


def test_zero_width_tokens_are_excluded():
    # a zero-width token (a == b) must be excluded by the b > a guard, as in the
    # original predicate — its position is inside a sentence but it spans nothing.
    nll = [0.1, 0.2, 0.3, 0.4]
    offsets = [(0, 2), (2, 2), (2, 4), (4, 6)]  # token 1 is zero-width
    bounds = [(0, 6)]
    assert _per_sentence_means(nll, offsets, bounds) == _naive(nll, offsets, bounds)


def test_token_spanning_sentence_start_is_excluded():
    # a token that starts before the sentence (a < start) but ends inside it must
    # be excluded — the sentence's surprisal is about its own tokens.
    nll = [0.1, 0.2, 0.3]
    offsets = [(0, 3), (3, 5), (5, 8)]
    bounds = [(2, 8)]  # first token starts at 0 < 2 → excluded
    assert _per_sentence_means(nll, offsets, bounds) == _naive(nll, offsets, bounds)


def test_overlapping_bounds_are_handled():
    # text.find-based bounds can overlap in degenerate cases; both sentences keep
    # their own tokens, exactly as the predicate defines them.
    nll, offsets = _dense_tokens(30)
    bounds = [(4, 16), (10, 24)]
    assert _per_sentence_means(nll, offsets, bounds) == _naive(nll, offsets, bounds)


def test_short_sentences_are_dropped():
    # fewer than 3 tokens → no burstiness data, matching the >= 3 guard.
    nll, offsets = _dense_tokens(12)
    bounds = [(0, 4), (4, 20), (20, 48)]
    means = _per_sentence_means(nll, offsets, bounds)
    naive = _naive(nll, offsets, bounds)
    assert means == naive
    assert len(means) < len(bounds)  # the 1-token sentence is dropped in both


def test_empty_bounds_and_empty_tokens():
    assert _per_sentence_means([], [], []) == []
    nll, offsets = _dense_tokens(10)
    assert _per_sentence_means(nll, offsets, []) == []


def test_accepts_torch_tensors():
    # the real call site passes a torch tensor for nll; .tolist() must be used.
    torch = pytest.importorskip("torch")
    nll, offsets = _dense_tokens(20)
    t = torch.tensor(nll, dtype=torch.float32)
    bounds = [(0, 80)]
    # the naive reference must see the same float32-rounded values the tensor carries
    assert _per_sentence_means(t, offsets, bounds) == _naive(t.tolist(), offsets, bounds)
