"""There is no "natural midpoint" — a word boundary chosen by counting is a clause boundary by luck.

`_split_long_sentences` initialised its split point to the midpoint and only moved it if a comma
turned up nearby. A sentence with no comma was therefore cut at whatever word sat halfway. FOUND by
reading RAID output:

    ...a team of experts in the field of artificial.
    Intelligence (AI) and medical imaging set out a set of guiding principles...

straight through the middle of "artificial intelligence". No guard downstream could catch it: the
right half opens with a capitalised noun and reads as a sentence to every check there is.

MEASURED over 269 long sentences (>28 words) across HC3 and RAID: 26 of them, 9.7%, contain no comma
at all and were being cut this way. One more contains a comma that only becomes visible after a
closing quote is stripped — `Imaging,"` does not end with a comma — and that one sentence is the one
above. Its invisible boundary is precisely how it reached the midpoint fallback.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter.structural import (
    _cannot_start_a_sentence,
    _looks_like_a_serial_list,
    _split_long_sentences,
    _split_one,
)

DRAWS = 25

NO_COMMA = (
    "In the paper a team of experts in the field of artificial intelligence and medical imaging "
    "set out a set of guiding principles and consensus recommendations for trustworthy deployment"
)
COMMA_INSIDE_QUOTES = (
    'In the paper "Guiding Principles for Trustworthy Artificial Intelligence in Future Medical '
    'Imaging," a team of experts in the field of artificial intelligence and medical imaging set '
    "out principles."
)
# The right half must be able to open a sentence on its own. A "..., so ..." boundary is NOT this
# fixture, because `_cannot_start_a_sentence` rejects a half beginning with "so" — correctly, and
# the first version of this file used one and failed for that reason rather than for the fix.
CLEAN_BOUNDARY = (
    "Crews worked through the night to clear the main roads across the county, the side streets "
    "were left untreated until the following afternoon."
)


def _split_counts(text: str, **kw) -> set[int]:
    """Sentences produced, counted by terminator.

    NOT `len(_split_long_sentences(...))`. That function returns one element per INPUT sentence and
    puts the split inside the string, so the list length is always 1 and every assertion on it
    passes whatever the code does. The first version of this file measured that and was vacuous.
    """
    counts = set()
    for seed in range(DRAWS):
        random.seed(seed)
        counts.add(sum(part.count(". ") + 1 for part in _split_long_sentences([text], **kw)))
    return counts


def test_a_sentence_with_no_comma_is_left_alone() -> None:
    assert _split_counts(NO_COMMA, max_words=20, rate=1.0) == {1}


def test_a_clean_comma_boundary_is_still_split() -> None:
    """Guards the guard. Declining every split would satisfy the test above and delete a transform
    that exists because AI sentences run long — measured, 18 net new sentence terminators on HC3 and
    76 on RAID over 40 texts each, after this change."""
    assert max(_split_counts(CLEAN_BOUNDARY, max_words=20, rate=1.0)) > 1


def test_a_comma_closing_a_quotation_is_visible_to_the_search() -> None:
    """The strip is load-bearing rather than cosmetic, and not because it enables a split here.

    Without it this sentence has no comma token at all, so it fell through to the midpoint cut.
    With it the boundary is found at `Imaging,"` — and then the appositive guard correctly refuses
    to split there, because "In the paper X," followed by "a team of experts" is exactly the
    appositive shape that guard exists for. Visible-then-rejected is a different outcome from
    invisible-then-butchered, and only the first one leaves the sentence intact.
    """
    words = COMMA_INSIDE_QUOTES.split()
    assert not [w for w in words if w.endswith(",")], "fixture no longer has the quoted comma only"
    stripped = [i for i, w in enumerate(words) if w.rstrip("\"')]”’").endswith(",")]
    assert stripped, "the closing-quote strip finds no comma; the fixture has drifted"

    at = stripped[0]
    first, second = " ".join(words[: at + 1]), " ".join(words[at + 1 :])
    assert _cannot_start_a_sentence(second, first), "the appositive guard should refuse this one"
    assert _split_counts(COMMA_INSIDE_QUOTES, max_words=20, rate=1.0) == {1}


# A comma NEAREST the midpoint that precedes a conjunction used to kill the whole split: the
# search picked it, the cannot-start guard rejected it, and the sentence was rejoined — the other,
# perfectly good comma earlier in the sentence was never tried. `_split_one` already skipped
# cannot-start commas inside its own search, so the same sentence split under one function and not
# the other. The clean comma at word 7 must still win once the conjunction comma at word 24 is
# skipped.
CONJUNCTION_TRAP = (
    "The entire data pipeline reads the incoming file, the parser then processes every single "
    "record in the correct order for later analysis by the analytics team, and the checker "
    "validates the final result."
)


def test_a_conjunction_trap_comma_does_not_kill_a_clean_split() -> None:
    assert max(_split_counts(CONJUNCTION_TRAP, max_words=20, rate=1.0)) > 1


SERIAL_LIST = (
    "The paper is the result of a collaborative effort between academia, industry, and regulatory "
    "bodies to address the ethical, social, and technical challenges associated with the use of AI "
    "in medical imaging."
)


def test_a_serial_list_is_not_a_clause_boundary() -> None:
    """Found on the re-read after the midpoint fix, in the very next RAID sentence:

        ...to address the ethical.
        Social, and technical challenges associated with the use of AI in medical imaging.

    `_split_one` has refused this shape for a long time; `_split_long_sentences` had no such guard.
    That is the THIRD time these two have been found with the same hole in one of them, so the
    predicate is now one function with two callers rather than a rule one of them can lack.
    """
    words = SERIAL_LIST.split()
    assert _looks_like_a_serial_list(words), "premise: the fixture must read as a list"
    assert _split_one(SERIAL_LIST) is None, "the older splitter has always refused this"
    assert _split_counts(SERIAL_LIST, max_words=20, rate=1.0) == {1}


def test_the_list_guard_is_shared_not_copied() -> None:
    """The point of extracting it. If either splitter grows its own copy, this is where it shows."""
    import inspect

    from untell.rewriter import structural

    source = inspect.getsource(structural)
    assert source.count("def _looks_like_a_serial_list") == 1
    assert source.count('endswith(",")) >= 3') == 1, (
        "a second copy of the serial-list threshold has appeared; the two splitters can now drift"
    )


@pytest.mark.parametrize("seed", range(10))
def test_no_split_lands_inside_a_compound_term(seed: int) -> None:
    """The specific damage, stated as the thing a reader saw: the two halves of a compound noun
    must not end up in different sentences."""
    random.seed(seed)
    produced = " ".join(_split_long_sentences([NO_COMMA], max_words=20, rate=1.0))
    assert "artificial. " not in produced, produced
    assert "artificial." not in produced.rstrip(), produced
