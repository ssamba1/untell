"""A prescribed substitution the meaning gate refuses is a permanently wasted draw.

`_SYN` tells the rewriter to make a swap; `hedges.certainty_kept` then vetoes any candidate
containing it, unconditionally — so the draw is discarded before it is ever scored. Five shipped
entries did this:

    profound    -> major           intensifier_added
    importantly -> significantly   intensifier_added
    arguably    -> debatably       modality (the hedge is dropped)
    various     -> different       quantifier (the vague quantity is firmed up)
    various     -> assorted        quantifier

This is the same failure the existing `test_every_substitute_is_not_itself_a_tell` guards against —
a substitute that cannot improve anything — one layer further on: there the swap left the tell in
place, here it makes the candidate unusable.

`arguably` and `various` are left with no substitutes rather than given invented ones. The comment
above `arguably` in the source already says it has no close single-word synonym and that "inventing
one to pad the list is how the other three got in"; an empty list is that conclusion applied.
"""

from __future__ import annotations

import pytest

from untell.attacks.word_importance import _SYN
from untell.scripts.hedges import certainty_kept, polarity_kept
from untell.scripts.numerals import numbers_kept

# Enough surrounding text that the gate sees a document rather than a fragment.
_PRE = "The committee met on Tuesday and reviewed the schedule for the coming quarter. "
_POST = " The report will be published in full before the end of the year."


def _pair(word: str) -> str:
    return f"{_PRE}The effect was {word} across the sites.{_POST}"


ALL_SUBSTITUTIONS = [(h, s) for h, subs in _SYN.items() for s in subs]


def test_there_are_substitutions_to_check() -> None:
    assert len(ALL_SUBSTITUTIONS) > 200, "the map shrank unexpectedly; this test would prove little"


@pytest.mark.parametrize("head,sub", ALL_SUBSTITUTIONS, ids=[f"{h}->{s}" for h, s in ALL_SUBSTITUTIONS])
def test_no_substitution_is_vetoed_by_the_certainty_gate(head: str, sub: str) -> None:
    assert certainty_kept(_pair(head), _pair(sub)), (
        f"{head!r} -> {sub!r} is prescribed by _SYN and refused by certainty_kept, so every "
        f"candidate carrying it is discarded unscored"
    )


@pytest.mark.parametrize("head,sub", ALL_SUBSTITUTIONS, ids=[f"{h}->{s}" for h, s in ALL_SUBSTITUTIONS])
def test_no_substitution_is_vetoed_by_the_polarity_or_number_gates(head: str, sub: str) -> None:
    """The other two unconditional vetoes in `meaning_preserved`, checked for the same reason."""
    a, b = _pair(head), _pair(sub)
    assert polarity_kept(a, b), f"{head!r} -> {sub!r} flips polarity"
    assert numbers_kept(a, b), f"{head!r} -> {sub!r} drops a number"


def test_a_headword_with_no_usable_substitute_is_removed_not_emptied() -> None:
    """An entry with no substitutes is dead weight that reads exactly like a live one.

    `arguably` and `various` each lost every substitute to the gate, so both are gone from the map
    rather than left as empty lists — which is what `test_substitutes_are_single_tokens_or_short_phrases`
    already required, and what caught the first version of this change.
    """
    for head in ("arguably", "various"):
        assert head not in _SYN, (
            f"{head!r} is back — check its substitutes against the gate before re-adding it"
        )
    assert not [k for k, v in _SYN.items() if not v], "an entry was emptied instead of removed"
