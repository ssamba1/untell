"""A comparison arm is a role, and swapping it inverts the finding.

`_triples` builds (subject, verb, object) per predicate, with a fallback to a prepositional object
only when there is NO direct object. "The drug reduced mortality compared with placebo" has one, so
"placebo" was never captured — and swapping the arms left every triple identical.

MEASURED before the fix, with all five gates live and both NLI and the role parser available:

    "The drug reduced mortality by 12% compared with placebo."
 -> "Placebo reduced mortality by 12% compared with the drug."
    contradiction 0.004, entailment 0.991, role_swap False  ->  PASSED every gate

In clinical and academic prose "A compared with B" is the commonest structure whose inversion
changes the result, and that register is what this repo targets.
"""

from __future__ import annotations

import pytest

from untell.scripts import roles as R

pytestmark = pytest.mark.skipif(not R.available(), reason="the role parser is not installed")

SWAPS = [
    ("The drug reduced mortality by 12% compared with placebo.",
     "Placebo reduced mortality by 12% compared with the drug."),
    ("The treatment scored higher than the control.",
     "The control scored higher than the treatment."),
    ("Revenue grew faster than costs.", "Costs grew faster than revenue."),
]

NOT_SWAPS = [
    # Voice change, synonym paraphrase, and a faithful rewording of the comparison itself. Any of
    # these firing would make the gate veto ordinary rewrites.
    ("The committee approved the plan.", "The plan was approved by the committee."),
    ("The drug reduced mortality.", "The medication lowered deaths."),
    ("The drug reduced mortality compared with placebo.",
     "The drug lowered deaths relative to placebo."),
    ("The study ran in April.", "The study ran during April."),
    ("The treatment scored higher than the control.",
     "The treatment scored better than the control."),
]


@pytest.mark.parametrize("src,cand", SWAPS, ids=[s[:28] for s, _ in SWAPS])
def test_a_swapped_comparison_arm_is_caught(src: str, cand: str) -> None:
    assert R.role_swap(src, cand) is True


@pytest.mark.parametrize("src,cand", NOT_SWAPS, ids=[s[:28] for s, _ in NOT_SWAPS])
def test_a_faithful_rewrite_is_not_flagged(src: str, cand: str) -> None:
    """The half that decides whether the gate is shippable. A veto that fires on passive voice or
    on 'compared with' -> 'relative to' would block ordinary work."""
    assert R.role_swap(src, cand) is False


def test_detection_depends_on_the_parse_and_is_not_symmetric() -> None:
    """A known limit, pinned so it is a documented property rather than a surprise.

    spaCy does not parse the two directions of this pair the same way: one yields a `than` triple
    and the other does not, so the swap is caught only when the source is the side that parses with
    the preposition attached. Recorded rather than worked around — a heuristic that forced the
    triple would misfire on genuine rephrasing.
    """
    a = "Aspirin performed better than ibuprofen."
    b = "Ibuprofen performed better than aspirin."
    triples_a, _ = R._analyse(a)
    triples_b, _ = R._analyse(b)
    assert len(triples_a) != len(triples_b), (
        "the parses agree now — if spaCy was upgraded, this limit may be gone and the test should "
        "become an assertion that the swap IS caught"
    )
