""""in combination WITH" is a fixed frame; "a combination OF" is not.

FOUND by reading loop output: "used in combination with other methods" became "used in **pairing**
with other methods", and `mix` and `blend` break it the same way — "in mix with", "in blend with".

Bound to `with` only. "a combination of X" takes every substitute cleanly, and that is **46 of the
47** occurrences across 240 HC3 and RAID texts — binding the word outright would cost the common
case to fix the rare one.

This is the same mechanism as `approach to`, `reliance on` and `capacity for` already in
`_PREPOSITION_BOUND`: a noun whose meaning is carried partly by the preposition after it, so
swapping the noun alone strands the preposition on a synonym that does not take it.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import _PREPOSITION_BOUND, _plain_register

DRAWS = 40
BROKEN_FRAMES = (" mix with", " blend with", " pairing with")


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_plain_register(text, intensity=1.0))
    return out


@pytest.mark.parametrize(
    "text",
    [
        "Salt works best when used in combination with other methods here.",
        "The tool runs in combination with the existing pipeline every night.",
    ],
    ids=lambda t: t[:24],
)
def test_the_with_frame_is_never_broken(text: str) -> None:
    for out in _outputs(text):
        for frame in BROKEN_FRAMES:
            assert frame not in out, out


@pytest.mark.parametrize(
    "text",
    [
        "The result is a combination of several factors across the whole study.",
        "They tried a combination of approaches before settling on the last one.",
    ],
    ids=lambda t: t[:24],
)
def test_the_of_frame_still_substitutes(text: str) -> None:
    """Guards the guard, and it is the reason for the binding rather than a removal. 46 of 47 corpus
    occurrences take this frame, and every substitute fits it."""
    changed = _outputs(text) - {text}
    assert changed, "the swap was declined outright rather than bound to the preposition"
    assert any("combination" not in c for c in changed), changed


def test_the_entry_is_bound_to_with_only() -> None:
    """An entry listing `of` as well would decline the common case, and every test above would
    still pass — the with-frame tests trivially, and the of-frame ones only assert that SOMETHING
    changed, which the sentence's other words can supply."""
    assert _PREPOSITION_BOUND["combination"] == frozenset({"with"})


def test_the_word_itself_is_replaced_in_the_free_frame() -> None:
    """Sharper than "something changed": the headword must actually be the thing that moved, or the
    of-frame test above is satisfied by an unrelated substitution elsewhere in the sentence."""
    text = "The result is a combination of several factors across the whole study."
    assert any(
        "combination" not in out and out != text for out in _outputs(text)
    ), "the headword itself was never substituted in the unbound frame"
