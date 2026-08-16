"""Roles-module paths the parser-gated tests do not reach: the unavailable branches,
the dead-parser paths, and the failure-disable path."""

from __future__ import annotations

import importlib.util
import logging
import sys
import types

import pytest

from untell.scripts import roles


@pytest.fixture
def fresh_nlp(monkeypatch):
    """Reset the module-level parser cache so each test starts from a live state."""
    monkeypatch.setattr(roles._NLP, "pipe", None)
    monkeypatch.setattr(roles._NLP, "dead", False)
    monkeypatch.setattr(roles._NLP, "warned", False)
    monkeypatch.delenv("UNTELL_DISABLE_ROLES", raising=False)
    # UNTELL_LITE_NO_TORCH gates the whole role check off (a140e37); these tests pin
    # the code BEHIND that gate, so the ambient lite setting must not short-circuit.
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)


def test_available_refuses_when_disabled_by_env(fresh_nlp, monkeypatch) -> None:
    monkeypatch.setenv("UNTELL_DISABLE_ROLES", "1")
    assert roles.available() is False


def test_lite_env_gate_disables_availability_and_parser_queries(fresh_nlp, monkeypatch) -> None:
    """UNTELL_LITE_NO_TORCH=1 is the documented stdlib path; the role check is spaCy
    backed and must not drag torch in for it (a140e37)."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert roles.available() is False
    assert roles.parser_available() is False
    assert roles.role_swap("the cat sat", "the dog ran") is None


def test_missing_model_disables_the_parser_and_says_so(fresh_nlp, monkeypatch, caplog) -> None:
    """No en_core_web_sm -> parser dead, an info line names the install command."""
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda name: None if name == "en_core_web_sm" else importlib.util.find_spec(name),
    )
    with caplog.at_level(logging.INFO, logger="untell.scripts.roles"):
        assert roles._load() is None
    assert roles._NLP.dead is True
    assert any("spacy download en_core_web_sm" in r.message for r in caplog.records)
    assert roles.available() is False


def test_a_raising_spacy_import_disables_the_parser(fresh_nlp, monkeypatch, caplog) -> None:
    fake_spacy = types.ModuleType("spacy")
    fake_spacy.load = lambda name, **kw: (_ for _ in ()).throw(RuntimeError("spacy exploded"))
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda name: types.SimpleNamespace() if name == "en_core_web_sm" else importlib.util.find_spec(name),
    )
    with caplog.at_level(logging.WARNING, logger="untell.scripts.roles"):
        assert roles._load() is None
    assert roles._NLP.dead is True
    assert any("role swaps will NOT be caught" in r.message for r in caplog.records)


def test_conditional_pair_without_a_parser_is_unknown(fresh_nlp, monkeypatch) -> None:
    monkeypatch.setattr(roles._NLP, "dead", True)
    assert roles._conditional_pair("if it rains, it pours") == (None, None)


def test_a_raising_parse_disables_the_veto_and_says_so_once(
    fresh_nlp, monkeypatch, caplog
) -> None:
    def boom(text):
        raise RuntimeError("parse exploded")

    monkeypatch.setattr(roles._NLP, "pipe", object())  # parser "loaded"
    monkeypatch.setattr(roles, "_analyse", boom)
    with caplog.at_level(logging.WARNING, logger="untell.scripts.roles"):
        assert roles.role_swap("the cat sat", "the dog ran") is None
        assert roles._NLP.dead is True
        assert roles._NLP.warned is True
        assert any("role swaps will NOT be caught" in r.message for r in caplog.records)
        # The second failure must not repeat the warning.
        assert roles.role_swap("a b", "c d") is None
    assert sum("will NOT be caught" in r.message for r in caplog.records) == 1
