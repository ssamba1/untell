"""Punctuation spacing must not decide a detector's verdict.

`Hello-SimpleAI/chatgpt-detector-roberta` is trained on HC3, whose two halves were preprocessed
differently: over 300 pairs the HUMAN half carries 90.33 space-before-punctuation marks per 1,000
words against the ChatGPT half's 0.02, separating the classes about 4,500:1. The model learned the
artefact. Inserting one space before each period drove it to exactly 0.000 on 25 of 25 RAID
documents, taking AUROC from 0.9871 to 0.1571 — below chance, so the attack inverts the detector
rather than blinding it.

That is reachable by accident, which is what makes it worth a test rather than a note: PDF text
extraction routinely inserts a space before punctuation, and double-space-after-period is an
ordinary typing habit.

The unit tests below need no model. The two integration tests do, and skip without one.
"""

from __future__ import annotations

import pytest

from untell.detectors.base import normalise_whitespace

# The artefact in each of the forms that reached the model.
EQUIVALENT_SPACINGS = [
    "The result was clear. The team shipped it.",
    "The result was clear.  The team shipped it.",  # double space after the period
    "The result was clear.   The team shipped it.",  # triple
    "The result was clear . The team shipped it .",  # space before the period (the HC3 artefact)
    "The result was clear.\tThe team shipped it.",  # tab
]


@pytest.mark.parametrize("text", EQUIVALENT_SPACINGS)
def test_normalisation_collapses_every_spacing_to_one_form(text: str) -> None:
    assert normalise_whitespace(text) == "The result was clear. The team shipped it."


def test_normalisation_preserves_line_structure() -> None:
    """Newlines are paragraphing, not the artefact — and were measured not to move any detector."""
    assert normalise_whitespace("One.\n\nTwo.") == "One.\n\nTwo."
    assert normalise_whitespace("One.  \n  Two.") == "One.\n Two."


def test_normalisation_is_a_no_op_on_clean_text() -> None:
    """The reason the fix is free: on ordinary prose it must change nothing at all."""
    clean = "The kettle boiled while I read the last few pages. Rain had started again, and the\nwindow fogged at the corners. I put the book down (finally) and went to look for a coat."
    assert normalise_whitespace(clean) == clean


def test_normalisation_does_not_touch_decimals_or_ellipses() -> None:
    assert normalise_whitespace("It cost 3.50 and took 1,200 ms...") == "It cost 3.50 and took 1,200 ms..."


def _detector(name: str):
    from untell.detectors import load_detectors

    for d in load_detectors():
        if d.name == name and d.available():
            return d
    pytest.skip(f"{name} unavailable (needs torch + transformers + model)")


# 120 words: comfortably one scoring window, so windowing cannot explain any difference.
_SAMPLE = (
    "The committee published its findings on Tuesday after a review that had run for most of the "
    "year. Three of the seven recommendations concern procurement, and the rest deal with how "
    "records are kept between departments. The chair said the delay was caused by a backlog of "
    "submissions rather than any disagreement among members. A second report covering the same "
    "period is expected before the end of the quarter, and officials have said it will be "
    "published in full rather than summarised. Several members have asked for the underlying "
    "data to be released alongside it so that the calculations can be checked independently by "
    "anyone who wants to repeat the work themselves."
)


@pytest.mark.parametrize("name", ["hc3_roberta", "roberta_openai"])
def test_spacing_does_not_change_the_score(name: str) -> None:
    """The invariant that was violated: same words, different punctuation spacing, same verdict."""
    d = _detector(name)
    base = d.score(_SAMPLE)
    assert base is not None
    for variant in (
        _SAMPLE.replace(".", " ."),  # drove hc3_roberta to 0.000 on 25 of 25 documents
        _SAMPLE.replace(". ", ".  "),
        _SAMPLE.replace(" ", "  "),
    ):
        got = d.score(variant)
        assert got is not None
        assert abs(got - base) < 1e-6, (
            f"{name}: respacing punctuation moved the score {base:.4f} -> {got:.4f}"
        )


@pytest.mark.parametrize("name", ["hc3_roberta", "roberta_openai"])
def test_clean_text_score_is_unchanged_by_the_fix(name: str) -> None:
    """Normalisation must be invisible on text that never had the artefact."""
    d = _detector(name)
    assert d.score(_SAMPLE) == d.score(normalise_whitespace(_SAMPLE))
