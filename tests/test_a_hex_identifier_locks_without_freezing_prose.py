"""A git sha must lock; the word "defaced" must not.

Hex identifiers — short shas, full shas, digests — were rewritable: one altered character makes
them point at nothing, and no rule in `preserve.py` covered them. The obvious fix is a hex
character class, and the obvious objection is that English is full of hex-shaped words.

MEASURED over 240 real texts (120 HC3 + 120 RAID pairs) plus prose traps, before choosing:

    [0-9a-f]{7,40}                     0 corpus locks, but locks "defaced"
    + at least one digit               0 corpus locks, 0 traps, 4/4 shas
    + at least one digit AND letter    0 corpus locks, 0 traps, 4/4 shas

The last is what shipped. The digit requirement rules out "defaced", "deadbeef" and "facade"; the
letter requirement keeps runs of plain digits in the number rule that already owns them.

A false lock is worse than a miss here. A locked span is frozen out of every rewrite for the whole
run, so locking an ordinary word silently degrades the output; a missed sha is still covered by the
other meaning gates. That asymmetry is why the pattern is the strict one and why the prose traps
are tested as hard as the shas.
"""
from __future__ import annotations

import pytest

from untell.scripts.preserve import lock, restore

SHAS = [
    ("short sha", "Fixed in commit 4f2a91c last week.", "4f2a91c"),
    ("md5", "The digest was a3f5b2c9d8e14f6072b3c4d5e6f70819.", "a3f5b2c9d8e14f6072b3c4d5e6f70819"),
    ("sha1", "See 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b for the tree.",
     "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"),
    ("mixed", "Reverted deadbeef123 after the outage.", "deadbeef123"),
]

PROSE = [
    "It took a decade to finish.",
    "The wall was defaced overnight.",
    "They added the feature and beefed up the tests.",
    "A facade of calm covered the effort.",
    "The cafe added a decaffeinated option.",
]


@pytest.mark.parametrize("name,text,token", SHAS, ids=[s[0] for s in SHAS])
def test_the_hex_identifier_is_locked_whole(name: str, text: str, token: str):
    masked, mapping = lock(text)
    assert token in mapping.values(), f"{name}: {token} not locked ({mapping})"
    assert token not in masked
    assert restore(masked, mapping) == text


@pytest.mark.parametrize("text", PROSE)
def test_ordinary_words_are_not_frozen(text: str):
    """The expensive direction. A locked word cannot be rewritten for the whole run."""
    _, mapping = lock(text)
    hexish = [v for v in mapping.values() if v.isalnum() and v.islower() and len(v) >= 7]
    assert not hexish, f"{text!r} locked an ordinary word: {hexish}"


def test_a_plain_run_of_digits_stays_with_the_number_rule():
    """The letter requirement exists so this rule does not shadow the numeric one."""
    _, mapping = lock("The id was 1234567 in the export.")
    assert "1234567" in mapping.values(), mapping


def test_uppercase_digests_are_covered_by_the_identifier_rule():
    """Checked rather than assumed — the first version of the comment claimed these were a miss."""
    for text, token in (
        ("The digest was A3F5B2C9D8E14F6072B3C4D5E6F70819.", "A3F5B2C9D8E14F6072B3C4D5E6F70819"),
        ("Model ABCDEF1 shipped in 2024.", "Model ABCDEF1"),
    ):
        _, mapping = lock(text)
        assert token in mapping.values(), f"{token} unlocked ({mapping})"


def test_a_six_character_hex_is_left_alone():
    """Seven is the floor because git short shas are; shorter runs are too word-like to risk."""
    _, mapping = lock("The colour code was a3f5b2 in the sheet.")
    assert "a3f5b2" not in mapping.values(), mapping
