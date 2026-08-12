"""The evidential class held past forms of four verbs and not their present forms.

`certainty_kept` fires when a hedge class present in the source is absent from the rewrite, so a
missing class member is invisible in one direction and a false veto in the other. This file
covers both, because both happened here.

MISSED (a real upgrade cleared the gate). The class had `believed`, `thought`, `considered` and
`estimates`/`estimated`, but not `believe`, `think`, `consider` or `estimate` — and the present
tense is how attribution is normally written:

    "We believe the mechanism is oxidative." -> "It is established the mechanism is oxidative."
    "Researchers think the effect is real."  -> "The effect is real."
    "We consider this the likely cause."     -> "This is the cause."
    "We estimate the loss at 40%."           -> "The loss is 40%."

Removing an attribution does not contradict the source, so NLI, roles, quantities and similarity
all pass it. This class is the only gate that can see it. Exactly the hole the file already
records fixing for `allege`/`accuse`.

FALSE VETO (a legitimate rewrite rejected). `suspected` and `purported` were also past-only, so
"We believe the effect is real." -> "We suspect the effect is real." read as a dropped class when
it is a lateral move between two weak hedges — the failure the `hint` note in hedges.py records.

MEASURED cost of widening, on 11 real rewrites the loop produced from HC3 documents: 0 evidential
vetoes with the new members and 0 without. The class only fires on absence, so a wider class can
only add vetoes, and on genuine corpus output it added none.
"""
from __future__ import annotations

import pytest

from untell.scripts.hedges import _CLASSES, certainty_kept

UPGRADES = [
    ("believe", "We believe the mechanism is oxidative.",
     "It is established the mechanism is oxidative."),
    ("think", "Researchers think the effect is real.", "The effect is real."),
    ("consider", "We consider this the likely cause.", "This is the cause."),
    ("estimate", "We estimate the loss at 40%.", "The loss is 40%."),
]


@pytest.mark.parametrize("verb,source,rewrite", UPGRADES, ids=[u[0] for u in UPGRADES])
def test_dropping_a_present_tense_attribution_is_caught(verb, source, rewrite):
    assert not certainty_kept(source, rewrite), (
        f"the rewrite dropped '{verb}' and asserts the claim outright; no other gate sees this"
    )


@pytest.mark.parametrize("verb", ["believe", "think", "consider", "estimate", "suspect", "purport"])
def test_the_class_holds_the_present_form_not_only_the_past(verb):
    """The shape of the bug, stated directly so a future edit cannot reintroduce half a verb."""
    assert verb in _CLASSES["evidential"], (
        f"'{verb}' is missing while its past form is present — the same hole this class already "
        "records fixing for 'allege'"
    )


def test_a_lateral_move_between_weak_hedges_is_not_a_veto():
    """`suspected` was listed and `suspect` was not, so this legitimate rewrite was rejected."""
    assert certainty_kept("We believe the effect is real.", "We suspect the effect is real.")


def test_weakening_a_claim_is_always_allowed():
    """The gate is one-directional by design: adding a hedge is never an upgrade."""
    assert certainty_kept("The effect is real.", "We believe the effect is real.")


def test_an_unrelated_rewrite_is_not_vetoed():
    """Widening a class can only add vetoes, so the quiet case is the one worth pinning."""
    assert certainty_kept(
        "The parser reads each record before handing it to the loader.",
        "Each record is read by the parser and then handed to the loader.",
    )


@pytest.mark.xfail(reason="approximators are in no hedge class; measured and left open", strict=True)
def test_dropping_an_approximator_is_caught():
    """An open gap, pinned as xfail so it is visible rather than forgotten.

    "About 40% recovered." -> "40% recovered." passes every gate: the number survives so
    `missing_numbers` is empty, and `about` belongs to no class so `certainty_kept` is True. An
    approximation became an exact figure, which is a different claim.

    Not fixed here because the obvious fix is worse than the gap: "about" is overwhelmingly used
    in its non-hedge sense ("a paper about X"), and this class fires on the SOURCE containing a
    member, so adding it would veto rewrites of any text that happens to say "about". A targeted
    version — an approximator immediately preceding a number — belongs with the quantity checks in
    numerals.py rather than here.
    """
    assert not certainty_kept("About 40% recovered.", "40% recovered.")
