"""Entailment module paths the model-gated tests do not reach: the unavailable
branches, the label-resolution warmup calls, the failure-disable path, and the two
mechanical meaning-gate rejections that fire before any model is consulted."""

from __future__ import annotations

import logging

import pytest

from untell.scripts import entailment


@pytest.fixture
def fresh_nli(monkeypatch):
    """Reset the module-level model cache so each test starts from a live state."""
    monkeypatch.setattr(entailment._NLI, "tok", None)
    monkeypatch.setattr(entailment._NLI, "model", None)
    monkeypatch.setattr(entailment._NLI, "label_idx", None)
    monkeypatch.setattr(entailment._NLI, "dead", False)
    monkeypatch.setattr(entailment._NLI, "warned", False)
    monkeypatch.delenv("UNTELL_DISABLE_NLI", raising=False)
    # UNTELL_LITE_NO_TORCH gates the whole NLI stack off (a140e37); these tests pin
    # the code BEHIND that gate, so the ambient lite setting must not short-circuit.
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)


def test_available_refuses_when_disabled_by_env(fresh_nli, monkeypatch) -> None:
    monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
    assert entailment.available() is False


def test_available_refuses_under_the_lite_env_gate(fresh_nli, monkeypatch) -> None:
    """UNTELL_LITE_NO_TORCH=1 is the documented stdlib path; the NLI veto is a model
    check and must not load torch for it (a140e37)."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert entailment.available() is False


def test_available_is_false_once_dead(fresh_nli, monkeypatch) -> None:
    monkeypatch.setattr(entailment._NLI, "dead", True)
    assert entailment.available() is False


def test_contradiction_resolves_labels_with_a_warmup_call(fresh_nli, monkeypatch) -> None:
    """With label_idx unresolved, one forward pass runs to discover the label order.

    The pass's result is discarded when the labels still cannot be resolved — the
    function reports None (unknown) rather than guessing an index order.
    """
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        entailment, "_pair_probs", lambda a, b: calls.append((a, b)) or [0.1, 0.2, 0.7]
    )
    assert entailment.contradiction_score("the cat sat", "the cat slept") is None
    assert len(calls) == 1


def test_entailment_resolves_labels_with_a_warmup_call(fresh_nli, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        entailment, "_pair_probs", lambda a, b: calls.append((a, b)) or [0.1, 0.2, 0.7]
    )
    assert entailment.entailment_score("the cat sat", "the cat slept") is None
    assert len(calls) == 1


def test_a_raising_model_disables_the_veto_and_says_so_once(
    fresh_nli, monkeypatch, caplog
) -> None:
    def boom(a, b):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(entailment, "_pair_probs", boom)
    monkeypatch.setattr(entailment._NLI, "label_idx", {"contradiction": 2, "entailment": 0})
    with caplog.at_level(logging.WARNING, logger="untell.scripts.entailment"):
        assert entailment.contradiction_score("x y", "x z") is None
        assert entailment._NLI.dead is True
        assert entailment._NLI.warned is True
        assert "meaning inversions will NOT be caught" in caplog.text
        # The second failure must not repeat the warning.
        assert entailment.entailment_score("x y", "x z") is None
    assert caplog.text.count("will NOT be caught") == 1


def test_meaning_preserved_rejects_a_polarity_flip(fresh_nli, monkeypatch) -> None:
    """Negation changes fail the mechanical polarity check before any model runs."""
    assert (
        entailment.meaning_preserved(
            "The system is not active.", "The system is active.",
            sim=0.99, strict_sim_bar=0.76,
        )
        is False
    )


def test_meaning_preserved_rejects_deletion_over_the_allowance(fresh_nli) -> None:
    source = "The committee reviewed the proposal and approved the funding. " * 12
    candidate = "The committee reviewed the proposal."
    assert (
        entailment.meaning_preserved(source, candidate, sim=0.9, strict_sim_bar=0.76)
        is False
    )


def test_cli_unavailable_reports_json_and_exits_zero(fresh_nli, capsys, monkeypatch) -> None:
    """Without the model the CLI says available:false and exits 0 (unknown, not failure)."""
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: None)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: None)
    assert entailment.main(["first sentence", "second sentence"]) == 0
    out = capsys.readouterr().out
    assert '"available": false' in out
    assert '"preserved": true' in out


def test_cli_usage_error_exits_two(caplog) -> None:
    assert entailment.main(["only-one-arg"]) == 2
    assert any("usage: entailment.py" in r.message for r in caplog.records)
