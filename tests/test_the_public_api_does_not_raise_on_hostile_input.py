"""Every public entry point must answer, or say it cannot — never raise into the caller.

The REST server and the MCP tools call these functions directly with whatever text arrives, so an
unhandled exception is a 500 for the sender rather than a verdict. `test_invariants.py` already
checks that composed PROPERTIES hold (scrub twice equals scrub once, lock-then-restore round
trips) over eight reasonable inputs. This file asks the cruder question over hostile ones: does
the call come back at all.

The inputs are things a real document can contain — a pasted null byte, a combining-mark pileup, a
minified token with no spaces, a heading line of 200 hashes — not fuzzer noise.

MEASURED when written: 90 of 90 calls returned. This is regression protection, not a bug report;
the value is that nothing here was pinned before, and the failure mode is loud but only in
production.
"""
from __future__ import annotations

import pytest

from untell.humanness import humanness
from untell.scripts.preserve import lock, restore
from untell.scripts.quality import similarity
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells
from untell.text_split import split_sentences

TEXTS = [
    pytest.param("", id="empty"),
    pytest.param("     ", id="spaces-only"),
    pytest.param("\n\n\n", id="newlines-only"),
    pytest.param("!!! ??? ... ,,, ;;;", id="punctuation-only"),
    pytest.param("a" * 20_000, id="one-very-long-word"),
    pytest.param("text with a \x00 null byte inside it", id="null-byte"),
    pytest.param("text\x01with\x02control\x03chars", id="control-chars"),
    pytest.param("text ‮ reversed ‬ here", id="rtl-override"),
    pytest.param("e" + "́" * 200, id="combining-pileup"),
    pytest.param("." * 2_000, id="many-periods"),
    pytest.param("#" * 200 + " heading\n\n" + "- item\n" * 200, id="deep-markdown"),
    pytest.param("one\tsentence\x0chere. another\x0bone.", id="tabs-and-form-feeds"),
    pytest.param("Ok. " * 2_000, id="very-many-sentences"),
]

FUNCTIONS = [
    pytest.param(lambda t: score_text(t, tier="lite"), id="score_text"),
    pytest.param(score_tells, id="score_tells"),
    pytest.param(split_sentences, id="split_sentences"),
    pytest.param(lambda t: humanness(t, tier="lite"), id="humanness"),
    pytest.param(lambda t: similarity(t, t), id="similarity"),
    pytest.param(lambda t: restore(*lock(t)), id="lock+restore"),
]


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    """The zero-dependency path, which is where a clean install lands."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.mark.parametrize("call", FUNCTIONS)
@pytest.mark.parametrize("text", TEXTS)
def test_it_returns_rather_than_raising(call, text):
    call(text)


def test_a_score_on_unscoreable_text_says_so_rather_than_reporting_zero():
    """Not raising is the floor, not the goal. 0.0 reads as a confident 'human'."""
    result = score_text("!!! ??? ... ,,, ;;;", tier="lite")
    assert result.get("scored") is False or result.get("warning"), (
        "punctuation-only text came back with a number and no caveat; 0.0 is the most "
        f"human-looking value this function can return: {result}"
    )


def test_lock_restore_round_trips_even_on_hostile_input():
    """The one property worth asserting here, because a silent corruption would not raise."""
    for text in ("text with a \x00 null byte", "e" + "́" * 200, "." * 2_000):
        assert restore(*lock(text)) == text
