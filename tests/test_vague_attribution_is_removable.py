"""A tell the catalogue flags and the rewriter cannot remove is a tell that survives every run.

FOUND by counting detections against fixes over 120 corpus texts: `vague_attribution` fired on one
text and `_flatten_vague_attribution` acted on **none**. The phrase was "it is generally accepted" —
covered by the detector's `it is (widely|often|generally) (believed|said|understood|accepted)` and
absent from the flattener's `it is (widely )?believed`. So the loop counted a tell, tried to remove
it, failed, and scored the result as unimproved.

The rest of the detector's vocabulary stays out of the flattener, and that gap is measured rather
than assumed. The detector also flags attributed subjects — reports, surveys, analysts, observers,
critics, sources — and rewriting "Critics argue that X" into "Evidence suggests that X" changes WHO
SAID IT.

**The meaning gates do not catch that.** On five such pairs: similarity 0.905-0.947, `contradicts`
False and `role_swap` False on every one. A wider flattener would ship attribution changes past every
guard this repository has. The impersonal forms have no attributor to lose, which is exactly why they
are the safe ones to add.
"""

from __future__ import annotations

import logging
import re

import pytest

from untell.rewriter.structural import _flatten_vague_attribution
from untell.scripts.tells import score_tells

LOWERCASE_AFTER_STOP = re.compile(r"[.!?]\s+[a-z]")


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


IMPERSONAL = [
    "It is generally accepted that the method scales well across large corpora.",
    "It is often said that the approach works best on the shorter documents.",
    "It is widely understood that costs rise with the size of the corpus.",
    "It is widely believed that the tool helps a great deal in practice.",
    "Studies show that the method works well on every corpus that was tested.",
]

ATTRIBUTED = [
    "Critics argue that the method fails badly on the longest documents here.",
    "Analysts say that the method will not scale to the largest corpora at all.",
    "Observers note that the results have not been replicated anywhere else.",
]


@pytest.mark.parametrize("text", IMPERSONAL, ids=lambda t: t[:24])
def test_an_impersonal_attribution_is_removed(text: str) -> None:
    assert _flatten_vague_attribution(text) != text


@pytest.mark.parametrize("text", ATTRIBUTED, ids=lambda t: t[:24])
def test_an_attributed_claim_is_left_alone(text: str) -> None:
    """Guards the guard, and this one protects a meaning the gates cannot. Replacing the subject
    would pass similarity, contradiction and role-swap — measured — so the only thing standing
    between "Critics argue" and "Evidence suggests" is this transform declining to touch it."""
    assert _flatten_vague_attribution(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "The team ran it twice. Studies show that the method works well. It held.",
        "The team ran it twice. It is generally accepted that the method works. Fine.",
        "It is often said that the approach works best on the shorter documents.",
    ],
    ids=lambda t: t[:24],
)
def test_the_replacement_keeps_the_case_of_what_it_replaced(text: str) -> None:
    """The substitution was a flat lowercase string, so a sentence-initial match produced
    ". evidence suggests". It went unnoticed because this transform never fired on real corpus text
    — 0 changes over 50 documents — and widening the pattern is what made it reachable."""
    out = _flatten_vague_attribution(text)
    assert out != text, "premise: the transform must have fired"
    assert not LOWERCASE_AFTER_STOP.search(out), out
    assert not out[:1].islower(), out


def test_what_the_detector_flags_the_flattener_can_act_on() -> None:
    """The invariant this file exists for, on the phrase that exposed it. A tell that is counted and
    cannot be removed is worse than one that is not counted: the loop spends a draw on it every
    iteration and scores the result as no better."""
    text = "It is generally accepted that the method scales well across the large corpora."
    detected = (score_tells(text, include_matches=True).get("by_category") or {}).get(
        "vague_attribution"
    )
    assert detected, "premise: the detector must flag this phrase"
    assert _flatten_vague_attribution(text) != text, "detected but not removable"
