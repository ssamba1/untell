"""A continuation that OPENS with a quote still counts as a continuation.

Both the ellipsis rule and the quoted-period rule decide on the NEXT WORD's case — but the plain
``nxt.lstrip()[:1].islower()`` test saw the opening quote first: ``"`` is not a letter, so
``islower()`` is False, and a lowercase continuation that happens to be quoted was treated as a
new sentence. ``He paused... "and continued."`` split into ``He paused...`` + ``"and continued."``
— the exact dangling-fragment shape the pass-520 quoted-period fix exists to remove, one quote
later. The signal is the first LETTER, past any leading quotes and brackets.
"""

from __future__ import annotations

import pytest

from untell.text_split import split_sentences

_CASES = [
    # (label, text, expected)
    ("ellipsis then quoted lowercase", 'He paused... "and continued."', 1),
    ("ellipsis then quoted capital", 'He paused... "Then he spoke."', 2),
    ("quoted period then quoted lowercase", 'She said "stop." "and left."', 1),
    ("quoted period then quoted capital", 'She said "stop." "Then left."', 2),
    ("quoted period then paren lowercase", 'He said "stop." (and then left.)', 1),
    ("ellipsis then digit", "He paused... 5 minutes later he spoke.", 2),
    ("quoted period then digit", 'He said "stop." 2 people left.', 2),
    ("regression: plain lowercase", 'He said "stop." and left.', 1),
    ("regression: plain capital", 'He said "Done." Then he left.', 2),
    ("regression: bare ellipsis lower", "He paused... then spoke. She left.", 2),
    ("regression: bare ellipsis capital", "It works... Mostly.", 2),
]


@pytest.mark.parametrize(("label", "text", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_quoted_continuation_case_decides(label, text, expected):
    got = split_sentences(text)
    assert len(got) == expected, got


def test_the_merge_keeps_the_quote_with_its_clause():
    assert split_sentences('He paused... "and continued."') == ['He paused... "and continued."']
    assert split_sentences('She said "stop." "and left."') == ['She said "stop." "and left."']
