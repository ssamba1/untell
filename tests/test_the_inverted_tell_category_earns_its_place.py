"""`repeated_sentence_openers` fires more on human text than AI text on HC3, and must stay.

Counted over 60 paired texts per corpus:

    corpus    human   ai    ratio
    HC3          40    28    0.70   <- inverted
    MAGE         57    89    1.56
    RAID         22   248   11.27

On HC3 the category supplies 37% of all human tells while firing LESS on the machine side, and
HC3 is the corpus most of this repository's numbers are taken on. Every instinct says drop it.

Checked instead of assumed — AUROC of tells-per-100-words with the category and without:

    corpus    with    without   delta
    HC3       0.898    0.904    +0.007
    MAGE      0.800    0.764    -0.036
    RAID      0.934    0.881    -0.053

Dropping it buys 0.007 on one corpus and costs five to seven times that on the other two.

This file exists because the tempting fix is a regression, and the evidence FOR it is one command
away while the evidence against it needs three corpora. The repo has the matching scar already:
a tells metric that pointed the wrong way on real text because the aggregate was checked and the
components were not. Checking a component is how this was found; acting on one component alone is
what these tests prevent.
"""
from __future__ import annotations

import pytest

from untell.scripts.tells import score_tells

CATEGORY = "repeated_sentence_openers"

# Openers deliberately repeated, the way HC3's forum answers do it. Long enough to clear
# `_MIN_WORDS_FOR_REPETITION` (60) and `len(starts) >= 4` — a shorter fixture returns 0 from the
# guard and would have tested nothing while looking like it tested the category.
HUMAN_LIKE = (
    "I tried the whole thing twice on the office machine and it still did not work properly. "
    "I asked a colleague about the same problem later that afternoon and got nowhere with it. "
    "I ended up rewriting the entire function from scratch over the weekend, which took hours. "
    "I would not go about it that way again if anyone gave me the choice a second time. "
    "I still think the original approach was closer to right than the one that replaced it."
)


def test_the_category_still_exists_and_fires():
    """A category quietly removed would make every number above unfalsifiable."""
    counts = score_tells(HUMAN_LIKE).get("by_category") or {}
    assert CATEGORY in counts, (
        f"{CATEGORY} no longer fires on four sentences opening with the same word — either the "
        "detector broke or the category was dropped, and the docstring records why it must not be"
    )
    assert counts[CATEGORY] > 0


def test_it_contributes_to_the_total():
    """It is summed into the naturalness number the loop uses as a tie-break, not reported aside."""
    result = score_tells(HUMAN_LIKE)
    counts = result.get("by_category") or {}
    assert result["tells"] == sum(counts.values())
    assert counts.get(CATEGORY, 0) > 0


def test_it_is_weighted_as_moderate_not_strong():
    """The weighting is where its uneven behaviour across corpora is already acknowledged."""
    from untell.scripts.tells import _EVIDENCE

    assert _EVIDENCE.get(CATEGORY) == "moderate", (
        "this category is inverted on HC3 and 11x on RAID; promoting it to 'strong' would weight "
        "the corpus disagreement up rather than down"
    )


def test_varied_openers_do_not_fire_it():
    """The other side: it must not be a constant, or the counts above measure nothing."""
    varied = (
        "The parser reads each record in turn before handing it onward to the loader process. "
        "Salt lowers the freezing point of water, which is the reason councils spread it about. "
        "Grit mixed into that salt gives the road surface some traction on a bad winter morning. "
        "Rebuilding the index happens later, once every record has landed safely on the disk. "
        "Nothing else in the pipeline waits for that step to finish before carrying on with work."
    )
    assert (score_tells(varied).get("by_category") or {}).get(CATEGORY, 0) == 0


@pytest.mark.parametrize("text", [HUMAN_LIKE, ""])
def test_it_never_raises_on_edge_input(text):
    score_tells(text)
