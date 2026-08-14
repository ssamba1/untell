"""Killing tests for perplexity_burstiness.py mutation survivors (2026-08-14 sweep).

  line 126  boundary: > -> >=      _burstiness zero-word sentence exclusion.
  line 273  constant: 2 -> 3       two-nonempty-sentence path split.
  line 525  boundary: < -> <=      abstain boundary at exactly _MIN_WORDS_FOR_SIGNAL
                                   (stdlib twin at 254 killed by the same test).

Killed here. 252 (whitespace guard `or` -> `and`) is unkillable: the MIN-words
guard that follows catches the same inputs. The torch-path survivors (350, 357,
383, 386, 405, 409, 442, 451) and constants (202, 211) are model-dependent or
tuning constants — annotated in survivors.md.
"""

from __future__ import annotations

from untell.detectors import perplexity_burstiness as PB


class TestBurstinessZeroWordExclusion:
    """Survivor p_b.py:126 — `n > 0` mutated to `n >= 0`.

    A sentence with zero words (punctuation only) is excluded from the CV. The
    mutation keeps it, changing the coefficient."""

    def test_zero_word_sentence_excluded(self) -> None:
        assert PB._burstiness(["one two", "!!!", "three four five"]) == 0.2

    def test_punctuation_only_ignored(self) -> None:
        # "!!!" alone is not a sentence for CV purposes
        assert PB._burstiness(["!!!", "a b", "c d"]) == 0.0


class TestTwoSentencePath:
    """Survivor p_b.py:273 — `len(nonempty) < 2` mutated to `< 3`.

    With exactly two non-empty sentences the burstiness path runs (the two lengths
    differ, so the score reflects it). The mutation forces the single-sentence
    shortcut, collapsing the score to the repetition-only value."""

    def test_two_sentences_use_burstiness(self) -> None:
        two = "one two three four five. six seven eight nine ten eleven twelve."
        one = "one two three four five six seven eight nine ten eleven twelve."
        assert PB.lite_score(two) != PB.lite_score(one)


class TestAbstainBoundary:
    """Survivor p_b.py:525 — `len(_WORD.findall(text)) < _MIN_WORDS_FOR_SIGNAL`
    mutated to `<=`.

    A text of EXACTLY _MIN_WORDS_FOR_SIGNAL words scores (5 is not < 5). The
    mutation abstains at exactly 5."""

    def test_exactly_min_words_scores(self) -> None:
        assert PB.lite_score("the quick brown fox jumps") is not None

    def test_below_min_abstains(self) -> None:
        assert PB.lite_score("the quick brown fox") is None
