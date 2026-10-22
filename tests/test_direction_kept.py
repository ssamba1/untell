"""An up word traded for a down word is an inversion, and it adds no negation.

"the drug reduced relapse" -> "the drug increased relapse" keeps every number, every hedge and every
negation, and scores near 1.0 on similarity. Where NLI is installed the contradiction veto catches
it; on the lite path nothing did, and `meaning_preserved` admitted it as faithful.

`direction_kept` is a TRANSFER check, not a count: it fires only when a word of one direction is
lost AND a word of the other is gained. MEASURED before it was wired in, over the offline corpora
(43 texts, structural/surgical/composite, 3 seeds): 0 vetoes in 240 changed candidates, 120 of them
from a source carrying a direction word. The invariant that makes that hold for the substitution
tables is pinned at the bottom of this file.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import meaning_preserved, meaning_preserved_vetoes
from untell.scripts.hedges import _DOWN_WORDS, _UP_WORDS, direction_kept
from untell.scripts.quality import similarity

SOURCE = (
    "The trial enrolled 240 patients across six sites, and the drug reduced relapse by 31 percent "
    "compared with the placebo group over the twelve-month follow-up period."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (SOURCE, SOURCE.replace("reduced", "increased")),
        ("The build runs faster.", "The build runs slower."),
        ("Costs fell sharply last year.", "Costs rose sharply last year."),
        ("The new cache lowers latency.", "The new cache raises latency."),
        ("Demand is higher in winter.", "Demand is lower in winter."),
    ],
    ids=["reduced->increased", "faster->slower", "fell->rose", "lowers->raises", "higher->lower"],
)
def test_an_inversion_is_caught(before: str, after: str) -> None:
    assert not direction_kept(before, after)
    assert not direction_kept(after, before), "the check must be symmetric"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (SOURCE, SOURCE.replace("reduced", "cut")),
        ("Tooling improves throughput.", "Tooling boosts throughput."),
        ("We optimize the pipeline.", "We improve the pipeline."),
        ("It adds additional checks.", "It adds more checks."),
        ("A cutting-edge tool.", "A leading tool."),
        ("Prices dropped and wages rose.", "Wages rose and prices dropped."),
        ("Prices dropped. Wages rose.", "Prices dropped."),
        (SOURCE, SOURCE),
    ],
    ids=["same-direction", "synonym", "one-sided add", "quantifier", "not 'cut'", "reordered",
         "deleted sentence", "identical"],
)
def test_a_faithful_edit_is_not(before: str, after: str) -> None:
    assert direction_kept(before, after)


def test_the_gate_vetoes_it_without_nli() -> None:
    """The point of the check: the path with no model now refuses the flip, and says which rule."""
    flipped = SOURCE.replace("reduced", "increased")
    assert "direction_kept" in meaning_preserved_vetoes(
        SOURCE, flipped, similarity(SOURCE, flipped), 0.86
    )
    assert not meaning_preserved(SOURCE, flipped, similarity(SOURCE, flipped), 0.86)


def test_the_two_lists_do_not_overlap() -> None:
    """A word in both would make every rewrite that kept it look like a transfer to itself."""
    assert not _UP_WORDS & _DOWN_WORDS, sorted(_UP_WORDS & _DOWN_WORDS)


def test_no_substitution_in_the_rewriters_tables_trades_one_direction_for_the_other() -> None:
    """Why the measured false-veto rate is zero, stated as a property rather than a sample.

    The free rewriters change words through these tables. If one ever mapped an up word onto a
    down word, this check would veto that rewrite every time it fired, and the rewrite would be
    a real inversion besides."""
    from untell.attacks.word_importance import _SYN

    crossing = [
        (word, option)
        for word, options in _SYN.items()
        for option in options
        if not direction_kept(word, option)
    ]
    assert not crossing, f"substitutions that invert direction: {crossing}"
