"""A sentence-final abbreviation no longer swallows the next sentence.

``The meeting is at 3 p.m. Then we left.`` used to come back as ONE sentence. The splitter's
abbreviation rule is what caused it: ``p.m.`` is in the dictionary, so the merge that protects
``Dr. Smith`` and ``e.g. hammers`` also swallowed a real boundary — the period after ``p.m.``
ended the sentence, and the capital ``Then`` opens the next one. Same for ``U.S.A.``, ``et al.``
and every other multi-character abbreviation. The under-count feeds burstiness CV, per-sentence
scoring and the targeted rewriter's unit of work.

The merge survives exactly where it must: a lowercase continuation cannot open a sentence
(``p.m. for the meeting``), a digit or parenthesis start is a citation, not a sentence
(``et al. (2020)``, ``et al. 2020``), and name prefixes (``Dr.``, ``J.R.R.``, ``1.``) keep the
unconditional merge because the capital after them is a name or an item, not a sentence.
"""

from __future__ import annotations

import pytest

from untell.text_split import split_sentences

# (label, text, expected sentences)
_CASES = [
    ("p.m. then a new sentence", "The meeting is at 3 p.m. Then we left.", 2),
    ("U.S.A. then a new sentence", "We moved to the U.S.A. It was 1998.", 2),
    ("et al. then a new sentence", "He cited Smith et al. Jones disagreed.", 2),
    ("Ph.D. then a new sentence", "He has a Ph.D. Students must register.", 2),
    ("etc. then a new sentence", "Bring tools etc. That is all.", 2),
    ("U.S. then a new sentence", "He lived in the U.S. He loved it.", 2),
    ("lowercase continuation merges", "He arrived at 3 p.m. for the meeting.", 1),
    ("digit continuation stays merged", "The meeting is at 3 p.m. 5 people came.", 1),
    ("paren citation stays merged", "See Smith et al. (2020) for details.", 1),
    ("bare-year citation stays merged", "See Smith et al. 2020 for details.", 1),
    ("regression: Dr. mid-sentence", "Dr. Smith arrived. He was late.", 2),
    ("regression: e.g. mid-sentence", "Use tools, e.g. hammers. Then stop.", 2),
    ("regression: lowercase abbr use", "The method removes fine detail (e.g. small branches).", 1),
]


@pytest.mark.parametrize(("label", "text", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_sentence_final_abbreviation_boundary(label, text, expected):
    got = split_sentences(text)
    assert len(got) == expected, got


@pytest.mark.parametrize(("label", "text", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_no_content_is_lost(label, text, expected):
    """The fix must split, never drop — the rewriter reassembles from these pieces."""
    joined = "".join("".join(p.split()) for p in split_sentences(text))
    assert joined == "".join(text.split())


def test_the_split_lands_on_the_real_boundary():
    """The sentence after the abbreviation must be WHOLE, not the fragment the regex left behind."""
    assert split_sentences("The meeting is at 3 p.m. Then we left.") == [
        "The meeting is at 3 p.m.",
        "Then we left.",
    ]
    assert split_sentences("We moved to the U.S.A. It was 1998.") == [
        "We moved to the U.S.A.",
        "It was 1998.",
    ]
