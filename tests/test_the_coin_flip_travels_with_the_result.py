"""When per-sentence targeting is near-chance, every caller has to be told, not just the first one.

`score_sentences` already knew: its docstring records per-sentence AUROC 0.493 for the pure-stdlib
path against 0.886-1.000 for the model-backed detectors, and it logs a warning saying the `flagged`
list is close to arbitrary.

The log line fires **once per process**. A long-running API server tells its first request and is
silent for every caller after it, and no HTTP client reads the server's log in any case. So the
strongest caveat this codebase produces — *the output you are reading is a coin flip* — was the one
least likely to reach the person holding the output.

Re-measured over 100 HC3 sentences while adding the field, and the shape is worse than a low AUROC
suggests:

    tier   distinct values / 100 sentences   most common      sentence AUROC
    lite   6                                 0.250 x 91       0.515
    full   39                                0.9992 x 50      0.965

It is not a weak ranking. It is a constant with a few exceptions, sorted.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.sentences import (
    UNINFORMATIVE_TARGETING_WARNING,
    _targeting_is_uninformative,
    score_sentences,
)

TEXT = (
    "It is worth noting that this approach leverages a robust framework. "
    "The parser splits each record and hands it onward. "
    "Salt lowers the freezing point of water, which is why it goes on roads."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_caveat_is_on_the_result_when_it_applies() -> None:
    uninformative = _targeting_is_uninformative("lite")
    result = score_sentences(TEXT, tier="lite")
    assert ("warning" in result) is uninformative
    if uninformative:
        assert result["warning"] == UNINFORMATIVE_TARGETING_WARNING


def test_every_call_carries_it_not_just_the_first(monkeypatch) -> None:
    """The defect. `_WARNED_UNINFORMATIVE` is a module global, so the log line is once per process;
    the field must not inherit that."""
    import untell.scripts.sentences as mod

    monkeypatch.setattr(mod, "_targeting_is_uninformative", lambda tier, modes=None: True)
    monkeypatch.setattr(mod, "_WARNED_UNINFORMATIVE", True)  # as if a previous call already logged
    for _ in range(3):
        assert "warning" in score_sentences(TEXT, tier="lite")


def test_a_ranking_tier_carries_no_caveat(monkeypatch) -> None:
    """Guards the guard. A caveat on every result is a caveat nobody reads."""
    import untell.scripts.sentences as mod

    monkeypatch.setattr(mod, "_targeting_is_uninformative", lambda tier, modes=None: False)
    assert "warning" not in score_sentences(TEXT, tier="lite")


def test_the_note_and_the_warning_are_different_things() -> None:
    """`note` is always present and is about per-sentence noise in general. Folding this into it
    would bury 'these results are arbitrary' inside a sentence that is true of every tier."""
    result = score_sentences(TEXT, tier="lite")
    assert "note" in result
    assert result.get("warning") != result["note"]


def test_the_rest_surface_documents_it() -> None:
    """Result 126's lesson, applied on the way in rather than after the fact: a field a client
    cannot discover is a field that does not exist for them."""
    pytest.importorskip("fastapi")
    from untell.api_server import app

    schema = (
        app.openapi()["paths"]["/sentences"]["post"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )
    assert "warning" in schema.get("properties", {})
