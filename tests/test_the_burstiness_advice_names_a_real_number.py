"""The advice told users human prose sits near 0.70. Seven of eighty human documents reach it.

FOUND by chasing three different "ideal" burstiness values in one codebase: `humanness` named 0.70,
the rewriter's default profile targets 0.45, and an earlier measurement in this log put human prose
near 0.48. Two of those can be right at most.

MEASURED, sentence-length coefficient of variation over 40 human texts per corpus, >=90 words:

    corpus   human mean   human median   AI mean   texts reaching 0.70
    HC3        0.514        0.491         0.278       6 / 40
    RAID       0.350        0.326         0.262       1 / 40

**The score was never wrong.** `_BURSTY_IDEAL` has never appeared in the penalty arithmetic, which
applies below 0.50 and above 1.0 — and 0.50 sits almost exactly on the HC3 human median. The
constant is used in a shape label, where any value inside the unpenalised band behaves identically,
and in the sentence shown to the user. So the defect was one sentence: the tool computed a fair
penalty and then told the reader to aim at a number 91% of human writing does not reach.

**The replacement is two numbers, not one.** The corpora differ by more than either differs from the
old constant — forum answers vary their sentence length far more than paper abstracts — so a single
figure would repeat the same mistake in a new place.
"""

from __future__ import annotations

import logging
import statistics

import pytest

from untell.humanness import _BURSTY_HUMAN_MEDIAN, _dominant_signal
from untell.text_split import split_sentences

ERRATIC = (
    "The system records the data each day and then it continues to do so, quietly and without any "
    "fuss whatsoever, for as long as the operators leave it running in the corner of the room. "
    "It stops. Then it starts. Fine."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_advice_quotes_the_measured_medians() -> None:
    note = _dominant_signal(ERRATIC, "lite") or ""
    assert "burstiness" in note, note[:120]
    assert "0.49" in note and "0.33" in note


def test_the_advice_no_longer_quotes_the_unsupported_figure() -> None:
    """7 of 80 human documents reach 0.70. Naming it as where human prose sits is advice to write
    less like the humans in both reference corpora."""
    assert "0.70" not in (_dominant_signal(ERRATIC, "lite") or "")


def test_it_names_the_register_each_number_belongs_to() -> None:
    """A bare pair of numbers is worse than one number. The reader has to know which applies."""
    note = _dominant_signal(ERRATIC, "lite") or ""
    assert "forum prose" in note and "academic abstracts" in note


def test_the_two_medians_are_far_apart() -> None:
    """The premise for quoting two. If they ever converge, one figure becomes the honest answer and
    this file should be revisited rather than the constants quietly averaged."""
    forum = _BURSTY_HUMAN_MEDIAN["forum prose"]
    academic = _BURSTY_HUMAN_MEDIAN["academic abstracts"]
    assert forum - academic > 0.10, (forum, academic)


def test_the_quoted_medians_match_the_corpus() -> None:
    """The numbers in the advice are measurements, so they are checked against the corpus rather
    than trusted. Tolerant by 0.08, because the sample is 40 texts per corpus and this must not
    fail on sampling noise."""
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    def cv(text: str) -> float | None:
        lens = [len(s.split()) for s in split_sentences(text) if s.strip()]
        if len(lens) < 2:
            return None
        mean = statistics.mean(lens)
        return statistics.pstdev(lens) / mean if mean else None

    for corpus, key in (("hc3", "forum prose"), ("raid", "academic abstracts")):
        pairs = load_pairs(corpus, n=40, min_words=90)
        values = [c for c in (cv(h) for h, _ in pairs) if c]
        if len(values) < 20:
            pytest.skip(f"{corpus} returned too few pairs to check the median")
        assert abs(statistics.median(values) - _BURSTY_HUMAN_MEDIAN[key]) < 0.08, (
            corpus, statistics.median(values), _BURSTY_HUMAN_MEDIAN[key]
        )


def test_the_penalty_cut_is_not_the_advice_number() -> None:
    """The distinction this whole result rests on: the arithmetic uses 0.50 and always did, so no
    score changes here. If a future edit wires `_BURSTY_IDEAL` into the penalty, that IS a scoring
    change and should not arrive quietly."""
    import inspect

    import untell.humanness as humanness

    source = inspect.getsource(humanness._dominant_signal)
    penalty_lines = [ln for ln in source.splitlines() if "penalty =" in ln]
    assert penalty_lines, "the penalty computation moved; this guard no longer covers it"
    assert not any("_BURSTY_IDEAL" in ln for ln in penalty_lines), penalty_lines
