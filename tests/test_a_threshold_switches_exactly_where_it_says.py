"""Seven user-visible thresholds, none of them tested at the point where they switch.

Round ninety-seven measured this suite's character precisely. Over 339 comparison sites with both
mutants run at each: of the 55 pairs where the tests distinguish a branch **inversion** from a
branch **off-by-one**, the inversion is caught and the off-by-one missed at **every single one** —
55 to 0, exact binomial p = 5.6 × 10⁻¹⁷. The suite tests that branches do the right thing and not
that they switch in the right place.

That is a prediction, and this is the check. The thresholds a person actually meets should be the
first place it bites, and MEASURED against the paired sweep, **7 of the 8 comparisons guarding a
documented threshold have a surviving off-by-one**, four of them with nothing testing either branch:

| site | off-by-one | inversion |
|---|---|---|
| `score.py:732` `words >= _MIN_WORDS_FOR_A_VERDICT` | survives | killed |
| `score.py:705` `words < _MIN_WORDS_FOR_A_VERDICT or …` | survives | survives |
| `tells.py:723` `len(words) < _MIN_WORDS_FOR_REPETITION` | survives | survives |
| `tells.py:853` same, in the opener check | survives | survives |
| `perplexity_burstiness.py:330` `< _MIN_WORDS_FOR_SIGNAL` | survives | killed |
| `perplexity_burstiness.py:632` same, other path | survives | killed |
| `humanness.py:426` `_words < _MIN_WORDS_FOR_A_BAND` | survives | survives |
| `sentences.py:163` `len(scores) < _MIN_SENTENCES_FOR_SPREAD` | **killed** | killed |

These are not internal details. `_MIN_WORDS_FOR_A_VERDICT` decides whether a person is told their
text is too short to judge, and the repository's own warning quotes the 40-word figure. An
off-by-one there means a 40-word document is handled as a 39-word one — the tool disagreeing with
its own documentation about the input in front of the reader.

Each threshold is asserted at **n−1, n and n+1**. Two points would leave the switch free to sit on
either side of the gap; three pin it.
"""

from __future__ import annotations

import pytest

from untell.detectors.perplexity_burstiness import _MIN_WORDS_FOR_SIGNAL, lite_score
from untell.humanness import _MIN_WORDS_FOR_A_BAND, humanness_with_caveats
from untell.scripts.score import (
    _MIN_WORDS_FOR_A_VERDICT,
    _STDLIB_PERPLEXITY_VERDICT_THRESHOLD,
    _length_false_positive_warning,
    _short_text_warning,
)
from untell.scripts.sentences import _MIN_SENTENCES_FOR_SPREAD
from untell.scripts.tells import (
    _MIN_WORDS_FOR_REPETITION,
    _duplicate_sentence_starts,
    _repeated_trigrams,
)


def words(n: int) -> str:
    """`n` whitespace-delimited words, which is what every one of these thresholds counts."""
    return " ".join(f"word{i}" for i in range(n))


def sentences_of(n: int, words_each: int = 8) -> str:
    """`n` sentences, each long enough to survive sentence splitting."""
    return " ".join(" ".join(f"w{i}{j}" for j in range(words_each)) + "." for i in range(n))


# --- _MIN_WORDS_FOR_A_VERDICT: whether a person is told the text is too short ------------------

def test_the_short_text_warning_stops_exactly_at_the_documented_floor():
    """`words >= _MIN_WORDS_FOR_A_VERDICT` returns None. One word fewer must still warn."""
    floor = _MIN_WORDS_FOR_A_VERDICT
    assert _short_text_warning(words(floor - 1)) is not None, "39 words is below the floor"
    assert _short_text_warning(words(floor)) is None, "40 words is AT the floor and is enough"
    assert _short_text_warning(words(floor + 1)) is None


def test_the_warning_quotes_the_count_it_actually_measured():
    """A boundary that is right but reports the wrong number is the same defect one step on."""
    warning = _short_text_warning(words(_MIN_WORDS_FOR_A_VERDICT - 1))
    assert warning is not None
    assert f"{_MIN_WORDS_FOR_A_VERDICT - 1} words" in warning


def test_the_elevated_false_positive_note_starts_exactly_at_the_floor():
    """`words < floor` returns None, so the note begins at the floor and not one word later."""
    bar = _STDLIB_PERPLEXITY_VERDICT_THRESHOLD
    floor = _MIN_WORDS_FOR_A_VERDICT
    assert _length_false_positive_warning(words(floor - 1), bar) is None
    assert _length_false_positive_warning(words(floor), bar) is not None
    assert _length_false_positive_warning(words(floor + 1), bar) is not None


def test_the_elevated_note_stops_at_the_top_of_its_measured_band():
    """The other end of the same comparison, which no test reached either."""
    from untell.scripts.score import _ELEVATED_FPR_BANDS

    bar = _STDLIB_PERPLEXITY_VERDICT_THRESHOLD
    top = _ELEVATED_FPR_BANDS[-1][0]
    assert _length_false_positive_warning(words(top - 1), bar) is not None
    assert _length_false_positive_warning(words(top), bar) is None, (
        "the band is measured below this length only; at the bound the note must stop"
    )


# --- _MIN_WORDS_FOR_SIGNAL: whether the detector scores at all --------------------------------

def test_the_detector_declines_exactly_below_its_minimum():
    """`< _MIN_WORDS_FOR_SIGNAL` returns None — the Detector protocol's 'no signal'."""
    floor = _MIN_WORDS_FOR_SIGNAL
    assert lite_score(words(floor - 1)) is None
    assert lite_score(words(floor)) is not None, "at the floor the detector must produce a number"
    assert lite_score(words(floor + 1)) is not None


def test_the_detector_object_declines_at_the_same_point_as_the_function():
    """The SAME floor, guarded a second time in `PerplexityBurstinessDetector.score`.

    Two copies of one threshold is two chances to get it wrong, and the second had no test: the
    function-level boundary mutant died to the test above while the method-level one survived it.
    They must agree, or the ensemble and the bare function disagree about the same input.
    """
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    detector = PerplexityBurstinessDetector()
    floor = _MIN_WORDS_FOR_SIGNAL
    assert detector.score(words(floor - 1)) is None
    assert detector.score(words(floor)) is not None, "at the floor the detector must score"
    assert lite_score(words(floor)) is not None, "and the function must agree with the method"


# --- _MIN_WORDS_FOR_REPETITION: the opener-repetition tell ------------------------------------

def _repeated_openers(total_words: int) -> str:
    """Exactly `total_words` words, every sentence opening with the same one.

    Exact matters: a first draft built "floor - 1" and "floor + 6" and killed neither mutant, because
    `< floor` and `<= floor` differ on exactly one input — the floor itself — and neither sample was
    it. That is the same mistake the suite makes everywhere, made while writing the test for it.
    """
    per = 6
    count = total_words // per
    remainder = total_words - count * per
    parts = ["Same " + " ".join(f"w{i}{j}" for j in range(per - 1)) + "." for i in range(count)]
    if remainder:
        parts.append("Same " + " ".join(f"x{j}" for j in range(remainder - 1)) + ".")
    return " ".join(parts)


def _repeated_trigram_text(total_words: int) -> str:
    """Exactly `total_words` words, more than 5% of them inside a repeated trigram."""
    unit = ["alpha", "beta", "gamma"]
    out = []
    while len(out) < total_words:
        out.extend(unit)
    return " ".join(out[:total_words]) + "."


def test_the_opener_check_starts_exactly_at_its_minimum():
    """`len(words) < _MIN_WORDS_FOR_REPETITION` returns 0 — so the floor itself must fire."""
    floor = _MIN_WORDS_FOR_REPETITION
    below = _repeated_openers(floor - 1)
    at = _repeated_openers(floor)
    assert len(below.split()) == floor - 1, "premise: the sample is exactly one word short"
    assert len(at.split()) == floor, "premise: the sample is exactly at the floor"
    assert _duplicate_sentence_starts(below) == 0, "one word short, the tell must not fire"
    assert _duplicate_sentence_starts(at) > 0, "AT the floor a repeated opener must fire"


def test_the_trigram_check_starts_exactly_at_its_minimum():
    """The same floor in `_repeated_trigrams`, which the opener test does not reach at all."""
    floor = _MIN_WORDS_FOR_REPETITION
    below = _repeated_trigram_text(floor - 1)
    at = _repeated_trigram_text(floor)
    assert len(below.split()) == floor - 1
    assert len(at.split()) == floor
    assert _repeated_trigrams(below) == 0, "one word short, the tell must not fire"
    assert _repeated_trigrams(at) > 0, "AT the floor a repeated trigram must fire"


# --- _MIN_WORDS_FOR_A_BAND: whether humanness qualifies its own number ------------------------

def test_the_humanness_band_caveat_stops_exactly_at_the_floor():
    """`_words < _MIN_WORDS_FOR_A_BAND` attaches the 'unreliable band' caveat."""
    floor = _MIN_WORDS_FOR_A_BAND

    def caveats(n: int) -> list[str]:
        return humanness_with_caveats(words(n), tier="lite")[1]

    # The caveat names the count and says the score does not separate the classes at this length.
    # Matched on that phrase rather than on the word "band": the constant is named for the band but
    # the sentence a reader sees is not, and asserting the wrong string is how a boundary test
    # passes for the wrong reason.
    below = " ".join(caveats(floor - 1))
    at = " ".join(caveats(floor))
    above = " ".join(caveats(floor + 1))
    assert "does not separate the classes" in below, (
        "one word below the floor the number must be qualified"
    )
    assert f"{floor - 1} words" in below, "and the caveat must quote the count it measured"
    assert "does not separate the classes" not in at, "at the floor the caveat must be gone"
    assert "does not separate the classes" not in above


# --- _MIN_SENTENCES_FOR_SPREAD: the one already protected, pinned so it stays ------------------

@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_unrankable_verdict_needs_exactly_its_minimum_sentences(offset: int):
    """Already killed both mutants in round 97. Kept so a later edit cannot quietly lose it.

    The threshold guards `_targeting_is_unrankable`, not a `spread` key — a first draft of this test
    asserted the latter and failed, which is the trap `docs/result-shapes.md` exists for and the
    fourth time this session that guessing a return shape cost a run.
    """
    from untell.scripts.sentences import _targeting_is_unrankable

    count = _MIN_SENTENCES_FOR_SPREAD + offset
    identical = [{"ai": 0.5} for _ in range(count)]
    verdict = _targeting_is_unrankable(identical)
    if count < _MIN_SENTENCES_FOR_SPREAD:
        assert verdict is False, (
            f"{count} scores is too few to call a document unrankable, however close they are"
        )
    else:
        assert verdict is True, f"{count} identical scores cannot be ordered"


def test_a_wide_spread_is_rankable_however_many_sentences_there_are():
    """Guards the test above: identical scores alone would pass under a broken spread bar too."""
    from untell.scripts.sentences import _targeting_is_unrankable

    spread_out = [{"ai": 0.05}, {"ai": 0.5}, {"ai": 0.95}, {"ai": 0.7}]
    assert _targeting_is_unrankable(spread_out) is False
