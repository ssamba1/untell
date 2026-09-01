"""The union/majority/unanimous ordering is the repository's central claim. Prove it, don't sample it.

Everything this project argues about aggregation rests on one relationship: a text flagged under the
unanimous rule is necessarily flagged under majority, and a text flagged under majority is
necessarily flagged under union. The published spread — 44.44% / 4.17% / 0.0% on Pratama's abstracts,
36.6% / 21.2% in a live residency match — is only interpretable if that ordering cannot break. If it
could, "requiring detectors to agree accuses fewer people" would be a claim about three specific
corpora rather than about arithmetic.

The existing tests check chosen cases. These enumerate **every possible flag pattern** for one to
seven detectors — 2^n outcomes each, 254 in total — which is not a sample of the input space, it is
all of it. Round thirty-eight is the reasoning: the strongest check available is one against
arithmetic that cannot be wrong.
"""

from __future__ import annotations

import itertools

import pytest

from untell.scripts.score import agreement

THRESHOLD = 0.5


def _scores(pattern: tuple[int, ...]) -> dict:
    """One detector per bit; 1 flags, 0 does not, at `THRESHOLD`."""
    return {f"d{i}": (0.9 if bit else 0.1) for i, bit in enumerate(pattern)}


ALL_PATTERNS = [p for n in range(1, 8) for p in itertools.product((0, 1), repeat=n)]


@pytest.mark.parametrize("pattern", ALL_PATTERNS, ids=lambda p: "".join(map(str, p)))
def test_the_rules_are_ordered_for_every_possible_outcome(pattern):
    """unanimous implies majority implies any. Exhaustive over 254 outcomes."""
    spread = agreement(_scores(pattern), THRESHOLD)
    assert spread is not None
    if spread["unanimous"]:
        assert spread["majority"], f"unanimous but not majority: {pattern}"
    if spread["majority"]:
        assert spread["any"], f"majority but not union: {pattern}"


@pytest.mark.parametrize("pattern", ALL_PATTERNS, ids=lambda p: "".join(map(str, p)))
def test_the_counts_are_consistent_with_the_verdicts(pattern):
    spread = agreement(_scores(pattern), THRESHOLD)
    flagging, total = spread["detectors_flagging"], spread["detectors_scoring"]
    assert 0 <= flagging <= total == len(pattern)
    assert spread["any"] is (flagging >= 1)
    assert spread["majority"] is (flagging * 2 > total)
    assert spread["unanimous"] is (flagging == total)


@pytest.mark.parametrize("pattern", [p for p in ALL_PATTERNS if len(p) == 1])
def test_one_detector_makes_the_three_rules_the_same_measurement(pattern):
    """The claim behind the `degenerate` warning, proved rather than asserted. Both tools that print
    it say the three rules are 'the same measurement printed three times' when one detector scores;
    if that were ever false the warning would be misdirecting the reader."""
    spread = agreement(_scores(pattern), THRESHOLD)
    assert spread["degenerate"] is True
    assert spread["any"] == spread["majority"] == spread["unanimous"]


@pytest.mark.parametrize("n", range(2, 8))
def test_more_than_one_detector_is_never_degenerate(n):
    spread = agreement(_scores(tuple([1] * n)), THRESHOLD)
    assert spread["degenerate"] is False


def test_the_rules_can_actually_separate():
    """Guards the guard. Every assertion above would hold vacuously if the three rules always agreed,
    so at least one outcome must distinguish them — otherwise this whole file proves nothing about a
    spread that never opens."""
    separating = [
        p for p in ALL_PATTERNS
        if len({agreement(_scores(p), THRESHOLD)[r] for r in ("any", "majority", "unanimous")}) > 1
    ]
    assert separating, "no flag pattern separates the three rules"
    assert len(separating) > 100, f"only {len(separating)} of {len(ALL_PATTERNS)} separate them"


@pytest.mark.parametrize("pattern", ALL_PATTERNS[:60], ids=lambda p: "".join(map(str, p)))
def test_adding_a_flagging_detector_never_makes_a_rule_less_likely(pattern):
    """Monotonicity. An extra detector that flags cannot turn `any` off, and cannot turn `majority`
    off either — a rule that could go backwards under more evidence would make the spread
    uninterpretable."""
    before = agreement(_scores(pattern), THRESHOLD)
    after = agreement(_scores(pattern + (1,)), THRESHOLD)
    assert after["any"] or not before["any"]
    if before["majority"]:
        assert after["majority"], f"majority lost by adding a flagging detector: {pattern}"
