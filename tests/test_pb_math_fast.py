"""Fast pure-math tests for perplexity_burstiness helpers (no model loads).

Pins the documented contract of _sentences / _burstiness / _common_ratio /
lite_score so the mutation sweeps of this module run against a fast suite.
"""

from __future__ import annotations

import pytest

from untell.detectors import perplexity_burstiness as PB


class TestSentences:
    def test_splits_on_terminators(self) -> None:
        assert PB._sentences("One. Two. Three!") == ["One.", "Two.", "Three!"]

    def test_no_terminators_returns_whole(self) -> None:
        assert PB._sentences("No punctuation here") == ["No punctuation here"]

    def test_empty_returns_empty(self) -> None:
        assert PB._sentences("") == []
        assert PB._sentences("   ") == []

    def test_abbreviation_not_split(self) -> None:
        # Dr. must not become its own sentence
        sents = PB._sentences("Dr. Smith arrived. He sat down.")
        assert len(sents) == 2


class TestBurstiness:
    def test_uniform_is_zero(self) -> None:
        assert PB._burstiness(["one two three", "four five six"]) == 0.0

    def test_varied_is_positive(self) -> None:
        cv = PB._burstiness(["one", "one two three four five"])
        assert cv > 0.0

    def test_known_cv(self) -> None:
        # lengths [1, 3]: mean 2, var 1, cv = 1/2 = 0.5
        assert PB._burstiness(["a", "a b c"]) == pytest.approx(0.5)

    def test_single_sentence_is_zero(self) -> None:
        assert PB._burstiness(["only one sentence here"]) == 0.0

    def test_empty_is_zero(self) -> None:
        assert PB._burstiness([]) == 0.0


class TestCommonRatio:
    def test_all_common_is_one(self) -> None:
        assert PB._common_ratio("the and of to a in is it") == 1.0

    def test_none_common_is_zero(self) -> None:
        assert PB._common_ratio("zyxwvutsrqponmlkjihgfedcba quantum") == 0.0

    def test_empty_is_zero(self) -> None:
        assert PB._common_ratio("") == 0.0

    def test_mixed(self) -> None:
        # 2 common of 4: the, cat, sat, on -> the/on common
        assert PB._common_ratio("the cat sat on") == 0.5

    def test_case_insensitive(self) -> None:
        assert PB._common_ratio("THE AND OF") == 1.0


class TestMinWordsSignal:
    def test_short_text_abstains(self) -> None:
        # "the of and" is 3 words < 5: lite_score returns None (no signal)
        assert PB.lite_score("the of and") is None

    def test_long_text_signals(self) -> None:
        text = "the quick brown fox jumps over the lazy dog and the cat"
        assert PB.lite_score(text) is not None
