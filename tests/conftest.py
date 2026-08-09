"""Shared fixtures.

`stdlib_lite` exists because three tests assert numbers that are only true of the pure-Python
lite scorer, and they were reading that path out of the ambient environment instead of asking for
it. They passed locally with UNTELL_LITE_NO_TORCH=1 exported and failed under a plain `pytest` on
a machine with torch installed — which is exactly what CI's full-tier job runs.

Deliberately opt-in rather than autouse. Forcing the stdlib path for the whole suite would hide
the torch-backed scorer from every test that should be exercising it.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def stdlib_lite(monkeypatch):
    """Pin the lite tier to its pure-Python implementation for the duration of one test."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.scripts import score as score_mod

    for name in ("score_text", "batch_score_texts"):
        fn = getattr(score_mod, name, None)
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()
    yield
    for name in ("score_text", "batch_score_texts"):
        fn = getattr(score_mod, name, None)
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()
