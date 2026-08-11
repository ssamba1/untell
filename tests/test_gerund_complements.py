""""involves X-ing" and "needs X-ing" are different sentences, and the table treated them as one.

"involves X-ing" means *includes the activity of* X-ing. "needs X-ing" means *requires being* X-ed.
With an object following, the second reading collapses. FOUND by reading RAID output:

    a fundamental task in computer vision that involves allowing a user to interact
      -> ...that NEEDS ALLOWING a user to interact

MEASURED across 240 HC3 and RAID texts, `involves` is followed by a gerund in 33% of its HC3
occurrences and 72% of its RAID ones — the majority case in academic prose, not an edge.

`means` reads correctly in the same slot, so the fix filters the option list rather than declining
the swap.

`requires` was first judged safe on the strength of "requires calibrating" -> "needs calibrating",
which is correct English. A sweep of 80 rewritten texts produced the counter-example anyway:

    ...as it requires balancing accuracy, speed, and computational efficiency
      -> ...as it NEEDS BALANCING accuracy, speed, and computational efficiency

So the two headwords fail for different reasons and need different rules. `involves` is unsafe
before ANY gerund, object or not — "the procedure needs staring at a fixed point" has no object and
is still wrong. `requires` is unsafe only when the gerund takes one, because that is exactly when
the passive reading becomes unavailable.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import (
    _GERUND_OBJECT_UNSAFE,
    _GERUND_UNSAFE,
    _gerund_takes_an_object,
    _plain_register,
)

DRAWS = 40


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_plain_register(text, intensity=1.0))
    return out


BEFORE_A_GERUND = [
    "Interactive segmentation is a fundamental task that involves allowing a user to interact "
    "with an image.",
    "The procedure involves staring at a fixed point for several minutes without blinking.",
]


@pytest.mark.parametrize("text", BEFORE_A_GERUND, ids=lambda t: t[:30])
def test_no_unsafe_substitute_governs_a_gerund(text: str) -> None:
    for out in _outputs(text):
        for bad in _GERUND_UNSAFE["involves"]:
            assert not re.search(rf"\b{bad}\s+\w+ing\b", out, re.I), out


@pytest.mark.parametrize("text", BEFORE_A_GERUND, ids=lambda t: t[:30])
def test_the_safe_substitute_still_fires(text: str) -> None:
    """Guards the guard. Declining the swap entirely would satisfy the test above and drop a
    transform on the majority of `involves` occurrences in academic prose."""
    changed = _outputs(text) - {text}
    assert changed, "the swap was declined outright rather than filtered"
    assert all("involves" not in c for c in changed)


def test_a_noun_complement_keeps_every_option() -> None:
    """The restriction is about the slot, not the word. Before a noun phrase all three substitutes
    are fine and must stay available, or best-of-N loses its diversity here."""
    text = "The upgrade involves a complete replacement of the sensor array in every unit."
    seen = {
        word
        for out in _outputs(text) - {text}
        for word in ("means", "needs", "takes")
        if f" {word} a complete" in out
    }
    assert len(seen) >= 2, f"only {seen} reachable; the gerund rule is firing on a noun"


def test_a_bare_gerund_still_converts() -> None:
    """The near-miss, and the reason the rule is about the OBJECT rather than the headword.

    "requires calibrating" -> "needs calibrating" keeps the passive reading and is correct English.
    The first version of this rule concluded from that pair that `requires` was safe entirely, and
    a corpus sweep of 80 rewritten texts produced the counter-example anyway:

        ...as it requires balancing accuracy, speed, and computational efficiency
          -> ...as it NEEDS BALANCING accuracy, speed, and computational efficiency

    So both halves have to hold: a gerund with no object still converts, one with an object does not.
    """
    for text in (
        "The equipment requires calibrating before every single session without exception.",
        "The scale in the corner of the laboratory requires calibrating.",
    ):
        changed = _outputs(text) - {text}
        assert any("needs calibrating" in c for c in changed), (text, changed)


def test_a_gerund_with_an_object_is_declined() -> None:
    text = (
        "Real-time segmentation poses big challenges as it requires balancing accuracy, speed "
        "and computational cost."
    )
    for out in _outputs(text):
        assert "needs balancing" not in out, out


@pytest.mark.parametrize(
    ("following", "has_object"),
    [
        (["balancing", "accuracy,", "speed"], True),
        (["allowing", "a", "user"], True),
        (["calibrating", "before", "every"], False),
        (["calibrating."], False),
        (["calibrating"], False),
        (["staring", "at", "a"], False),
        (["testing", "and", "review"], False),
    ],
    ids=lambda x: str(x)[:26],
)
def test_the_object_test_itself(following: list[str], has_object: bool) -> None:
    assert _gerund_takes_an_object(following) is has_object


def test_the_unsafe_maps_name_real_substitutes() -> None:
    """An entry naming a word that is not in the table reads as protection and is not — this check
    caught a phantom `involved` key on the hour it was written."""
    from untell.attacks.word_importance import _SYN

    for mapping in (_GERUND_UNSAFE, _GERUND_OBJECT_UNSAFE):
        for head, unsafe in mapping.items():
            assert head in _SYN, f"{head!r} is guarded but no longer in _SYN"
            listed = {s.lower() for s in _SYN[head]}
            assert unsafe & listed, f"none of {sorted(unsafe)} substitutes {head!r} any more"


def test_the_unconditional_map_leaves_something_usable() -> None:
    """`_GERUND_UNSAFE` fires on every gerund, so a headword whose whole option list is unsafe could
    never convert before one — that entry should be a removal from the table, not a guard.

    `_GERUND_OBJECT_UNSAFE` is deliberately exempt: `requires -> needs` is its only option and IS
    declined outright in the object slot, while still converting in the other one.
    """
    from untell.attacks.word_importance import _SYN

    for head, unsafe in _GERUND_UNSAFE.items():
        listed = {s.lower() for s in _SYN[head]}
        assert listed - unsafe, f"every substitute for {head!r} is unsafe before any gerund"


def test_involves_is_unsafe_even_without_an_object() -> None:
    """The failure that split the one map into two. "involves staring at a fixed point" has no
    object, so an object-based rule let `needs` through — and "the procedure needs staring at a
    fixed point" is still wrong, because "includes the activity of" and "requires being" are
    different claims regardless of what follows."""
    text = "The procedure involves staring at a fixed point for several minutes without blinking."
    for out in _outputs(text):
        assert "needs staring" not in out and "takes staring" not in out, out
