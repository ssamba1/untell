"""A polarity flip is the cheapest meaning inversion, and the NLI gate does not reliably catch it.

MEASURED with every gate live and both models available:

    "The trial enrolled 240 patients and the drug reduced mortality by 12% compared with placebo,
     though the effect may not hold in older adults."
 -> the same sentence with "reduced" changed to "did not reduce"
    contradiction 0.066, entailment 0.929, role_swap False  ->  PASSED every gate

Four fresh hedge+negation pairs were built to check whether this generalises. It does not — all
four stayed blocked (contradiction 0.604-0.998). So this is a narrow hole rather than a general
failure, and a cheap mechanical check closes it.
"""

from __future__ import annotations

import pytest

from untell.scripts.hedges import negation_count, polarity_kept

SRC = ("The trial enrolled 240 patients and the drug reduced mortality by 12% compared with "
       "placebo, though the effect may not hold in older adults.")


def test_the_attack_that_passed_every_other_gate_is_blocked() -> None:
    assert not polarity_kept(SRC, SRC.replace("the drug reduced", "the drug did not reduce"))


def test_removing_a_negation_is_blocked_too() -> None:
    """Symmetric on purpose: "did not reduce" -> "reduced" inverts the claim exactly as badly, and
    certainty_kept covers hedges rather than polarity."""
    negated = SRC.replace("the drug reduced", "the drug did not reduce")
    assert not polarity_kept(negated, SRC)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("It does not work", 1),
        ("It doesn't work", 1),
        ("They are not here", 1),
        ("They aren't here", 1),
        ("No evidence was found", 1),
        ("Not only A but also B", 0),
        ("not only A but also not B", 1),
        ("The study succeeded", 0),
    ],
)
def test_the_marker_count_is_what_it_claims(text: str, expected: int) -> None:
    """`n't` is deliberately not \b-anchored: in "aren't" the apostrophe-t is preceded by a word
    character, so \bn't\b never matches and every contraction reads as having lost its negation.
    That mistake produced a phantom "negations decreased on 4 of 25 outputs" while this check was
    being measured — the same \b failure recorded in Result 44, in the instrument this time."""
    assert negation_count(text) == expected


def test_a_contraction_is_not_a_polarity_change() -> None:
    """The rewriter contracts constantly; if this fired the gate would veto most real output."""
    assert polarity_kept("They do not agree with the plan.", "They don't agree with the plan.")


def test_not_only_becoming_and_is_not_a_polarity_change() -> None:
    """"Not only X but also Y" is a correlative conjunction — the claim is that BOTH hold — and the
    structural rewriter turns it into "X and Y". MEASURED over 30 RAID texts this was the only
    apparent polarity loss, 1 of 30, and it was this."""
    assert polarity_kept("Not only A but also B happened.", "A and B happened.")


def test_a_faithful_paraphrase_passes() -> None:
    assert polarity_kept(SRC, "Across 240 enrolled patients the drug cut mortality by 12% versus "
                              "placebo, although that may not carry over to older adults.")
