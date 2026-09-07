"""Remaining boundary survivors in the sentence splitter and the API server.

Every fixture sits ON its constant, with a neighbour either side. `_MIN_SPLIT_SIDE` appears three
times in `structural.py` and each occurrence is a separate boundary, so each is exercised through
the branch that actually reads it.
"""

from __future__ import annotations

import asyncio
import random

from untell import api_server
from untell.api_server import _HEALTH_TTL_S, _RATE_BUCKET_SOFT_CAP
from untell.rewriter import structural as S
from untell.rewriter.structural import _MIN_SPLIT_SIDE

_WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india",
          "juliet", "kilo", "lima", "mike", "november", "oscar", "papa", "quebec", "romeo",
          "sierra", "tango", "uniform", "victor", "whiskey", "xray", "yankee", "zulu", "apple",
          "bridge", "candle", "dragon", "ember", "forest", "garden", "harbor"]


def _long_sentence(n: int, comma_at: int) -> str:
    """``n`` words with exactly one comma, at index ``comma_at``.

    One comma only: the search takes the comma NEAREST the midpoint, so a second one would decide
    the split point instead of the index under test.
    """
    words = [_WORDS[i].capitalize() if i == 0 else _WORDS[i] for i in range(n)]
    words[comma_at] += ","
    return " ".join(words) + "."


def _was_split(sentence: str) -> bool:
    """True when `_split_long_sentences` actually broke the sentence.

    It returns one string per input either way — a rejected split re-appends the original — so
    the observable is the CONTENT, not the length of the list. Measuring `len(out)` reads as
    "never splits" on every input, which is how a test here can pass while proving nothing.
    """
    random.seed(0)
    out = S._split_long_sentences([sentence], max_words=28, rate=1.0)
    return out[0] != sentence


def test_a_left_half_of_exactly_the_minimum_content_words_is_allowed_to_split():
    """`_content_word_count(words[:split_at]) < _MIN_SPLIT_SIDE` rejects a stranded marker.

    At exactly the minimum the left half is a sentence, and the split stands. Under `<=` the
    rewriter silently declines a legitimate split, and the transform is lost with no diagnostic.
    """
    assert _was_split(_long_sentence(34, comma_at=_MIN_SPLIT_SIDE - 1))


def test_a_left_half_one_content_word_short_is_refused():
    """The neighbour: one under the minimum is a stranded discourse marker, not a sentence."""
    assert not _was_split(_long_sentence(34, comma_at=_MIN_SPLIT_SIDE - 2))


def test_a_right_half_of_exactly_the_minimum_words_is_allowed_to_split():
    """`len(words) - split_at < _MIN_SPLIT_SIDE`, the other half of the same guard.

    The comma sits so the RIGHT side is exactly the minimum. Under `<=` this split is refused.
    """
    n = 34
    assert _was_split(_long_sentence(n, comma_at=n - _MIN_SPLIT_SIDE - 1))


def test_a_right_half_one_word_short_is_refused():
    """The neighbour on the right side."""
    n = 34
    assert not _was_split(_long_sentence(n, comma_at=n - _MIN_SPLIT_SIDE))


def _conjunction_sentence(n_after: int) -> str:
    """A conjunction with exactly ``n_after`` words after it and NO comma anywhere.

    No comma on purpose: with one present the splitter takes the comma and the conjunction branch —
    the line under test — is never reached, so the test would pass either way.
    """
    tail = " ".join(["they", "reported", "modest", "gains", "again", "overall"][:n_after])
    return f"The quarterly revenue rose sharply across every single region but {tail}."


def test_a_clause_of_exactly_the_minimum_length_after_a_conjunction_is_a_split_point():
    """`_words_until_next_comma(words, pos + 1) >= _MIN_SPLIT_SIDE` separates a LIST's coordinator
    from a clause coordinator without a parser.

    At exactly the minimum it is a clause and the sentence splits. Under `>`, a real clause
    boundary is read as a list coordinator and the split is skipped.
    """
    assert S._split_one(_conjunction_sentence(_MIN_SPLIT_SIDE)) is not None


def test_a_clause_one_word_short_of_the_minimum_is_not_a_split_point():
    """The neighbour: one word short reads as a list item, and the sentence is left alone."""
    assert S._split_one(_conjunction_sentence(_MIN_SPLIT_SIDE - 1)) is None


# --- api_server: the health cache TTL ---

def test_a_health_cache_exactly_at_its_ttl_is_stale_and_refreshed(monkeypatch):
    """`now - _health_cache[0] < _HEALTH_TTL_S` decides cached vs recomputed.

    At exactly the TTL the entry has expired and must be refreshed. Under `<=` it is served one
    tick past its own expiry — a cache that outlives its stated lifetime is a cache nobody can
    reason about, and this one reports `detector_tier`, which is what a poller watches for a
    model going away.
    """
    # Anchored at 0.0, not at a large clock value: `1000.0 + (TTL - ulp)` rounds straight back to
    # 1002.0, because doubles near 1002 are spaced ~2.3e-13 while the ulp of 2.0 is ~4.4e-16. The
    # neighbour test below would then measure the same instant as this one.
    start = 0.0
    monkeypatch.setattr(api_server, "_health_cache", (start, {"sentinel": "cached"}))
    monkeypatch.setattr(api_server.time, "monotonic", lambda: start + _HEALTH_TTL_S)
    result = asyncio.run(api_server.health())
    assert result.get("sentinel") != "cached", (
        "an entry exactly at its TTL has expired and must be recomputed")


def test_a_health_cache_a_hair_inside_its_ttl_is_served(monkeypatch):
    """The neighbour, so the refresh above is the TTL and not a cache that never hits."""
    import math
    start = 0.0
    monkeypatch.setattr(api_server, "_health_cache", (start, {"sentinel": "cached"}))
    monkeypatch.setattr(api_server.time, "monotonic",
                        lambda: start + math.nextafter(_HEALTH_TTL_S, 0.0))
    assert asyncio.run(api_server.health()).get("sentinel") == "cached"


def test_the_rate_bucket_soft_cap_sweep_is_an_equivalent_mutant():
    """A fourth boundary that no test can kill, recorded rather than papered over.

    `_evict_stale_buckets` ends::

        if len(_rate_buckets) > _RATE_BUCKET_SOFT_CAP:
            for k, _v in sorted(...)[: len(_rate_buckets) - _RATE_BUCKET_SOFT_CAP]:
                del _rate_buckets[k]

    Under `>=`, a dict sitting exactly at the cap enters the loop — and the slice bound is
    `len - CAP`, which is `[:0]` at equality, so it deletes nothing. Both operators are a no-op
    there. EQUIVALENT, and it stays that way as long as the slice is expressed in terms of the same
    two quantities the guard compares.
    """
    for n in (_RATE_BUCKET_SOFT_CAP, _RATE_BUCKET_SOFT_CAP + 1):
        keys = list(range(n))
        gt = keys[: n - _RATE_BUCKET_SOFT_CAP] if n > _RATE_BUCKET_SOFT_CAP else []
        ge = keys[: n - _RATE_BUCKET_SOFT_CAP] if n >= _RATE_BUCKET_SOFT_CAP else []
        assert gt == ge, (
            f"at len={n} the two operators now drop different buckets — this boundary has become "
            f"reachable and needs a real test")
