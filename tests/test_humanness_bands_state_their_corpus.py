"""The humanness bands were placed around a separability that only one corpus has.

`classification`'s docstring recorded "lowest HUMAN 75.6, highest AI 72.0 — a boundary at 75
misclassifies 0 of 80 in either direction". Re-measured on the same protocol, 40 pairs each:

    corpus   lowest HUMAN   highest AI   human below 75
    RAID          79.2         44.0           0 / 40
    HC3           41.0         44.0          14 / 40

The claim holds on RAID and fails on HC3, and at 41.0 against 44.0 the ranges overlap, so no cut
separates them. Averaging the corpora is what hid it.

These tests pin the property that DOES hold and is the one that matters — nothing calls AI writing
human — plus the band arithmetic, which is cheap and corpus-free. The corpus-dependent figures live
in the docstring, where they can be re-measured rather than silently trusted.
"""

from __future__ import annotations

import pytest

from untell.humanness import classification


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (100.0, "human"),
        (75.0, "human"),
        (74.9, "mostly human"),
        (60.0, "mostly human"),
        (59.9, "mixed"),
        (45.0, "mixed"),
        (44.9, "likely AI"),
        (30.0, "likely AI"),
        (29.9, "AI"),
        (0.0, "AI"),
    ],
)
def test_the_bands_are_where_the_docstring_says(score: float, label: str):
    assert classification(score) == label


def test_the_bands_are_monotonic():
    """A higher score may never get a less human label."""
    order = ["AI", "likely AI", "mixed", "mostly human", "human"]
    ranks = [order.index(classification(s)) for s in range(0, 101, 1)]
    assert ranks == sorted(ranks)


def test_the_cannot_tell_answer_lands_in_mixed():
    """Short and empty text both return 50.0; that must not read as a verdict either way."""
    assert classification(50.0) == "mixed"


def test_the_docstring_records_that_separability_is_corpus_dependent():
    """The claim this file exists for. If the caveat is dropped, this fails rather than the reader.

    The original "0 of 80 in either direction" is left in place deliberately — it was true when
    taken — so the check is that the correction sits beside it.
    """
    doc = classification.__doc__ or ""
    assert "41.0" in doc, "the measured HC3 minimum must be recorded"
    assert "RAID" in doc and "HC3" in doc, "the two corpora must be named separately"
    assert "OVERLAP" in doc.upper(), "the ranges overlap; a reader must not infer a clean cut"


def test_the_boundary_is_safe_in_the_direction_that_matters():
    """No AI text reached 75 in either corpus (0 of 80), so 75 must stay a 'human' score.

    Lowering the boundary to recover the HC3 false positives would start admitting AI text, which
    is the trade this scale explicitly declines.
    """
    assert classification(75.0) == "human"
    assert classification(44.0) != "human", "the highest AI score measured must not be 'human'"
