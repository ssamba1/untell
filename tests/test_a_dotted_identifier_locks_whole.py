"""A version number locked as far as its second dot and left the rest rewritable.

`lock()` masks spans a rewrite must not touch, and the loop rejects any candidate whose sentinels
differ. A token only PARTLY locked is the worst of both: the sentinel survives, so every guard
reports success, while the unmasked tail is free text the rewriter may edit.

MEASURED before the `dotted` pattern existed:

    "Requires numpy 1.26.4 or newer."       ->  "Requires numpy ⟦HZ0000⟧.4 or newer."
    "The host was 192.168.1.24 yesterday."  ->  "The host was ⟦HZ0000⟧.⟦HZ0001⟧ yesterday."

so 1.26.4 could become 1.26.7 with every lock intact. `v2.10.3` masked whole only because the
leading `v` makes it an identifier — protection depended on notation rather than on meaning.

The rule needs three or more components, so ordinary decimals stay rewritable: `preserve.py`
deliberately leaves small bare numbers unlocked, and swallowing "3.5" here would change that.
"""
from __future__ import annotations

import pytest

from untell.scripts.preserve import lock, restore

WHOLE = [
    ("bare semver", "Requires numpy 1.26.4 or newer.", "1.26.4"),
    ("ipv4", "The host was 192.168.1.24 yesterday.", "192.168.1.24"),
    ("section number", "See section 2.3.1 for details.", "2.3.1"),
    ("four components", "Build 10.0.19045.3803 shipped.", "10.0.19045.3803"),
]


@pytest.mark.parametrize("name,text,token", WHOLE, ids=[w[0] for w in WHOLE])
def test_the_whole_token_is_locked(name: str, text: str, token: str):
    masked, mapping = lock(text)
    assert token in mapping.values(), f"{name}: {token} was not locked as one span ({mapping})"
    assert token not in masked, (
        f"{name}: part of {token} is still in open text — {masked!r}. A rewrite can edit the "
        "unmasked tail while the sentinel stays intact, so every guard reports success"
    )


@pytest.mark.parametrize("name,text,token", WHOLE, ids=[w[0] for w in WHOLE])
def test_it_round_trips(name: str, text: str, token: str):
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text


@pytest.mark.parametrize(
    "text",
    [
        "The mean was 3.5 units.",
        "It rose 1.5 percent.",
        "A ratio of 2.0 was observed.",
    ],
)
def test_an_ordinary_decimal_is_not_swallowed(text: str):
    """Two components is a number, not an identifier.

    `preserve.py` leaves small bare numbers unlocked on purpose — a rewrite may legitimately write
    "three point five" — and the numerals gate covers them instead. Locking every decimal here
    would quietly change that policy.
    """
    masked, mapping = lock(text)
    assert not any("." in v and v.count(".") >= 2 for v in mapping.values()), mapping


def test_a_version_with_a_v_prefix_still_locks_whole():
    """It did before, via the identifier rule; the new pattern must not fragment it."""
    masked, mapping = lock("Released as v2.10.3 last week.")
    assert "v2.10.3" in mapping.values(), mapping
    assert restore(masked, mapping) == "Released as v2.10.3 last week."


def test_a_date_is_not_re_locked_differently():
    """ISO dates use dashes, not dots, but a nearby rule could still overlap. Pin the outcome."""
    text = "The cutoff was 2024-03-15 exactly."
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text
