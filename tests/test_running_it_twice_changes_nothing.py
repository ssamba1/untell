"""Users re-run tools. The second pass must not undo the first.

Nothing had checked it. A loop that keeps rewriting already-clean text would drift a document further
from its source every time someone pasted the output back in — and the meaning gate compares each
candidate against the CURRENT input, not the original, so the drift compounds silently.

MEASURED at `tier=lite`, `structural`, `max_iters=2`, `best_of=1`, seed fixed, on 8 HC3 answers.
Every document ran its full two iterations (`stopped: max_iters`), so nothing short-circuited:

    doc  tells0  tells1  tells2  sim(1,2)  changed by 1st  changed by 2nd
     1     23      23      23     1.000        no               no
     2      1       1       1     1.000        no               no
     3      1       0       0     1.000        yes              no
     4      4       0       0     1.000        yes              no
     5      0       0       0     1.000        yes              no
     6     28      28      28     1.000        yes              no
     7      1       0       0     1.000        yes              no
     8     13      13      13     1.000        no               no

**5 of 8 were changed by the first pass, and all 5 came back byte-identical from the second.** The
other three adopted no candidate at all and prove nothing about idempotence — which is why the
denominator is written down rather than the headline 8.

The three unchanged documents are not a defect in this configuration: `lite` + `structural` +
`best_of=1` is the weakest path the tool offers, and a loop that adopts nothing when no candidate
beats the incumbent is behaving correctly. This file makes no claim about the default path.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.quality import similarity
from untell.scripts.run import untell_text
from untell.scripts.tells import score_tells

TEXTS = [
    "Moreover, the framework leverages a robust and comprehensive approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the transformative impact for "
    "every stakeholder involved in the programme this year.",
    "It is worth noting that the system utilizes a comprehensive methodology throughout. "
    "Additionally, the platform empowers users to streamline their daily workflows considerably, "
    "and the intricate design fosters a vibrant ecosystem for everyone.",
]
KWARGS = dict(tier="lite", threshold=0.3, max_iters=2, rewriter="structural", best_of=1, seed=3)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def passes() -> list[tuple[str, str, str]]:
    out = []
    for text in TEXTS:
        first = untell_text(text, **KWARGS).get("final") or text
        second = untell_text(first, **KWARGS).get("final") or first
        out.append((text, first, second))
    return out


def test_the_first_pass_actually_changed_something(passes) -> None:
    """The denominator. A loop that adopts no candidate is trivially idempotent, and three of the
    eight corpus documents behaved exactly that way — so the assertions below mean nothing without
    a first pass that did work."""
    changed = [1 for src, first, _ in passes if first != src]
    assert changed, "no document was rewritten; idempotence is untested here"


def test_the_second_pass_is_a_no_op(passes) -> None:
    for _, first, second in passes:
        assert second == first


def test_the_second_pass_does_not_add_tells(passes) -> None:
    """Weaker than byte-equality and worth asserting separately: a future non-deterministic path
    could legitimately produce different text, and this is the property that would still have to
    hold."""
    for _, first, second in passes:
        assert score_tells(second)["tells"] <= score_tells(first)["tells"]


def test_meaning_does_not_drift_on_the_second_pass(passes) -> None:
    """The compounding risk. Each candidate is judged against the CURRENT input, so a gate that
    admits a small drift admits it again from the new baseline, and the distance from the original
    grows without any single step ever failing."""
    for _, first, second in passes:
        assert similarity(first, second) >= 0.99
