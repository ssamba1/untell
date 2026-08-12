"""A falling total can hide a category that rose.

The loop lowers total tells — 169 -> 149 over 16 HC3 documents. That number says nothing about
whether some individual category went UP, and this repo has the scar: 14 replacement pairs whose
output side was itself a catalogued tell, found only by checking the good column of a bad->good
table rather than the total.

MEASURED per category, before and after the loop, three corpora, 16 documents each:

    corpus   total          categories that rose
    HC3      169 -> 149     none
    RAID     377 -> 298     none
    MAGE      36 ->  35     none

Clean today. The point of the test is that nothing was watching: `test_invariants.py` checks the
category sum against the total, `test_every_tell_category_can_fire.py` checks each can fire, and
neither asks whether the pipeline emits one.

Run on short fixtures rather than a corpus so this stays a unit test. The corpus figures above are
the evidence; this is the tripwire.
"""
from __future__ import annotations

import pytest

from untell.scripts.run import untell_text
from untell.scripts.tells import score_tells

# Each carries a different mix, so a transform that emits into one category has somewhere to land.
FIXTURES = {
    "transitions": (
        "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
        "Furthermore, it significantly improves overall efficiency across the evaluated corpus. "
        "Additionally, these findings underscore the importance of a comprehensive approach here. "
        "In conclusion, the transformative impact continues to expand across numerous sectors."
    ),
    # Over 60 words deliberately: `_MIN_WORDS_FOR_REPETITION` gates both repetition categories, so
    # a shorter version of this fires nothing and the check above passes without exercising
    # anything. The paired guard test below is what caught that.
    "repetition": (
        "The system processes the data. The system validates the data. The system stores the data "
        "in the primary store. The system then replicates the data to the secondary store, and "
        "the system confirms that the data arrived intact before it moves on to the next batch. "
        "The system logs each batch as it goes. The system retries any batch that failed to land, "
        "and the system reports the retry count at the end of the run so the operator can see it."
    ),
    "hedges": (
        "It is important to note that results may potentially vary somewhat across conditions. "
        "Arguably, some researchers suggest that the effect could possibly be somewhat smaller. "
        "It is worth noting that this might perhaps indicate a broadly comparable outcome overall, "
        "though it seems that further work would likely be needed to establish that clearly."
    ),
}


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_no_category_comes_out_higher_than_it_went_in(name):
    text = FIXTURES[name]
    result = untell_text(
        text, tier="lite", threshold=0.30, max_iters=2, rewriter="composite", seed=5
    )

    before = score_tells(text).get("by_category") or {}
    after = score_tells(result["final"]).get("by_category") or {}

    grew = {
        category: (before.get(category, 0), count)
        for category, count in after.items()
        if count > before.get(category, 0)
    }
    assert not grew, (
        f"the loop emitted tells it did not receive on the {name!r} fixture: {grew} "
        "(before, after). A falling total does not make this acceptable — the catalogue is what "
        "the output is measured against, so the pipeline writing INTO a category is a defect"
    )


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_the_fixture_actually_carries_tells(name):
    """Guards the guard. A fixture with no tells passes the test above without exercising it."""
    assert (score_tells(FIXTURES[name]).get("by_category") or {}), (
        f"the {name!r} fixture no longer fires any category, so the check above proves nothing"
    )
