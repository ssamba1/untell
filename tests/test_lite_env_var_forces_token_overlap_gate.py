"""UNTELL_LITE_NO_TORCH=1 must actually force the stdlib similarity gate.

quality._st_model() ignored the env var: whenever sentence-transformers was
installed it loaded MiniLM anyway, so "lite" ran ~20s of torch imports plus an
embedding encode per comparison while being documented (README + the fallback
note at quality.py:234) as token-overlap. MEASURED on the slice12 corpus bench:
a 309-word flagged doc took 13.19s with embeddings live vs 0.69s on the true
stdlib path. The env gate must be checked before the cached model, so a test
that flips the variable mid-process still gets the stdlib gate.
"""
from __future__ import annotations

import untell.scripts.quality as quality


def test_env_var_forces_token_overlap_even_when_a_model_is_cached(monkeypatch):
    # A model is already loaded (e.g. an earlier test ran the embedding path)…
    monkeypatch.setattr(quality, "_model", object())
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert quality._st_model() is None
    assert quality.method() == "token_overlap"
    assert quality.recommended_bar() == quality.TOKEN_BAR
    # …and the cached model is untouched, so unsetting the var restores it.
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH")
    assert quality._st_model() is not None
    # Leave the module cache clean for later tests.
    monkeypatch.setattr(quality, "_model", quality._UNSET)


def test_env_var_short_circuits_before_any_import(monkeypatch):
    """The gate must fire before sentence-transformers is imported/constructed:
    that is the whole point — a lite run must not pay torch's ~20s import."""
    import builtins

    real_import = builtins.__import__

    def spy_import(name, *a, **kw):
        assert "sentence_transformers" not in name, (
            f"sentence_transformers was imported under UNTELL_LITE_NO_TORCH=1 ({name})"
        )
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", spy_import)
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(quality, "_model", quality._UNSET)
    assert quality._st_model() is None
    assert quality.method() == "token_overlap"