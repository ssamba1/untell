""""It is important to note that X" asserts nothing about X, and the role gate disagreed.

FOUND by asking which transforms fire and are then rejected by the gate the loop actually uses.
MEASURED over 120 corpus texts:

    _flatten_cliches              fired 22, rejected 4 — every rejection from role_swap
    _flatten_negated_contrast     fired  3, rejected 1 — a TRUE catch, see below

All four `_flatten_cliches` rejections were false vetoes of the same shape as the sign-off case one
result earlier: deleting "It's important to note that" removes the predicate *note*, and the
predicate-argument checker reads a vanished predicate as a changed role. Every other gate passed —
numbers, certainty, polarity, length, contradiction 0.002, entailment 0.856.

The cost was not a wasted draw. **1 document in 20 lost its ENTIRE structural rewrite** to it.

The exemption is exactly the set `structural._CLICHE_FLATTEN` deletes outright and nothing wider.
Exempting every catalogued cliché would let a genuine role swap hide inside a cliché match, which is
the leak direction; these nine frames carry no argument structure about the subject at all.

`_flatten_negated_contrast`'s rejection is left alone and is the reason the gate exists: numbers
False, polarity False, 54 words gone. Real damage, correctly caught.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import meaning_preserved, strip_scaffolding
from untell.scripts.quality import similarity
from untell.scripts.tells import STANCE_FRAME_RE


@pytest.fixture(autouse=True)
def _embedding_path(monkeypatch):
    """The meaning-gate bars here (0.76 similarity, NLI admission) are embedding/NLI
    measurements. Under UNTELL_LITE_NO_TORCH the similarity-only fallback rejects the
    frame removal at token_overlap 0.706 — the frame's words are a real fraction of a
    short sentence under token counting. Pin the env unset for the file.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)

DELETED_FRAMES = [
    "It's important to note that the cache is cleared on restart.",
    "It is also worth noting that the cache is cleared on restart.",
    "It should be noted that the cache is cleared on restart.",
    "It's no secret that the cache is cleared on restart.",
    "The bottom line is that the cache is cleared on restart.",
    "In conclusion, the cache is cleared on restart.",
    "In summary, the cache is cleared on restart.",
    "At its core, the cache is cleared on restart.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("text", DELETED_FRAMES, ids=lambda t: t[:24])
def test_the_pattern_matches_every_frame_it_names(text: str) -> None:
    """A known-positive per branch, which this pattern shipped without and needed.

    The first version was generated through a shell heredoc and landed as a literal 0x08 BACKSPACE
    byte where the word-boundary escape was meant. It matched nothing, the exemption did nothing,
    and every measurement looked exactly like a correct no-op — the same defect this repository has
    already recorded for three other patterns. It was caught only by re-running the measurement the
    fix was supposed to move and finding it unmoved.
    """
    assert STANCE_FRAME_RE.search(text), text


def test_the_pattern_does_not_match_ordinary_prose() -> None:
    """Guards the guard from the other side: a pattern that matched everything would exempt the
    whole document from the role check."""
    for text in ("The cache is cleared on restart.", "Note the cache setting before you deploy."):
        assert not STANCE_FRAME_RE.search(text), text


@pytest.mark.parametrize("text", DELETED_FRAMES, ids=lambda t: t[:24])
def test_removing_a_frame_survives_the_meaning_gate(text: str) -> None:
    bare = "The cache is cleared on restart."
    assert meaning_preserved(text, bare, similarity(text, bare), 0.76), text


def test_a_role_swap_inside_a_frame_is_still_caught() -> None:
    """The leak direction, and the reason the exemption is the deleted set rather than every
    cliché. Stripping the frame must not strip what it introduces."""
    a = "It is important to note that the company sued the regulator over the licence."
    b = "It is important to note that the regulator sued the company over the licence."
    assert not meaning_preserved(a, b, similarity(a, b), 0.76)


def test_the_frame_is_removed_from_both_sides() -> None:
    """Symmetry is what makes this safe: the same span disappears from source and candidate, so
    only a difference outside the frame can survive to be judged."""
    with_frame = "In conclusion, the cache is cleared on restart."
    without = "The cache is cleared on restart."
    # Case-insensitive: removing a leading frame leaves the next word lowercase, which the rewriter
    # repairs afterwards and the gate does not care about.
    assert strip_scaffolding(with_frame).strip().lower() == strip_scaffolding(without).strip().lower()


def test_every_frame_the_rewriter_deletes_is_exempted() -> None:
    """The anti-drift check. Two lists that must name the same thing is how the sign-off transform
    and the meaning gate came to disagree in the first place."""
    from untell.rewriter.structural import _CLICHE_FLATTEN

    deletions = [p for p, replacement in _CLICHE_FLATTEN if not replacement.strip()]
    # Counted rather than pattern-matched. A first version searched the deletion patterns' SOURCE
    # text for keywords and failed on `\bthe\s+bottom\s+line\s+is\s+that\s+`, because a regex's
    # source is not the prose it matches — the check was reading the wrong artefact.
    assert len(deletions) == 9, (
        "the rewriter's deletion set changed. Add the new frame to `tells.STANCE_FRAME_RE` and to "
        "DELETED_FRAMES above, or the gate will veto the transform that removes it."
    )
