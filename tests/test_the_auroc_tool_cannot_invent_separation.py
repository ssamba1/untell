"""The tool that publishes the catalogue's AUROC numbers, asked to prove it can be wrong.

Four times in one session a probe produced a false finding through its own flaw: a harness that
swallowed a traceback, a dead-function scan that wrote its subject into its own haystack, a marker
scanner that matched itself, a constant sweep that ignored module scope. Each was a throwaway script.
`eval/tells_auroc.py` is not throwaway — its output is quoted throughout the catalogue as the
evidence that a tell separates the classes — and nothing asked it the same question.

Three known-answers, none of which needs a corpus download:

    identical halves   AUROC must be exactly 0.5      — no separation exists to find
    swapped labels     AUROC must invert              — the direction must come from the data
    real difference    AUROC must exceed chance       — it must still find what is there

MEASURED on 30 real HC3 pairs while writing this: 0.8906 normally, 0.5000 on identical halves,
0.1094 swapped — inverting to four decimals — and `precision_table` claimed a direction for 0 of 8
categories when both halves were the same text.

The point is the middle row. A tool that reports separation on identical inputs is not measuring the
corpus, and every number it has published would be an artefact.
"""

from __future__ import annotations

import logging

import pytest

from eval.tells_auroc import auroc, measure, precision_table

# Tell-dense on one side, plain on the other. Deliberately synthetic: this file must run without a
# dataset download, and the claim is about the TOOL's behaviour, not about any corpus.
AI_LIKE = [
    "Moreover, the framework leverages a robust and comprehensive approach to delivery. "
    "Furthermore, it is important to note that this underscores the transformative impact.",
    "In conclusion, organizations must harness these pivotal solutions. Additionally, the seamless "
    "integration fosters a vibrant and multifaceted ecosystem for every stakeholder involved.",
    "It is crucial to underscore the intricate interplay at work here. Moreover, the meticulous "
    "approach showcases a groundbreaking paradigm that continues to resonate across the landscape.",
    "Furthermore, the holistic methodology empowers teams to streamline operations. Notably, this "
    "actionable framework delivers unprecedented value across a plethora of diverse verticals.",
]
HUMAN_LIKE = [
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees. Below that you need something else.",
    "The cat sat on the mat and then went outside to look at the birds in the garden. "
    "She stayed out there most of the afternoon, which is unusual for her in this weather.",
    "I tried the recipe twice. First time the dough was too wet, second time I cut the milk by a "
    "third and it came out fine. The oven runs hot so I dropped it twenty degrees as well.",
    "We drove up on Friday and the traffic was awful past the junction. Took nearly four hours "
    "for what should be two. Next time we will leave before lunch and see if that helps.",
]

PAIRS = list(zip(HUMAN_LIKE, AI_LIKE))


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_probe_finds_a_difference_that_is_there() -> None:
    """Premise. If the synthetic halves stopped differing, the two checks below would pass for the
    wrong reason — the tool would look honest because it had nothing to find."""
    assert measure(PAIRS)["auroc"] > 0.5


def test_identical_halves_report_chance() -> None:
    """The one that matters. A tool reporting separation on identical inputs is not measuring the
    corpus, and every number it has published would be an artefact of its own plumbing."""
    assert measure([(ai, ai) for ai in AI_LIKE])["auroc"] == pytest.approx(0.5, abs=1e-9)


def test_swapping_the_labels_inverts_the_answer() -> None:
    """The direction has to come from the data rather than from which argument is which."""
    forward = measure(PAIRS)["auroc"]
    backward = measure([(ai, human) for human, ai in PAIRS])["auroc"]
    assert forward + backward == pytest.approx(1.0, abs=1e-9)


def test_no_category_claims_a_direction_on_identical_halves() -> None:
    """`precision_table` publishes per-category precision, and a category firing equally on both
    sides must not read as evidence for either."""
    rows = precision_table([(ai, ai) for ai in AI_LIKE])
    decisive = [
        r for r in rows
        if isinstance(r.get("precision"), (int, float))
        and (r["precision"] > 0.9 or r["precision"] < 0.1)
        and r.get("n", 0) >= 4
    ]
    assert not decisive, decisive


def test_the_primitive_is_sound_on_its_own() -> None:
    """Underneath the plumbing, so a failure above says which layer broke."""
    assert auroc([1.0, 2.0, 3.0], [0.0, 0.5, 0.9]) == pytest.approx(1.0)
    assert auroc([0.0, 0.5, 0.9], [1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert auroc([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.5)
