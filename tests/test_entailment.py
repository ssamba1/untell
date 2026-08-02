"""Tests for the contradiction veto.

Logic is tested with fakes so the suite stays fast; the real-model behaviour is pinned by one
torch-gated test, because the whole point of this module is a property of the actual model.
"""
from __future__ import annotations

import json

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


# --------------------------------------------------------------------------- entailment / gate
def test_entailment_takes_min_of_both_directions(monkeypatch):
    """min() is what makes this meaning-PRESERVATION rather than one-way implication: a truncation
    entails its source in one direction only."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment._NLI, "dead", False)
    monkeypatch.setattr(entailment._NLI, "label_idx", {"contradiction": 0, "entailment": 1, "neutral": 2})
    monkeypatch.setattr(entailment, "_load", lambda: (None, None))

    calls = {"n": 0}

    def _fake(premise, hypothesis):
        calls["n"] += 1
        # forward entails strongly, backward does not (information was dropped)
        return [0.01, 0.95, 0.04] if calls["n"] == 1 else [0.02, 0.03, 0.95]

    monkeypatch.setattr(entailment, "_pair_probs", _fake)
    assert entailment.entailment_score("a", "b") == pytest.approx(0.03)


def test_gate_falls_back_to_strict_similarity_without_nli(monkeypatch):
    """No NLI means nothing to lean on — loosening the bar would be pure risk, since the metric that
    would have to catch bad rewrites is the one measured to be blind to them."""
    monkeypatch.setattr(entailment, "available", lambda: False)
    assert entailment.meaning_preserved("a", "b", sim=0.80, strict_sim_bar=0.76) is True
    assert entailment.meaning_preserved("a", "b", sim=0.50, strict_sim_bar=0.76) is False


def test_gate_falls_back_to_strict_when_model_dies_midrun(monkeypatch):
    """A model that dies mid-run must not silently become a permissive gate."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: None)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: None)
    assert entailment.meaning_preserved("a", "b", sim=0.50, strict_sim_bar=0.76) is False


def test_gate_admits_faithful_register_shift_and_rejects_inversion(monkeypatch):
    monkeypatch.setattr(entailment, "available", lambda: True)

    # Faithful: low similarity (register changed) but no contradiction and real entailment.
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.006)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: 0.858)
    assert entailment.meaning_preserved("a", "b", sim=0.578, strict_sim_bar=0.76) is True

    # Inverted: high similarity but a clear contradiction.
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.997)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: 0.001)
    assert entailment.meaning_preserved("a", "b", sim=0.974, strict_sim_bar=0.76) is False


def test_gate_rejects_information_loss_that_is_not_a_contradiction(monkeypatch):
    """Truncation contradicts nothing (contra 0.060) but does not entail (ent 0.002)."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.060)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: 0.002)
    assert entailment.meaning_preserved("a", "b", sim=0.556, strict_sim_bar=0.76) is False


def test_gate_still_rejects_gross_topic_drift(monkeypatch):
    """NLI can rate an unrelated sentence merely 'neutral', so the relaxed similarity floor remains
    as the gross-drift catch."""
    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.01)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: 0.90)
    assert entailment.meaning_preserved("a", "b", sim=0.05, strict_sim_bar=0.76) is False


def test_real_model_gate_beats_similarity_alone_on_both_axes():
    """The headline claim, against the real model: more faithful rewrites admitted AND fewer bad."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    if not entailment.available():
        pytest.skip("NLI stack unavailable")

    from untell.scripts.quality import similarity

    good = [
        ("Organizations use these tools to improve operational efficiency.",
         "Companies rely on this stuff to run things better."),
        ("Furthermore, adoption rates continue to increase steadily.",
         "Also, more people keep signing up."),
    ]
    bad = [
        ("The build runs significantly faster after the change.",
         "The build runs significantly slower after the change."),
        ("The cat sat on the mat and watched the rain fall outside.",
         "The cat sat somewhere."),
    ]
    try:
        new_good = sum(1 for a, b in good if entailment.meaning_preserved(a, b, similarity(a, b), 0.76))
        new_bad = sum(1 for a, b in bad if entailment.meaning_preserved(a, b, similarity(a, b), 0.76))
    except Exception:
        pytest.skip("NLI model failed to load")

    old_bad = sum(1 for a, b in bad if similarity(a, b) >= 0.76)

    assert new_good == len(good), "faithful register shifts must be admitted"
    assert new_bad == 0, "no meaning-lost rewrite may pass"
    assert old_bad > 0, "probe set must actually contain a case the old gate let through"


class TestEntailmentCLI:
    """The CLI exists so SKILL.md can reach this gate; the skill path previously had no meaning
    check at all and gated on cosine similarity alone."""

    def test_help_exits_zero(self, capsys):
        assert entailment.main(["--help"]) == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_missing_args_is_usage_error(self):
        # 2, not 1 — a caller must be able to tell "you called me wrong" from "meaning changed".
        assert entailment.main([]) == 2
        assert entailment.main(["only one"]) == 2

    def test_output_is_valid_json_with_required_keys(self, capsys):
        entailment.main(["The cat sat on the mat.", "A cat was sitting on the mat."])
        payload = json.loads(capsys.readouterr().out)
        assert {"available", "contradiction", "entailment", "preserved"} <= set(payload)
        assert isinstance(payload["preserved"], bool)

    def test_exit_code_matches_preserved_field(self, capsys):
        """The exit code is the contract for shell callers — it must not disagree with the JSON."""
        for a, b in [
            ("The cat sat on the mat.", "A cat was sitting on the mat."),
            ("The build runs faster.", "The build runs slower."),
        ]:
            code = entailment.main([a, b])
            payload = json.loads(capsys.readouterr().out)
            assert code == (0 if payload["preserved"] else 1)

    def test_unavailable_model_skips_rather_than_rejects(self, capsys, monkeypatch):
        """No model must mean "cannot judge", not "reject everything" — otherwise installing fewer
        extras would silently block every rewrite the skill proposes."""
        monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: None)
        monkeypatch.setattr(entailment, "entailment_score", lambda a, b: None)
        assert entailment.main(["anything", "anything else"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["available"] is False and payload["preserved"] is True

    @pytest.mark.skipif(not entailment.available(), reason="NLI model not installed")
    def test_rejects_inversion_that_similarity_accepts(self, capsys):
        """The reason this gate exists: cosine scores this pair ~0.97, above the 0.76 bar."""
        assert entailment.main(["The build runs faster.", "The build runs slower."]) == 1
        assert json.loads(capsys.readouterr().out)["contradiction"] > 0.5


class TestModelFreeChecksRunWithoutNLI:
    """The stdlib-only gates must not be gated behind the NLI model's availability.

    `meaning_preserved` used to return `sim >= strict_sim_bar` the moment NLI was unavailable —
    before reaching the quantity and certainty checks. Both are pure regex and need no model, so on
    the zero-dependency tier (the advertised default) a rewrite could drop a stated number or
    upgrade a hedged claim and nothing would object.
    """

    @pytest.mark.parametrize(
        ("source", "candidate", "label"),
        [
            ("Only 7 of the 19 tests passed.", "Only a few of the 19 tests passed.", "drops a number"),
            ("The drug may cause drowsiness.", "The drug causes drowsiness.", "drops a hedge"),
            ("Screen time is correlated with poor sleep.", "Screen time causes poor sleep.", "causal upgrade"),
            ("The study found an effect.", "The study found a large effect.", "intensifier added"),
        ],
    )
    def test_bad_rewrites_rejected_without_nli(self, source, candidate, label, monkeypatch):
        monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
        assert not entailment.available()
        assert not entailment.meaning_preserved(source, candidate, 0.95, strict_sim_bar=0.76), label

    @pytest.mark.parametrize(
        ("source", "candidate", "label"),
        [
            ("Only 7 of the 19 tests passed.", "Just 7 of the 19 tests passed.", "faithful"),
            ("The drug may cause drowsiness.", "The drug might make you drowsy.", "hedge swap"),
        ],
    )
    def test_faithful_rewrites_still_pass_without_nli(self, source, candidate, label, monkeypatch):
        monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
        assert entailment.meaning_preserved(source, candidate, 0.95, strict_sim_bar=0.76), label

    def test_mechanical_checks_precede_the_model(self):
        """Also the cheap order: a candidate rejected mechanically skips four NLI forward passes and
        a spaCy parse. All checks are conjunctive, so order cannot change the verdict, only cost."""
        import inspect

        src = inspect.getsource(entailment.meaning_preserved)
        assert src.index("numbers_kept") < src.index("if not available()")
        assert src.index("certainty_kept") < src.index("if not available()")
