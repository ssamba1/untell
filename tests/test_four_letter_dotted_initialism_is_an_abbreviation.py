"""A four-letter dotted initialism is an abbreviation, not three sentence fragments.

The initials test was capped at three characters, and "U.S.S.R." is four — so ``The U.S.S.R.
collapsed.`` split into ``The U.S.S.R.`` + ``collapsed.``, a dangling fragment followed by a
lowercase fragment that cannot open a sentence. The splitter feeds burstiness CV, per-sentence
scoring and the targeted rewriter's unit of work, so the miscount propagated into all of them.

The cap exists to keep a sentence-final number (``The mean was 3.5.``) from reading as an
abbreviation; the dotted-initialism branch and the digit branch are separate, so the cap applies
to letters only — ``3.5`` still ends its sentence, and ``3.5.`` as a whole-fragment section
marker still does not.
"""

from __future__ import annotations

import pytest

from untell.text_split import split_sentences

_CASES = [
    ("U.S.S.R. mid-sentence", "The U.S.S.R. collapsed. It was 1991.", 2),
    ("N.A.T.O. mid-sentence", "N.A.T.O. was founded. It still exists.", 2),
    ("A.B.C.D. mid-sentence", "A.B.C.D. stands for four things. That is all.", 2),
    ("U.S.S.R. alone", "The U.S.S.R. collapsed.", 1),
    ("regression: J.R.R. name", "It was J.R.R. Tolkien. Everyone knows it.", 2),
    ("regression: spaced initials", "J. R. R. Tolkien wrote it. Lewis did too.", 2),
    ("regression: decimal still splits", "The mean was 3.5. Variance was low.", 2),
    ("regression: section marker", "3.5. Methods. 3.6. Results.", 2),
    ("regression: single letter", "The answer is 3. The next question is harder.", 2),
]


@pytest.mark.parametrize(("label", "text", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_four_letter_dotted_initialism(label, text, expected):
    got = split_sentences(text)
    assert len(got) == expected, got


def test_the_split_lands_on_the_real_boundary():
    """``U.S.S.R.`` must stay with its verb, not dangle as a fragment."""
    assert split_sentences("The U.S.S.R. collapsed. It was 1991.") == [
        "The U.S.S.R. collapsed.",
        "It was 1991.",
    ]
