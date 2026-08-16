"""Bidi controls between a sentence terminator and the next word must not hide the boundary.

``_ZERO_WIDTH_BETWEEN`` covers ZWSP/ZWNJ/ZWJ/word-joiner/BOM, the invisible math
operators and the variation selectors — the carrier set scrub_hidden removes — but
NOT the bidi controls (LRM/RLM/LRE/RLE/PDF/LRO/RLO/LRI/RLI/FSI/PDI) or ALM, although
scrub_hidden strips all of them as carriers in Latin text. The splitter's own
docstring says the class is "the same carrier set untell.attacks.unicode_tricks
scrubs" — it was not.

MEASURED before the fix, every one of these splits as ONE sentence:

    split_sentences('First sentence.\u200FSecond sentence starts here.')   -> 1
    split_sentences('First sentence.\u2067Second sentence starts here.')   -> 1
    split_sentences('First sentence.\u061CSecond sentence starts here.')   -> 1

...while ZWSP in the same position splits into two. The author wrote a boundary;
the invisible character must not be allowed to hide it (the splitter removes
nothing, it only refuses to let the carrier block the split). The same class feeds
``ends_with_abbreviation`` and layout's sentence-end test, so the fix is one place.
"""

from __future__ import annotations

import pytest

from untell.text_split import ends_with_abbreviation, split_sentences

BIDI_CARRIERS = [
    ("LRM", "\u200E"), ("RLM", "\u200F"), ("LRE", "\u202A"), ("RLE", "\u202B"),
    ("PDF", "\u202C"), ("LRO", "\u202D"), ("RLO", "\u202E"), ("LRI", "\u2066"),
    ("RLI", "\u2067"), ("FSI", "\u2068"), ("PDI", "\u2069"), ("ALM", "\u061C"),
]


@pytest.mark.parametrize("name,carrier", BIDI_CARRIERS, ids=[c[0] for c in BIDI_CARRIERS])
def test_a_bidi_control_between_sentences_does_not_block_the_split(name, carrier):
    parts = split_sentences(f"First sentence.{carrier}Second sentence starts here.")
    assert len(parts) == 2, (
        f"{name}: got {len(parts)} sentence(s): {parts!r}"
    )
    assert parts[0] == f"First sentence.{carrier}"
    assert parts[1] == "Second sentence starts here."


@pytest.mark.parametrize("name,carrier", BIDI_CARRIERS, ids=[c[0] for c in BIDI_CARRIERS])
def test_a_bidi_control_after_a_terminator_then_space_splits_too(name, carrier):
    parts = split_sentences(f"First sentence.{carrier} Second sentence starts here.")
    assert len(parts) == 2, f"{name}: {parts!r}"


def test_an_abbreviation_tail_with_a_bidi_control_is_still_recognised():
    # 'p.m.\u200F' must still read as the abbreviation 'p.m.' — the carrier after the
    # period is invisible payload, not a different word.
    assert ends_with_abbreviation("The meeting is at 3 p.m.\u200F")
    parts = split_sentences("The meeting is at 3 p.m.\u200F Then we left.")
    assert len(parts) == 2, parts
    assert parts[0] == "The meeting is at 3 p.m.\u200F"
    assert parts[1] == "Then we left."


def test_an_ellipsis_continuation_merges_across_a_bidi_control():
    # '...' is a pause, not a terminator: a lowercase continuation is the same clause
    # even with a bidi control after the dots.
    parts = split_sentences(f"He paused...\u200F then continued with the analysis.")
    assert len(parts) == 1, parts


def test_a_quoted_period_continuation_merges_across_a_bidi_control():
    parts = split_sentences(f'He said "stop."\u200F and left.')
    assert len(parts) == 1, parts
