"""An optional model that cannot load must return None, not raise.

`method()` is written as `"embedding" if _st_model() is not None else "token_overlap"`, so None is
the documented answer for "unavailable". Raising is not one of the options — and `recommended_bar()`
is called at MODULE level by `test_documented_thresholds_are_the_real_ones`, so an exception there
aborts pytest collection and the whole suite fails before a single test runs.

MEASURED: with torch, transformers and sentence-transformers installed but no model cached, the
constructor reaches the network. A proxy that refuses the CONNECT returns `httpx.ProxyError`, which
is an `httpx.HTTPError` and therefore neither `ImportError` nor `OSError` — the two the guard used
to catch. One unreachable host took out the entire run.
"""

from __future__ import annotations

import pytest

from untell.scripts import quality


class _ProxyRefused(Exception):
    """Stands in for `httpx.ProxyError`: not an OSError, not an ImportError, raised from the
    constructor rather than the import."""


@pytest.fixture(autouse=True)
def _clear_model_cache(monkeypatch):
    """`_st_model` memoises into a module global, including the None. Every case here needs a cold
    start or it measures the previous test's answer."""
    monkeypatch.setattr(quality, "_model", quality._UNSET)
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)


def _raise_on_construct(monkeypatch, exc: type[BaseException]) -> None:
    import sys
    import types

    module = types.ModuleType("sentence_transformers")

    def _boom(*_a, **_k):
        raise exc("model could not be fetched")

    module.SentenceTransformer = _boom
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def test_a_network_failure_while_loading_the_model_is_not_an_exception(monkeypatch):
    """The exact shape that aborted collection: a non-OSError raised by the constructor."""
    _raise_on_construct(monkeypatch, _ProxyRefused)
    assert quality._st_model() is None


def test_the_method_falls_back_to_token_overlap_rather_than_propagating(monkeypatch):
    """What the caller sees. `recommended_bar()` runs at import time in another module, so this is
    the difference between a degraded run and no run at all."""
    _raise_on_construct(monkeypatch, _ProxyRefused)
    assert quality.method() == "token_overlap"
    assert isinstance(quality.recommended_bar(), float)


def test_a_missing_package_still_falls_back(monkeypatch):
    """The case that always worked, kept so the broadened guard is not the only thing tested."""
    import sys

    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert quality._st_model() is None


def test_the_lite_env_gate_still_short_circuits_before_any_load(monkeypatch):
    """The documented stdlib path must not be disturbed by widening the exception guard: it returns
    before the import, which is what keeps ~20s of torch imports out of a lite run."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")

    def _should_not_run(*_a, **_k):
        raise AssertionError("the env gate must return before anything is imported")

    import sys
    import types

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _should_not_run
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    assert quality._st_model() is None
