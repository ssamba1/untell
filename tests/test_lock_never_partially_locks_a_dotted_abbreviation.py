"""A three-component dotted abbreviation is never partially locked.

The dotted rule's negative lookahead excluded whole abbreviations from being locked — but it only
guards the START of a match. For a three-component abbreviation like ``u.s.a.``, the rule matched
the TAIL ``s.a`` instead, producing ``u.⟦HZ0000⟧.``: a sentinel before a bare period, which every
downstream pass that asks "is this dot a terminator?" reads as a sentence end. The fix requires a
non-word, non-dot character before the match start, so an interior component of a longer dotted
word is never locked on its own.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock
from untell.text_split import split_sentences

ABBREVIATIONS = ["u.s.a", "u.s.s.r", "e.g", "p.m", "d.c"]


@pytest.mark.parametrize("abbr", ABBREVIATIONS)
def test_no_sentinel_before_a_bare_dot(abbr: str) -> None:
    text = f"The team used {abbr}. small samples were taken from the site last week."
    masked, _ = lock(text)
    assert "⟧." not in masked, masked


@pytest.mark.parametrize("abbr", ABBREVIATIONS)
def test_masked_text_splits_into_the_same_sentences(abbr: str) -> None:
    """The mask must not change what the splitter sees: locking ``s.a`` out of ``u.s.a.`` made the
    masked text split differently from the original, miscounting every downstream consumer."""
    text = f"The team used {abbr}. small samples from the site. The results were clear enough."
    masked, _ = lock(text)
    assert len(split_sentences(masked)) == len(split_sentences(text)), (masked, text)


def test_real_dotted_identifiers_still_lock() -> None:
    """Guards the guard: the tighter start condition must not take the rule down with it."""
    for ident in ["np.float64", "tensorflow.keras", "os.path", "untell.score"]:
        text = f"The call to {ident} returns before the buffer is flushed to disk."
        masked, spans = lock(text)
        assert ident in spans.values(), (ident, masked)
