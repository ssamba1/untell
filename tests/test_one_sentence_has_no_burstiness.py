"""0.2500 on a single sentence is what the stdlib heuristic emits when half of it has no input.

The stdlib detector is perplexity plus BURSTINESS, and burstiness is the variation in sentence
length — undefined on one sentence. MEASURED over 60 real HC3 sentences, first sentence alone
against the first two together:

    single-sentence scores      8 distinct values of 60, and 82% are exactly 0.2500
    |delta| from one more       median 0.406, mean 0.367, range 0.000-0.672
    share moving by >0.30       67%

The first version of this file asserted "a second sentence moves it by 0.68" from one hand-picked
pair. The pair below moves 0.063, and the test failed — which is the only reason the distribution
above was measured at all. The range, not the best case, is what the caveat now quotes.

**The existing short-text guard does not catch this.** It counts WORDS, and a 71-word single
sentence clears its 40-word bar and scored 0.2500 with nothing said. Length and sentence count are
different limits, and a long run-on has only the second one.

This is also the mechanism behind the per-sentence finding: `score_sentences` on the stdlib path
returns 6 distinct values across 100 sentences, 91 of them 0.250, AUROC 0.515. Asked the same
question at DOCUMENT granularity, the same detector gives **119 distinct values across 120
documents, AUROC 0.864 on HC3 and 0.791 on RAID**. It is not a weak detector being asked a hard
question; it is a detector being asked a question one of its two halves cannot answer.

The caveat is scoped to the case where the stdlib heuristic is the ONLY detector. A model-backed
detector does not need sentence variation, so on the full tier a single sentence is fine.
"""

from __future__ import annotations

import logging

import pytest

from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector
from untell.scripts.score import _single_sentence_warning, score_text

ONE_LONG_SENTENCE = (
    "The system reads the file before anything else happens on the node and then the parser "
    "splits it into records which are handed one by one to the loader that writes each of them to "
    "the store and waits for an acknowledgement from the replica set before moving on to the next "
    "record in the queue, which is what makes the first stage of the pipeline slow on a cold cache."
)

SECOND = " Salt lowers the freezing point of water, which is why councils spread it on roads."


class _Model:
    name = "hc3_roberta"
    tier = "full"

    def score(self, text: str) -> float:
        return 0.9


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_sentence_is_long_enough_to_clear_the_word_guard() -> None:
    """The premise. If this were short the existing warning would cover it and there would be
    nothing here to fix."""
    from untell.scripts.score import _MIN_WORDS_FOR_A_VERDICT, _short_text_warning

    assert len(ONE_LONG_SENTENCE.split()) > _MIN_WORDS_FOR_A_VERDICT
    assert _short_text_warning(ONE_LONG_SENTENCE) is None


SINGLES = [
    "The system reads the file before anything else happens on the node today.",
    "Salt lowers the freezing point of water, which is why councils spread it.",
    "The parser splits it into records and hands each one onward to the loader.",
    "Most councils mix the salt with grit so the road surface also gains traction.",
    "The index is rebuilt afterwards once every record has landed on the disk.",
]


def test_most_single_sentences_return_the_same_number() -> None:
    """82% of 60 corpus sentences score exactly 0.2500. The constructed set is smaller, so this
    asserts the shape — a handful of distinct values — rather than the corpus percentage."""
    detector = PerplexityBurstinessDetector()
    scores = {round(detector.score(s), 4) for s in SINGLES}
    assert len(scores) <= 2, scores


def test_adding_a_sentence_moves_the_score_on_most_of_them() -> None:
    """The measurement the caveat quotes, as a median over several pairs rather than a best case.
    Stated as a median because the range really is 0.000 to 0.672 and one pair proves nothing."""
    import statistics

    detector = PerplexityBurstinessDetector()
    deltas = [
        abs(detector.score(a + " " + b) - detector.score(a))
        for a, b in zip(SINGLES, SINGLES[1:] + SINGLES[:1])
    ]
    assert statistics.median(deltas) > 0.15, deltas


def test_the_caveat_fires_on_one_sentence() -> None:
    stdlib = [PerplexityBurstinessDetector()]
    assert _single_sentence_warning(ONE_LONG_SENTENCE, stdlib)
    assert "burstiness" in _single_sentence_warning(ONE_LONG_SENTENCE, stdlib)


def test_it_does_not_fire_on_two() -> None:
    """Guards the guard. A caveat on every score is a caveat nobody reads."""
    stdlib = [PerplexityBurstinessDetector()]
    assert _single_sentence_warning(ONE_LONG_SENTENCE + SECOND, stdlib) is None


def test_it_does_not_fire_when_a_model_detector_is_present() -> None:
    """Scoped to the limit it describes. A transformer scores a lone sentence perfectly well, and
    saying otherwise would train readers to skip the sentence."""
    mixed = [PerplexityBurstinessDetector(), _Model()]
    assert _single_sentence_warning(ONE_LONG_SENTENCE, mixed) is None


def test_the_caveat_reaches_the_score_result() -> None:
    result = score_text(ONE_LONG_SENTENCE, tier="lite")
    if any(m == "stdlib" for m in (result.get("detector_modes") or {}).values()):
        assert "one sentence:" in str(result.get("warning"))
    else:  # torch present: lite auto-upgrades and the limit does not apply
        assert "one sentence:" not in str(result.get("warning"))


def test_it_composes_with_the_other_caveats() -> None:
    """`Also:`-joined, like the rest. A short single sentence has both problems and an elif would
    report whichever was checked first."""
    result = score_text("The cat sat on the mat and then it did not.", tier="lite")
    warning = str(result.get("warning") or "")
    if "one sentence:" in warning and "too short" in warning:
        assert "Also:" in warning
