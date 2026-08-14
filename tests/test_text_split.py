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


class TestASentenceMayEndInANumber:
    """The initials test was length-only — "every dot-separated part is at most one character".

    "3.5" satisfies that exactly as well as "J.R" does, so a sentence ending in a single digit or a
    single-digit decimal was read as an abbreviation and never ended. Two sentences came back as
    one, and this splitter feeds burstiness CV, per-sentence scoring, and the targeted rewriter's
    unit of work, so the miscount propagated into all of them.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "The mean was 3.5. Variance was low.",
            "The answer is 3. The next question is harder.",
            "Growth reached 7.2. That beat every forecast.",
            "Accuracy hit 0.9. Precision lagged behind.",
            "See section 4. The details are there.",
        ],
    )
    def test_a_trailing_number_ends_the_sentence(self, text):
        assert len(split_sentences(text)) == 2, split_sentences(text)

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1. First item. 2. Second item.", 2),
            ("3.5. Methods. 3.6. Results.", 2),
        ],
    )
    def test_a_list_or_section_marker_still_does_not_end_a_sentence(self, text, expected):
        """A number that IS the whole fragment is a marker; a sentence-final number has words
        before it. That is the only thing separating "1. First item" from "The answer is 1."."""
        assert len(split_sentences(text)) == expected, split_sentences(text)

    @pytest.mark.parametrize(
        "text",
        ["Dr. Smith arrived. He was late.", "It was J.R.R. Tolkien. Everyone knows it."],
    )
    def test_real_initials_and_abbreviations_are_untouched(self, text):
        # NB: an abbreviation that ENDS a sentence ("...moved to the U.S.A. It was 1998.") stays
        # merged. That is ambiguous without a parser and is pre-existing behaviour, unrelated to
        # the numeric case fixed here.
        assert len(split_sentences(text)) == 2, split_sentences(text)


class TestSentencesThatEndInsideAQuoteOrBracket:
    r"""Terminal punctuation is not always the last character of a sentence.

    `He said "Done." Then he left.` puts the closing quote between the period and the space, so a
    bare `(?<=[.!?])\s+` never fires and the two sentences come back as one. MEASURED on HC3: 23 of
    800 texts contain at least one such boundary. Every one is a silent UNDER-count, and the
    under-count lands in the statistic burstiness is built on — two sentences merged into one long
    one is precisely the length-variance signal the detector reads.
    """

    def test_a_closing_quote_does_not_swallow_the_boundary(self):
        assert split_sentences('He said "Done." Then he left.') == [
            'He said "Done."',
            "Then he left.",
        ]

    def test_curly_quotes_too(self):
        assert split_sentences("She said “Go.” He went.") == [
            "She said “Go.”",
            "He went.",
        ]

    def test_a_closing_bracket_too(self):
        assert split_sentences("(See note.) Next up.") == ["(See note.)", "Next up."]

    def test_a_quote_nested_in_a_bracket_still_ends(self):
        assert split_sentences('(He said "Done.") Next up.') == ['(He said "Done.")', "Next up."]

    def test_the_closer_stays_with_its_sentence(self):
        """The closer is behind the split point, not consumed as part of the separator — consuming
        it would split correctly and delete the character from the output."""
        out = split_sentences('He said "Done." Then he left.')
        assert "".join(out).count('"') == 2

    def test_a_mid_sentence_quote_is_not_a_boundary(self):
        assert split_sentences('A quote "like this," and more. Done.') == [
            'A quote "like this," and more.',
            "Done.",
        ]

    def test_an_abbreviation_inside_a_quote_still_does_not_end_the_sentence(self):
        assert split_sentences('He said "See Fig. 3 for details." Then he left.') == [
            'He said "See Fig. 3 for details."',
            "Then he left.",
        ]

    def test_a_quoted_period_with_a_lowercase_continuation_is_not_a_boundary(self):
        """A quote's period only ends the sentence when a new sentence follows.

        `He said "stop." and left.` — the quoted period is followed by a LOWERCASE
        continuation, which cannot open a new sentence, so the period was mid-sentence and the
        fragment "and left." must merge back. The splitter used to cut there, handing the
        rewriter (and back_translation's chunker) a dangling clause as a standalone "sentence".
        A capitalised continuation (`"Done." Then he left.`) still splits — the case of the
        next word decides, same shape as the ellipsis rule.
        """
        assert split_sentences('He said "the meeting is at 3." and left.') == [
            'He said "the meeting is at 3." and left.',
        ]
        assert split_sentences('He said "the meeting is at 3 p.m." and left.') == [
            'He said "the meeting is at 3 p.m." and left.',
        ]
        # capitalised continuation keeps the split
        assert split_sentences('He said "Done." Then he left.') == [
            'He said "Done."',
            "Then he left.",
        ]
        # bracket-nested quoted period keeps the split on a capitalised next sentence
        assert split_sentences('(He said "Done.") Next up.') == [
            '(He said "Done.")',
            "Next up.",
        ]
