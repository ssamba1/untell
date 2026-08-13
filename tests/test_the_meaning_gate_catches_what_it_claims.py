"""The gate that decides whether a rewrite ships. Twelve deliberate meaning breaks, one per claim.

`meaning_preserved` is a conjunction of eight checks — numerals, certainty, polarity, deletion,
similarity, contradiction, bidirectional entailment, predicate-argument roles — and nothing asked it
whether each one detects the defect it exists for. A gate that never fires is the dead-regex class:
it passes every document forever and reads as evidence of health.

MEASURED, one candidate per break against a 26-word clinical sentence, NLI and spaCy both live:

    vetoed      numeral changed, numeral dropped, percentage changed, polarity flipped,
                negation added, clause deleted, contradiction, count changed          8 of 12
    ADMITTED    certainty raised, certainty hedged, subject swapped, unit changed     4 of 12
    faithful    register change, reordered, de-nominalised, identical                 0 of 4 rejected

The four admitted are recorded rather than fixed, because the same discipline the gate's own
docstrings apply says so — and the measurement that decides it is here rather than assumed:

**Over 80 corpus documents (40 HC3 + 40 RAID) the shipped free rewriters changed the booster count
by 0 and the hedge count by 0.** Not "rarely" — exactly zero, both directions, both corpora. Their
transforms are substitutions, merges and splits, none of which introduces "certainly" or "may have".
So a booster check would be unfalsifiable on the path that can be verified here, which is the
reasoning `certainty_kept` already records for its two known false vetoes.

Two of the four are worth naming precisely, because they are not the same kind of gap:

* `certainty_kept` is `not dropped_hedges(...)` — one-directional by construction. It detects a
  hedge REMOVED, and a hedge or booster ADDED is outside what it measures. The module's stated
  danger is "ships a strengthened claim", and a dropped hedge is one way to strengthen; adding a
  booster is another.
* `role_swap` caught the drug/placebo swap in a 7-word sentence and missed it in the 26-word one
  (entailment 0.984, contradiction 0.010, so nothing else objected either). The check is not
  absent; it degrades with sentence complexity.

The eight vetoes are asserted hard. The four gaps are `xfail(strict=False)`, so fixing one shows up
as an XPASS rather than as a failure — the boundary is recorded, and moving it is visible.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import available, meaning_preserved
from untell.scripts.quality import similarity

SOURCE = (
    "The trial enrolled 240 patients across six sites, and the drug reduced relapse by 31 percent "
    "compared with the placebo group over the twelve-month follow-up period."
)
SIM_BAR = 0.86

CAUGHT = {
    "numeral changed": SOURCE.replace("240", "420"),
    "numeral dropped": SOURCE.replace("240 patients", "patients"),
    "percentage changed": SOURCE.replace("31 percent", "13 percent"),
    "polarity flipped": SOURCE.replace("reduced", "increased"),
    "negation added": SOURCE.replace("the drug reduced", "the drug did not reduce"),
    "clause deleted": "The trial enrolled 240 patients across six sites.",
    "contradiction": SOURCE.replace(
        "reduced relapse by 31 percent", "had no measurable effect on relapse"
    ),
    "count changed": SOURCE.replace("six sites", "sixteen sites"),
}
GAPS = {
    "certainty raised": SOURCE.replace(
        "reduced relapse by 31 percent", "certainly reduced relapse by exactly 31 percent"
    ),
    "certainty hedged": SOURCE.replace("the drug reduced", "the drug may have reduced"),
    "subject swapped": SOURCE.replace(
        "the drug reduced relapse by 31 percent compared with the placebo group",
        "the placebo reduced relapse by 31 percent compared with the drug group",
    ),
    "unit changed": SOURCE.replace("twelve-month", "twelve-week"),
}
FAITHFUL = {
    "register change": (
        "The trial signed up 240 patients at six sites, and the drug cut relapse by 31 percent "
        "against placebo over the twelve months that followed."
    ),
    "reordered": (
        "Across six sites the trial enrolled 240 patients; over the twelve-month follow-up the "
        "drug reduced relapse by 31 percent compared with placebo."
    ),
    "de-nominalised": (
        "The trial enrolled 240 patients across six sites. The drug reduced relapse by 31 percent "
        "compared with the placebo group over twelve months."
    ),
    "identical": SOURCE,
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _admits(candidate: str) -> bool:
    return meaning_preserved(SOURCE, candidate, similarity(SOURCE, candidate), SIM_BAR)


@pytest.mark.parametrize("name", sorted(CAUGHT))
def test_a_meaning_break_is_vetoed(name: str) -> None:
    assert not _admits(CAUGHT[name]), name


@pytest.mark.parametrize("name", sorted(FAITHFUL))
def test_a_faithful_rewrite_is_admitted(name: str) -> None:
    """Guards the guard. A gate that vetoed everything would satisfy every assertion above while
    making the loop unable to adopt anything — which is the failure mode the similarity-only gate
    had, rejecting 6 of 6 faithful formal-to-casual rewrites."""
    assert _admits(FAITHFUL[name]), name


@pytest.mark.parametrize("name", sorted(GAPS))
@pytest.mark.xfail(strict=False, reason="measured gap, see module docstring: 0 of 80 corpus "
                                        "documents produce these shapes on the free path")
def test_a_known_gap(name: str) -> None:
    assert not _admits(GAPS[name]), name


def test_the_free_rewriters_do_not_produce_the_gap_shapes() -> None:
    """The measurement the four xfails rest on, in miniature. If a rewriter ever starts adding a
    booster or a hedge, this fails here rather than in a user's document — which is the whole reason
    to record an unreachable gap instead of deleting it from the list."""
    import re

    from untell.scripts.run import untell_text

    boosters = re.compile(r"\b(?:certainly|definitely|clearly|obviously|exactly|precisely)\b", re.I)
    hedges = re.compile(r"\b(?:may|might|could|possibly|perhaps|arguably|seems?)\b", re.I)
    doc = (
        "Moreover, it is important to note that the trial enrolled 240 patients across six sites. "
        "Furthermore, the drug reduced relapse by 31 percent compared with the placebo group. "
        "In today's fast-paced world, this underscores the value of a well-powered study."
    )
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert len(boosters.findall(final)) <= len(boosters.findall(doc)), final[:200]
    assert len(hedges.findall(final)) <= len(hedges.findall(doc)), final[:200]


def test_the_gate_is_actually_running_its_model_checks() -> None:
    """`meaning_preserved` falls back to a bare similarity bar when NLI is unavailable, and in that
    mode most of this file measures something else entirely. Recorded so a green run cannot be
    mistaken for a green run of the full gate."""
    if not available():
        pytest.skip("NLI stack unavailable — the eight vetoes above are the mechanical ones only")
    assert not _admits(CAUGHT["contradiction"])
