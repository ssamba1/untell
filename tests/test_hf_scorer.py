"""`hf:<model>` — which label means AI is never guessed, and no repository code is run."""

from __future__ import annotations

import inspect

import pytest

from untell.evidence import hf_scorer as H


def test_a_model_with_no_known_ai_label_is_refused():
    with pytest.raises(ValueError, match="#<label"):
        H._parse("someone/unknown-detector")


def test_an_explicit_index_is_honoured():
    model, spec = H._parse("someone/unknown-detector#1")
    assert model == "someone/unknown-detector" and spec.ai_index == 1


def test_every_curated_entry_says_where_its_label_came_from():
    for model, spec in H.KNOWN.items():
        assert spec.note, model
        assert spec.ai_index in (0, 1)


def test_the_openai_detectors_map_fake_to_ai():
    assert H.KNOWN["openai-community/roberta-base-openai-detector"].ai_index == 0
    assert H.KNOWN["openai-community/roberta-large-openai-detector"].ai_index == 0


def test_no_remote_code_is_ever_enabled():
    src = inspect.getsource(H)
    assert "trust_remote_code=True" not in src


def test_the_spec_is_wired_into_the_resolver():
    from untell.evidence import scorers
    assert 'spec.startswith("hf:")' in inspect.getsource(scorers.resolve_scorer)
