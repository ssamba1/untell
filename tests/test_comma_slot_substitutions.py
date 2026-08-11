""""However," takes a comma. "But" and "though" do not, and the table swapped them in anyway.

FOUND by reading RAID output, in two separate runs:

    However, existing methods for interactive segmentation are limited...
      -> But, existing techniques ...
      -> Though, existing techniques ...

Neither is English. And measured across 240 HC3 and RAID texts, neither is anything at all:

    "However,"   95 occurrences
    "But,"        0
    "Though,"     0

Zero in the human half and zero in the AI half. So the substitution did not merely produce bad
grammar, it produced a form nobody in the reference corpus writes — a fingerprint, manufactured by
the pass whose whole purpose is removing them.

86% of the 117 `however` occurrences carry that comma, so this is the usual slot. Without the comma
the same substitutes are correct — "the method is fast, however it fails" -> "...but it fails" — so
the rule filters on the comma rather than dropping the options.
"""

from __future__ import annotations

import random

import pytest

from untell.attacks.word_importance import _SYN
from untell.rewriter.structural import _COMMA_UNSAFE, _plain_register

DRAWS = 40

WITH_COMMA = (
    "However, existing methods for interactive segmentation are often limited by their reliance "
    "on iterative user input."
)
WITHOUT_COMMA = (
    "The method is fast however it fails on the longest inputs in every trial we ran this year."
)


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_plain_register(text, intensity=1.0))
    return out


@pytest.mark.parametrize("bad", sorted(_COMMA_UNSAFE["however"]))
def test_no_conjunction_is_left_holding_the_comma(bad: str) -> None:
    for out in _outputs(WITH_COMMA):
        assert not out.lower().startswith(f"{bad},"), out


def test_the_sentence_adverb_still_fires() -> None:
    """Guards the guard. Declining the swap would satisfy the test above and leave "However," — one
    of the strongest AI transition tells — untouched on 86% of its occurrences."""
    changed = _outputs(WITH_COMMA) - {WITH_COMMA}
    assert changed, "the swap was declined outright rather than filtered"
    assert any(o.startswith("By contrast,") for o in changed), changed


def test_the_conjunctions_survive_where_they_are_correct() -> None:
    """The restriction is about the comma, not the words. Removing them from the table entirely
    would cost the join case, where they are exactly right."""
    reachable = {
        word
        for out in _outputs(WITHOUT_COMMA) - {WITHOUT_COMMA}
        for word in _COMMA_UNSAFE["however"]
        if f" {word} it fails" in out
    }
    assert reachable, "no conjunction reachable in the slot where it is the correct choice"


def test_the_map_names_real_substitutes() -> None:
    """An entry naming a word the table no longer offers reads as protection and is not — the same
    check that caught a phantom `involved` entry in `_GERUND_UNSAFE` on the hour it was written."""
    for head, unsafe in _COMMA_UNSAFE.items():
        assert head in _SYN, f"{head!r} is guarded but no longer in _SYN"
        listed = {s.lower() for s in _SYN[head]}
        assert unsafe & listed, f"none of {sorted(unsafe)} substitutes {head!r} any more"
        assert listed - unsafe, (
            f"every substitute for {head!r} is comma-unsafe, so the comma slot can never convert — "
            "drop the headword instead of guarding it"
        )
