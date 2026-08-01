"""Tests for the contradiction veto.

Logic is tested with fakes so the suite stays fast; the real-model behaviour is pinned by one
torch-gated test, because the whole point of this module is a property of the actual model.
"""
from __future__ import annotations

import pytest

from untell.scripts import entailment


def test_unavailable_degrades_to_no_veto(monkeypatch):
    """A missing model must NOT turn into a silent veto that rejects every candidate."""
    monkeypatch.setattr(entailment, "available", lambda: False)
    assert entailment.contradiction_score("a", "b") is None
    assert entailment.contradicts("a", "b") is False


def test_disable_env_var_turns_it_off(monkeypatch):
    monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
    monkeypatch.setattr(entailment._NLI, "dead", False)
    assert entailment.available() is False


def test_empty_text_is_never_a_contradiction(monkeypatch):
    monkeypatch.setattr(entailment, "available", lambda: True)
    assert entailment.contradiction_score("", "something") is None
    assert entailment.contradiction_score("something", "   ") is None


def test_model_failure_disables_veto_without_raising(monkeypatch):
    """One failure must disable the veto for the process, not raise per candidate."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment._NLI, "dead", False)
    monkeypatch.setattr(entailment._NLI, "warned", False)

    def _boom(*a, **k):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(entailment, "_pair_probs", _boom)
    assert entailment.contradiction_score("a b c", "d e f") is None
    assert entailment._NLI.dead is True


def test_takes_max_across_both_directions(monkeypatch):
    """Contradiction is not symmetric in the model output; either direction is disqualifying."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment._NLI, "dead", False)
    monkeypatch.setattr(entailment._NLI, "label_idx", {"contradiction": 0, "entailment": 1, "neutral": 2})

    calls = {"n": 0}

    def _fake(premise, hypothesis):
        calls["n"] += 1
        # forward looks innocent, backward is a clear contradiction
        return [0.01, 0.9, 0.09] if calls["n"] == 1 else [0.95, 0.02, 0.03]

    monkeypatch.setattr(entailment, "_pair_probs", _fake)
    monkeypatch.setattr(entailment, "_load", lambda: (None, None))
    assert entailment.contradiction_score("a b", "c d") == pytest.approx(0.95)
    assert entailment.contradicts("a b", "c d") is True


def test_bar_is_respected(monkeypatch):
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.4)
    assert entailment.contradicts("a", "b", bar=0.5) is False
    assert entailment.contradicts("a", "b", bar=0.3) is True


def test_real_model_vetoes_inversion_but_not_register_shift():
    """The property the module exists for, against the real model.

    Embedding similarity rates "runs faster" vs "runs slower" at 0.974 — it sails through the 0.76
    meaning gate. The veto must catch it, while leaving a faithful formal->casual rewrite alone.
    """
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    if not entailment.available():
        pytest.skip("NLI stack unavailable")

    inverted = (
        "The build runs significantly faster after the change.",
        "The build runs significantly slower after the change.",
    )
    faithful = (
        "Organizations use these tools to improve operational efficiency.",
        "Companies rely on this stuff to run things better.",
    )
    try:
        inv_score = entailment.contradiction_score(*inverted)
        ok_score = entailment.contradiction_score(*faithful)
    except Exception:
        pytest.skip("NLI model failed to load")
    if inv_score is None or ok_score is None:
        pytest.skip("NLI model unavailable")

    assert inv_score > 0.5, f"meaning inversion not caught (got {inv_score})"
    assert ok_score < 0.5, f"faithful register shift wrongly vetoed (got {ok_score})"
    assert entailment.contradicts(*inverted) is True
    assert entailment.contradicts(*faithful) is False
