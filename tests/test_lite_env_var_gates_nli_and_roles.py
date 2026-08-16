"""UNTELL_LITE_NO_TORCH=1 must also gate the model-backed meaning gates.

The env var is documented (README env table) as "force the pure-stdlib lite path even
when torch is installed", and it already gates the perplexity detector and the quality
gate's embedding backend. It did NOT gate the two model-backed meaning gates:

- `entailment.available()` imported torch + transformers and `meaning_preserved` then
  loaded the ~330MB NLI cross-encoder and ran four forward passes per candidate —
  the loop's most expensive gate — on a run documented as stdlib-only.
- `roles.available()` / `parser_available()` / `role_swap` loaded spaCy, and spaCy
  imports torch itself through thinc (`thinc.shims.pytorch`), so "no torch" was
  doubly violated.

MEASURED on this machine (torch 2.12.1+cpu, spacy + en_core_web_sm installed): a
`score_text(tier="lite")` call under the env var took ~9-17s and imported spacy+torch;
with the heavy paths genuinely skipped the same call completes in ~0.13s. All three
fixes below return the "unavailable" answer WITHOUT importing anything.
"""
from __future__ import annotations

import builtins

from untell.scripts import entailment, roles
from untell.scripts.entailment import meaning_preserved


def _no_heavy_imports(monkeypatch, libs):
    """Fail the test if any of `libs` (top-level names) is imported."""
    real_import = builtins.__import__

    def spy_import(name, *a, **kw):
        top = name.split(".")[0]
        assert top not in libs, (
            f"{name} was imported under UNTELL_LITE_NO_TORCH=1"
        )
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", spy_import)


def test_env_var_turns_off_the_nli_veto(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(entailment._NLI, "dead", False)
    assert entailment.available() is False


def test_env_var_gates_nli_before_any_import(monkeypatch):
    """The whole point: a lite run must not pay torch/transformers' import."""
    _no_heavy_imports(monkeypatch, {"torch", "transformers"})
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert entailment.available() is False


def test_env_var_turns_off_the_role_check(monkeypatch):
    _no_heavy_imports(monkeypatch, {"spacy"})
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert roles.available() is False
    assert roles.parser_available() is False


def test_env_var_makes_role_swap_unknown_without_loading_spacy(monkeypatch):
    """role_swap returns None ("unknown", never a pass) and imports nothing."""
    _no_heavy_imports(monkeypatch, {"spacy"})
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert roles.role_swap("The company sued the regulator.", "The regulator sued the company.") is None


def test_meaning_preserved_falls_back_to_the_strict_bar_under_the_env_var(monkeypatch):
    """With NLI gated off, meaning_preserved must use the strict similarity bar and
    must NOT reach the NLI model (which would defeat the gate)."""
    _no_heavy_imports(monkeypatch, {"torch", "transformers"})
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")

    # A faithful pair above the strict bar passes…
    assert meaning_preserved(
        "The build runs faster after the change.",
        "The build runs quicker after the change.",
        0.90, 0.76,
    ) is True
    # …and the same pair below the strict bar is rejected, exactly as the
    # similarity-only path documents.
    assert meaning_preserved(
        "The build runs faster after the change.",
        "The build runs quicker after the change.",
        0.40, 0.76,
    ) is False


def test_the_loop_names_the_weakened_gate_under_the_env_var(monkeypatch):
    """End to end: a lite loop under the env var reports the similarity-only gate,
    not "nli" — the run must not claim a guarantee it did not enforce."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    r = untell_text(
        "Furthermore, the system leverages robust methodologies to optimize outcomes today.",
        tier="lite", threshold=0.30, max_iters=1,
        rewriter=get_rewriter(prefer="surgical"),
    )
    assert r["meaning_gate"] == "similarity-only (NLI unavailable)"
