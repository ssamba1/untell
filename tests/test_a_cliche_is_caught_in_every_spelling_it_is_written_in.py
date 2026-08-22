"""`game-?changer` matched two spellings of three, and the missing one is the common one.

The `?` makes the HYPHEN optional, which covers "game-changer" and "gamechanger". It does not
cover "game changer", because a space is a different character from a hyphen. That is the most
frequent written form in English prose and in AI output alike, so the pattern was blind to the
majority case while reading as though it handled all of them.

MEASURED before the fix:

    _CLICHE_RE.search("This is a game changer.")   ->  None

This is the recurring defect class in this catalogue, and it is invisible from the outside: a
pattern that matches nothing contributes a count of zero, which is indistinguishable from a
document that genuinely has no tells. It has appeared here as a literal 0x08 byte where `\\b` was
meant (three dead patterns, 2526 tests still green) and as `it (?:is|'s)` never matching a
contraction. The remedy is the same each time and it is what this module does: assert every
counting pattern against a string it is supposed to match.

The near-misses matter as much as the hits. `[- ]?` must not start matching "game" alone, or
"the game changed", which would trade a false zero for a false positive on ordinary prose.
"""

from __future__ import annotations

from untell.scripts.tells import _CLICHE_RE, score_tells

# All three spellings a writer actually produces. The spaced form is the one that was missed.
SPELLINGS = [
    "This is a game changer for the industry.",
    "This is a game-changer for the industry.",
    "This is a gamechanger for the industry.",
    "It was a game changing decision.",
    "It was a game-changing decision.",
]

# Prose that contains the word "game" but not the cliche. A separator made too permissive would
# start firing here, which is the failure the fix must not trade into.
NOT_THE_CLICHE = [
    "The game changed after halftime.",
    "She changed the game she was playing.",
    "A game, changed by rain, resumed on Sunday.",
]

# THE TRADE, stated rather than discovered later. Allowing a space means the literal noun phrase
# "game changer" now matches wherever it appears, so a sentence like
#
#     "The board game changer mechanism was jammed."
#
# is counted as a cliche. That is a false positive and it is accepted: "game changer" used as a
# plain compound noun is rare in prose, while the spaced spelling of the cliche is the COMMON one,
# so refusing the space to protect the rare case costs far more than it saves. Recorded here so
# the next reader finds the reasoning instead of rediscovering the case.
ACCEPTED_FALSE_POSITIVE = "The board game changer mechanism was jammed."


def test_every_spelling_of_the_cliche_is_caught():
    for text in SPELLINGS:
        assert _CLICHE_RE.search(text), f"cliche not matched in: {text!r}"


def test_the_spaced_form_specifically_matches():
    """Stated on its own, because this is the one that was silently missing."""
    match = _CLICHE_RE.search("This is a game changer.")
    assert match is not None, "the spaced form is the common one and was not matched"
    assert match.group(0).lower() == "game changer"


def test_ordinary_prose_about_a_game_is_not_a_cliche():
    """`[- ]?` must not have bought the spaced form at the cost of a false positive."""
    for text in NOT_THE_CLICHE:
        assert not _CLICHE_RE.search(text), f"false positive on ordinary prose: {text!r}"


def test_the_accepted_false_positive_is_still_the_behaviour_that_ships():
    """Pin the trade, so a later reader sees a decision rather than an oversight.

    If someone tightens the separator to kill this case, this test fails and points them at the
    reasoning above -- which is the whole reason it is written down.
    """
    assert _CLICHE_RE.search(ACCEPTED_FALSE_POSITIVE), (
        "the accepted false positive stopped firing -- if that was deliberate, the spaced form "
        "of the cliche probably stopped matching too; check that first"
    )


def test_the_spaced_form_reaches_the_score_and_is_not_only_a_regex_property():
    """A pattern can match while the category is never consulted -- check the shipped path.

    `_claimed_spans` counts by span, so a pattern that matches can still contribute nothing if
    another category claimed the same characters first. Asserting on the score is what makes this
    a statement about the product rather than about a regex.
    """
    spaced = score_tells("This is a game changer for the industry and everyone knows it.")
    clean = score_tells("The bus was late again and I walked to the office in the rain today.")

    assert spaced["tells_per_100w"] > clean["tells_per_100w"], (
        f"the cliche did not raise the tell rate: {spaced['tells_per_100w']} "
        f"vs {clean['tells_per_100w']}"
    )
