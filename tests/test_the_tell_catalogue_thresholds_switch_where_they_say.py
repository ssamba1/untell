"""Three thresholds in `untell/scripts/tells.py` that survived the boundary sweep.

A boundary mutant (`<=` -> `<`, `>=` -> `>`) changes behaviour at exactly ONE input: the value that
equals the constant. A test that feeds 3 and 9 to a bar of 6 passes either way, which is how a
suite of ten thousand tests can carry a 26.2% boundary-mutation score. Every case here sits ON the
constant, with a neighbour on each side to show the switch is where it is claimed and not merely
somewhere.

Verified genuinely unprotected by `python -m eval.boundaries --verify` against the 72 tests that
import this module — not assumed from the register, which over-reported by three.
"""

from __future__ import annotations

import pytest

from untell.scripts import tells
from untell.scripts.preserve import _collect_spans
from untell.scripts.tells import (
    _COMMON_IN_HUMAN_WRITING,
    _LANG_MIN_WORDS,
    _OTHER_FUNCTION_WORD_FLOOR,
    CLOSER_REMAINDER_WORDS,
    base_rate_note,
    is_pure_scaffolding,
    looks_non_english,
)

# --- CLOSER_REMAINDER_WORDS: `len(remainder.split()) <= CLOSER_REMAINDER_WORDS` ---

# Purely alphabetic. `word0` reads as an IDENTIFIER to `preserve._collect_spans`, which locks it,
# and a sentence with a locked span returns False before the word count is ever reached — the
# fixture would then pass for the wrong reason on both sides of the bar.
_FILLER = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")


def _closer_with_remainder(n: int) -> str:
    """A sign-off whose text OUTSIDE the matched closer is exactly ``n`` words.

    `is_pure_scaffolding` strips the matched span and counts what is left, so the padding is what
    the rule actually measures.
    """
    sentence = f"I hope this helps {' '.join(_FILLER[:n])}".strip()
    assert not _collect_spans(sentence), (
        "the preserve layer locked part of the fixture, so this would short-circuit before the "
        "word count and pass whichever way the comparison points")
    return sentence


def test_a_closer_with_exactly_the_remainder_limit_is_still_scaffolding():
    """The equality case, and the only input where `<=` and `<` disagree.

    At the limit the sentence IS pure scaffolding. Under `<`, this sign-off survives into the
    output as though it were content.
    """
    sentence = _closer_with_remainder(CLOSER_REMAINDER_WORDS)
    assert len(sentence.split()) - 4 == CLOSER_REMAINDER_WORDS, "the fixture must sit ON the bar"
    assert is_pure_scaffolding(sentence) is True


def test_one_word_under_the_limit_is_scaffolding_and_one_over_is_not():
    """The neighbours. Without these the equality case alone cannot show the switch is here."""
    assert is_pure_scaffolding(_closer_with_remainder(CLOSER_REMAINDER_WORDS - 1)) is True
    assert is_pure_scaffolding(_closer_with_remainder(CLOSER_REMAINDER_WORDS + 1)) is False


# --- _OTHER_FUNCTION_WORD_FLOOR: `other >= _OTHER_FUNCTION_WORD_FLOOR and other > english` ---

def _text_with_shares(n_other: int, n_english: int, total: int) -> str:
    """``total`` words of which ``n_other`` are non-English function words and ``n_english`` English.

    The filler is nonsense in neither list, so the two shares are exactly as requested.
    """
    other = ["der", "und", "mit", "von", "den", "das", "des", "dem", "ein", "auf"][:n_other]
    english = ["the", "and", "of", "to", "in", "is", "it", "for"][:n_english]
    filler = [_FILLER[i % len(_FILLER)] + "x" * (i // len(_FILLER) + 1)
              for i in range(total - n_other - n_english)]
    words = other + english + filler
    assert len(words) == total
    return " ".join(words)


def test_a_text_exactly_on_the_other_function_word_floor_reads_as_non_english():
    """25 words with 3 non-English function words is a share of exactly 0.12, the floor.

    Under `>` this text reads as English, and `language_supported` then reports a tell count for a
    catalogue that cannot read it — the failure mode the floor exists to prevent.
    """
    text = _text_with_shares(n_other=3, n_english=1, total=25)
    assert len(text.split()) >= _LANG_MIN_WORDS
    assert 3 / 25 == pytest.approx(_OTHER_FUNCTION_WORD_FLOOR), "the fixture must sit ON the floor"
    assert looks_non_english(text) is True


def test_just_under_the_floor_reads_as_english_and_just_over_does_not():
    """Neighbours in the same 25-word frame: 2/25 = 0.08 under, 4/25 = 0.16 over."""
    assert looks_non_english(_text_with_shares(n_other=2, n_english=1, total=25)) is False
    assert looks_non_english(_text_with_shares(n_other=4, n_english=1, total=25)) is True


# --- _COMMON_IN_HUMAN_WRITING: `rates.get(name, 0) >= _COMMON_IN_HUMAN_WRITING` ---

def _rates(monkeypatch, **by_category):
    monkeypatch.setattr(
        tells, "human_base_rates",
        lambda: {"by_category": dict(by_category), "corpus": {"name": "test", "n": 100}})


def test_a_category_exactly_at_the_human_base_rate_bar_is_named(monkeypatch):
    """A tell firing in exactly 5% of human documents is reported as common.

    Under `>` the note goes silent at the bar, and the caller reads "1 AI tell" with no indication
    that human writing carries it too — which is the whole reason this note exists.
    """
    _rates(monkeypatch, hedging=_COMMON_IN_HUMAN_WRITING)
    note = base_rate_note({"hedging": 2})
    assert note is not None and "hedging" in note


def test_just_under_the_bar_is_silent_and_just_over_is_named(monkeypatch):
    """The neighbours, so the equality case cannot pass by accident of a shifted bar."""
    _rates(monkeypatch, hedging=_COMMON_IN_HUMAN_WRITING - 0.01)
    assert base_rate_note({"hedging": 2}) is None
    _rates(monkeypatch, hedging=_COMMON_IN_HUMAN_WRITING + 0.01)
    assert base_rate_note({"hedging": 2}) is not None
