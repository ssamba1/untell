"""The lazy BERTScore loader must load, not return the unset sentinel.

quality.py:71: `if _bs_model is not _UNSET: return _bs_model` — the first call
loads the scorer and caches it. The mutation is not -> is makes the guard fire
on the INITIAL state, so the first call returns the _UNSET sentinel object
instead of loading. Callers that treat a None return as 'unavailable' would
get a sentinel that is neither a scorer nor None.
"""
import untell.scripts.quality as quality


def test_first_call_loads_instead_of_returning_sentinel():
    old = quality._bs_model
    quality._bs_model = quality._UNSET
    try:
        result = quality._bs_scorer()
        assert result is not quality._UNSET, "first call returned the unset sentinel"
    finally:
        quality._bs_model = old


def test_cached_call_returns_cached():
    old = quality._bs_model
    quality._bs_model = object()  # any cached non-sentinel value
    try:
        assert quality._bs_scorer() is quality._bs_model
    finally:
        quality._bs_model = old
