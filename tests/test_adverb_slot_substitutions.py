"""Two ways a correct substitution table still produces broken English.

Found by reading real rewriter output rather than by scoring it — a tell catalogue and a detector
both read "It improves in the end efficiency" as clean, because nothing in either measures grammar.

1. `overall` has an adjective sense and all three of its substitutes are sentence adverbs, so in the
   adjective slot every one of them breaks:

       the overall cost            -> the all told cost / the in the end cost
       improves overall efficiency -> improves in the end efficiency

   Derived rather than guessed: every _SYN entry with a phrasal substitute was scanned for
   `<determiner> <head> <noun>` across 240 HC3 texts, and `overall` is the only hit with a live
   adjective sense. Its adverbial slots are fine and must stay fine.

2. A substitute that opens with its own determiner cannot follow an article. The single corpus case
   of that shape produced "a significantly longer wait" -> "an a lot longer wait", with
   `agree_article` faithfully re-agreeing "a" to "an" for the vowel it should not have been given.
"""

from __future__ import annotations

import random

import pytest

from untell.attacks.word_importance import _SYN
from untell.rewriter.structural import _ADVERB_SLOT_ONLY, _BARE_ARTICLES, _plain_register

DRAWS = 40


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_plain_register(text, intensity=1.0))
    return out


ADJECTIVE_SLOT = [
    "This adds to the overall cost of the project.",
    "The overall distribution of wealth remained uneven.",
    "It improves overall efficiency and accuracy across the corpus.",
]

ADVERB_SLOT = [
    ("The results improved overall.", "sentence-final"),
    ("The result, overall, was disappointing.", "comma-flanked"),
]


@pytest.mark.parametrize("text", ADJECTIVE_SLOT, ids=lambda t: t[:28])
def test_the_adjective_slot_is_left_alone(text: str) -> None:
    assert _outputs(text) == {text}, "an adverb phrase cannot modify a noun"


@pytest.mark.parametrize(("text", "slot"), ADVERB_SLOT, ids=lambda x: str(x)[:24])
def test_the_adverb_slots_still_substitute(text: str, slot: str) -> None:
    """Guards the guard. Declining everywhere would pass the test above and silently delete a
    working transform — the same "fix" that makes a dead regex look like a clean result."""
    changed = _outputs(text) - {text}
    assert changed, f"{slot} 'overall' no longer substitutes at all"
    assert all("overall" not in c for c in changed)


def test_no_output_stacks_two_determiners() -> None:
    text = "There was a significantly longer wait than expected."
    outs = _outputs(text)
    for out in outs:
        for article in ("a", "an", "the"):
            for second in _BARE_ARTICLES:
                assert f" {article} {second} " not in f" {out} ", out
    assert outs - {text}, "the swap was declined entirely; sharply/greatly are fine in this slot"


def test_the_declined_word_is_not_silently_dropped() -> None:
    """Declining must return the original span, article and all — not the empty string, and not the
    bare word without its article."""
    text = "This adds to the overall cost of the project."
    for out in _outputs(text):
        assert "the overall cost" in out, out


def test_the_adverb_slot_list_matches_the_table() -> None:
    """`_ADVERB_SLOT_ONLY` names headwords the table still has to contain. An entry removed from
    _SYN would leave a guard pointing at nothing, which reads as protection and is not."""
    for word in _ADVERB_SLOT_ONLY:
        assert word in _SYN, f"{word!r} is guarded but no longer in _SYN"
        assert all(" " in s for s in _SYN[word]), (
            f"{word!r} now has a single-word substitute, which may fit the adjective slot — "
            "re-derive the guard rather than keeping it on faith"
        )
