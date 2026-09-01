"""A tell count says how often a pattern fired, never how often human writing fires it.

The gap between those turned out to be the whole story. MEASURED on 6,842 pre-2022 ACL abstracts —
human by publication date, so every occurrence is a human one:

    ai_vocab                45.67% of documents
    formulaic_transition    18.43%
    state-of-the-art        25.37%   (one string, a quarter of the corpus)

And matched by length against machine-written abstracts, the catalogue fires on **48.1%** of human
documents against **8.6%** of machine ones — AUROC **0.2697**, further from a coin flip than the lite
score's 0.3538. Every one of the thirteen categories that fired at all fired more on human text.

⚠️ **The register is the point, not a caveat on it.** `state-of-the-art` sits in the vocabulary list
beside "best-in-class", "top-tier" and "turnkey", which are promotional. In NLP it is the standard
term for the best current method. The catalogue is not wrong about marketing copy; it is being
applied to academic prose, where these are the field's own words.

So the rates are reported and the catalogue is left alone — deciding what belongs in it is a
judgement about a register this corpus cannot speak for. What these tests pin is that the reporting
happens, that it is measured rather than asserted, and that it stays quiet when it has nothing to say.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from untell.scripts.tells import (
    _COMMON_IN_HUMAN_WRITING,
    base_rate_note,
    human_base_rates,
    score_tells,
)

REPO = Path(__file__).resolve().parent.parent
RATES = REPO / "eval" / "data" / "tell_base_rates.json"

VOCAB_HEAVY = (
    "We propose a comprehensive and robust approach that leverages state-of-the-art models. "
    "Furthermore, the results are crucial for the field. Moreover, we utilize a novel paradigm."
)
PLAIN = (
    "The salt melts ice on the road. Councils spread it in winter. It stops working below minus "
    "nine degrees, so they switch to other chemicals then."
)


def test_the_base_rates_are_a_committed_measurement_not_an_assertion():
    rates = json.loads(RATES.read_text(encoding="utf-8"))
    assert rates["corpus"]["documents"] > 6000
    assert rates["corpus"]["max_year"] == 2021, "the corpus must predate ChatGPT to be known-human"
    assert rates["by_category"]["ai_vocab"] > 0.4
    assert rates["by_tell"]["ai_vocab:state-of-the-art"] > 0.2


def test_a_document_full_of_the_catalogue_is_told_how_common_that_is():
    result = score_tells(VOCAB_HEAVY)
    assert result["tells"] > 0
    note = result["human_base_rate_note"]
    assert "ai_vocab" in note and "45" in note
    assert "pre-2022 ACL abstracts" in note
    assert "human by publication date" in note


def test_text_that_fires_nothing_common_gets_no_note():
    """A caveat on every document is a banner, and the ordering rule exists because stacking
    caveats buries the actionable one."""
    assert "human_base_rate_note" not in score_tells(PLAIN)


def test_the_note_names_the_most_common_categories_first():
    note = base_rate_note({"ai_vocab": 1, "formulaic_transition": 1, "cliche": 1})
    assert note.index("ai_vocab") < note.index("formulaic_transition"), note


def test_a_rare_category_alone_does_not_trigger_the_note():
    """`negated_contrast` is 3.06% — below the floor, and the floor has room under it."""
    assert base_rate_note({"negated_contrast": 2}) is None
    assert _COMMON_IN_HUMAN_WRITING > 0.031, "the floor must sit above the next category down"


def test_a_missing_or_broken_rates_file_does_not_break_the_count(monkeypatch, tmp_path):
    """A caveat must never break the count it qualifies — the same contract
    `_mostly_locked_warning` keeps."""
    human_base_rates.cache_clear()
    monkeypatch.setattr("untell.scripts.tells._BASE_RATES_PATH", tmp_path / "absent.json")
    try:
        assert human_base_rates() == {}
        assert base_rate_note({"ai_vocab": 3}) is None
        assert score_tells(VOCAB_HEAVY)["tells"] > 0
    finally:
        human_base_rates.cache_clear()


@pytest.mark.parametrize("category", ["ai_vocab", "formulaic_transition"])
def test_the_two_dominant_categories_are_above_the_floor(category):
    """If either fell below it, the note would go quiet on the documents that most need it."""
    assert human_base_rates()["by_category"][category] >= _COMMON_IN_HUMAN_WRITING


def test_state_of_the_art_is_the_single_largest_contributor():
    """One string, a quarter of a corpus of human academic abstracts. It is the field's own term of
    art, sitting in a list beside "best-in-class" and "turnkey"."""
    by_tell = human_base_rates()["by_tell"]
    top = max(by_tell.items(), key=lambda kv: kv[1])
    assert top[0] == "ai_vocab:state-of-the-art", top
    assert top[1] > 4 * by_tell["formulaic_transition:furthermore"]
