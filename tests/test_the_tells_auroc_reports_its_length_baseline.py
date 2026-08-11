"""A separation figure needs the dumbest baseline printed beside it.

FOUND by asking what `tells_per_100w` is actually normalised for. Dividing by words looks like length
control and is not: the two repetition categories only fire above thresholds a longer text crosses
more easily, so the rate itself climbs with length — MEASURED on RAID+HC3 AI text, 3.68 per 100
words under 150 words against 12.33 above 250.

So the headline AUROC was measured against the dumbest possible competitor, counting words:

    RAID   catalogue 0.9555   word count alone 0.9303   margin +0.025
    HC3    catalogue 0.8696   word count alone 0.6922   margin +0.177

**On RAID the entire fifteen-category catalogue beats a word counter by 0.025.** Its AI halves run
285.9 words against 194.6 human, a 47% asymmetry, and the reported separation is mostly that. On
HC3, whose halves are 190.1 against 184.9, the same catalogue earns +0.177. Same code, opposite
readings — which is why the baseline is printed on every run rather than derived once and quoted.

Truncating both halves to a fixed window was tried first and reports no single number: RAID lands at
0.619 / 0.695 / 0.815 for a 120 / 150 / 180-word window, because a wider window both removes the
asymmetry and hands the repetition tells more text to fire on. The word-count baseline needs no
truncation, discards no pairs, and answers the question directly.
"""

from __future__ import annotations

import logging

import pytest

from eval.tells_auroc import LENGTH_MARGIN_FLOOR, measure, render

HUMAN = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads once the "
    "forecast turns. It stops working somewhere around minus nine, and below that you need "
    "something else entirely. Most mixes add grit so the surface gains a bit of traction too."
)

AI = (
    "It is worth noting that salt plays a crucial role in lowering the freezing point of water. "
    "Additionally, this pivotal property underscores why salt is a cornerstone of winter road "
    "maintenance. Moreover, the comprehensive approach leverages a robust and seamless combination "
    "of grit and salt. Furthermore, this multifaceted strategy delivers a compelling outcome."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_baseline_is_reported() -> None:
    m = measure([(HUMAN, AI)] * 4)
    assert "auroc_length_baseline" in m
    assert "margin_over_length" in m
    assert m["margin_over_length"] == pytest.approx(m["auroc"] - m["auroc_length_baseline"], abs=1e-4)


def test_a_pure_length_difference_is_caught_by_the_baseline() -> None:
    """Guards the guard. A corpus whose halves differ ONLY in length is the case the baseline exists
    to expose: the catalogue separates it, and so does counting words, so the margin collapses and
    the note has to fire."""
    long_human = " ".join([HUMAN] * 3)
    pairs = [(HUMAN, long_human)] * 4
    m = measure(pairs)
    assert m["auroc_length_baseline"] == pytest.approx(1.0), "premise: length alone separates this"
    assert m["margin_over_length"] < LENGTH_MARGIN_FLOOR
    assert "counting words" in render("synthetic", m)


def test_a_real_style_difference_keeps_its_margin() -> None:
    """The other side. Same length on both halves, tells only on one — the catalogue must beat the
    baseline by more than the floor, or the floor is set somewhere useless."""
    n = min(len(HUMAN.split()), len(AI.split()))
    pairs = [(" ".join(HUMAN.split()[:n]), " ".join(AI.split()[:n]))] * 4
    m = measure(pairs)
    assert m["human_words_mean"] == m["ai_words_mean"], "premise: length must be neutralised"
    assert m["auroc_length_baseline"] == pytest.approx(0.5), "premise: length must say nothing"
    assert m["auroc"] > m["auroc_length_baseline"]
    assert m["margin_over_length"] >= LENGTH_MARGIN_FLOOR
    assert "counting words" not in render("synthetic", m)


def test_the_word_means_are_reported_so_the_asymmetry_is_visible() -> None:
    """The margin says a confound exists; these two numbers say which way it points, which is what
    a reader needs to decide whether their own corpus has the same problem."""
    m = measure([(HUMAN, " ".join([HUMAN] * 3))] * 4)
    assert m["ai_words_mean"] > m["human_words_mean"]
    out = render("synthetic", m)
    assert f"{m['ai_words_mean']:.1f}" in out and f"{m['human_words_mean']:.1f}" in out
