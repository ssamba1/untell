"""An ellipsis is a pause. Treating it as a sentence end manufactures fragments.

Two independent places read the last dot of "..." as a terminator:

* `split_sentences` — its lookbehind is `[.!?]`, so "He paused... then continued." became two
  sentences, the second starting lowercase with no subject.
* `_AFTER_SENTENCE_START` in the cliché flattener — it upcases any lowercase letter following
  `[.!?]\\s+`, over the whole text rather than only where a deletion happened.

Together they turned correct input into "He paused... Then continued with the analysis." on 4 of
12 seeds. Nothing downstream could see it: no word changed, so similarity, NLI and the role check
all pass, and a subjectless fragment is clean to a tell catalogue.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import StructuralRewriter, _flatten_cliches
from untell.text_split import split_sentences

SCORE: dict = {"tier": "full", "max": 1.0, "detectors": {}}
_PROMOTED = re.compile(r"(?:\.{2,}|…)\s+[A-Z]")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A lowercase continuation is one sentence.
        ("He paused... then continued with the analysis. She left.", 2),
        ("He paused… then continued with the analysis. She left.", 2),
        ("Wait.. what happened next. Nobody knew.", 2),
        # A capitalised clause after an ellipsis IS a new sentence.
        ("It works... Mostly. The team shipped it.", 3),
        ("The result was clear... But nobody acted. Costs rose.", 3),
        # Unaffected.
        ("First sentence. Second sentence.", 2),
    ],
)
def test_the_splitter_treats_an_ellipsis_by_what_follows_it(text: str, expected: int):
    assert len([s for s in split_sentences(text) if s.strip()]) == expected


@pytest.mark.parametrize(
    "text",
    [
        "He paused... then continued with the analysis. She left the room quietly.",
        "The result was clear... but nobody acted on it for months. Costs rose.",
        "It works... mostly. The team shipped it anyway last quarter.",
    ],
)
def test_a_rewrite_never_promotes_the_continuation_to_a_sentence(text: str):
    rewriter = StructuralRewriter(intensity=1.0)
    for seed in range(12):
        random.seed(seed)
        out = rewriter.rewrite(text, SCORE, 0.30, intensity=1.0)
        assert not _PROMOTED.search(out), f"seed {seed}: {out}"


def test_the_cliche_flattener_still_restores_a_real_capital():
    """The behaviour the narrowed pattern must not break."""
    assert _flatten_cliches("It is important to note that the system works.").startswith("The ")


def test_a_terminator_that_is_not_a_dot_still_capitalises():
    """`(?<!\\.)` must exclude ellipses only, not every doubled terminator."""
    assert _flatten_cliches("What?! yes it does.") == "What?! Yes it does."


def test_an_ordinary_sentence_boundary_still_capitalises():
    assert _flatten_cliches("it works. it really does.") == "It works. It really does."
