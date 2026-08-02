"""The shared sentence splitter — a bug here propagates to almost everything.

`split_sentences` feeds the burstiness term in perplexity_burstiness, the per-sentence targeting in
sentences.py, the predicate-argument triples in roles.py, and the targeted rewriter's reassembly.
It had no tests of its own; the only coverage was incidental, through callers.

The failure that matters is a naive split on ".\\s", which turns "Dr." into its own sentence. That
is not cosmetic downstream: per-sentence surprisal over a one-token fragment is noise fed straight
into burstiness, and a one-word "sentence" is scored and possibly flagged for rewriting.

Behaviour verified against the implementation before these were written — all fourteen cases below
already pass, so this pins current behaviour rather than reporting a defect.
"""

from __future__ import annotations

import pytest

from untell.text_split import split_sentences

# (label, text, expected sentence count)
_CASES = [
    ("abbreviated title", "Dr. Smith arrived. He was late.", 2),
    ("mid-sentence e.g.", "Use tools, e.g. hammers. Then stop.", 2),
    ("spaced initials", "J. R. R. Tolkien wrote it. Lewis did too.", 2),
    ("decimal number", "It rose 3.5 percent. Then fell.", 2),
    ("url with dots", "See https://ex.com/a.b/c. Then read on.", 2),
    ("no final punctuation", "First sentence. Second one", 2),
    ("blank lines", "Line one.\nLine two.\n\nLine three.", 3),
    ("repeated punctuation", "Really?! Yes. Absolutely!!", 3),
    ("numbered list", "1. First item. 2. Second item.", 2),
    ("single sentence", "Just one sentence here", 1),
]


@pytest.mark.parametrize(("label", "text", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_sentence_counts(label, text, expected):
    assert len(split_sentences(text)) == expected, split_sentences(text)


@pytest.mark.parametrize(
    "text",
    [t for _, t, _ in _CASES] + [
        "He paused... then spoke. She left.",
        'She said "stop." He stopped.',
        "Mixed: 3.5% vs. 2.1%, per Dr. Jones (2024). Next.",
    ],
)
def test_no_content_is_lost(text):
    """Every non-whitespace character must survive the split.

    This is the invariant the callers actually depend on — the targeted rewriter reassembles from
    these pieces, so a dropped character is a dropped character in the user's document.
    """
    joined = "".join("".join(p.split()) for p in split_sentences(text))
    assert joined == "".join(text.split())


@pytest.mark.parametrize("text", ["", "   ", "\n\n", "\t"])
def test_empty_input_yields_no_sentences(text):
    """Not one empty "sentence" — a fragment with no words reaches the detectors as real input and
    is scored, which is how an empty string ended up classified as AI-generated once before."""
    assert split_sentences(text) == []


def test_abbreviations_do_not_start_a_new_sentence():
    """The specific regression the abbreviation-aware splitter exists to prevent."""
    for text in ("Dr. Smith arrived.", "Use tools, e.g. hammers.", "It rose 3.5 percent."):
        assert len(split_sentences(text)) == 1, split_sentences(text)
