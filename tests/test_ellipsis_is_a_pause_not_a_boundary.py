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


# --- sentence-start capitalisation must not rewrite non-prose tokens -----------------------------
# The restore pass upcases the first letter after any terminator. That is right for prose and wrong
# for what technical text puts at a sentence start. MEASURED before the shape guard:
#
#     "Call untell.score. untell.tells also works."  -> "... Untell.tells also works."
#
# An identifier, module path, flag or file path is lowercase because that is its spelling, not
# because a capital went missing — and broken capitalisation is itself a catalogued tell.

NOT_PROSE = [
    ("dotted identifier", "Call untell.score. untell.tells also works.", "untell.tells"),
    ("long flag", "Run the tool. --tier full is the default.", "--tier"),
    ("posix path", "See the file. src/main.py has it.", "src/main.py"),
    # Raw string: written through a shell heredoc this collapsed to a real carriage return, so the
    # fixture tested CR handling rather than backslashes and `\S*` stopped at the whitespace.
    ("windows path", r"Open it. docs\readme.md explains why.", r"docs\readme.md"),
    ("call", "Check it. score_text(x) returns a dict.", "score_text(x)"),
    ("comparison", "Pin it. untell==0.2.0 is the version.", "untell==0.2.0"),
]


@pytest.mark.parametrize(("label", "text", "token"), NOT_PROSE, ids=[c[0] for c in NOT_PROSE])
def test_a_non_prose_token_keeps_its_own_spelling(label, text, token):
    out = _flatten_cliches(text)
    assert token in out, f"{label}: {out!r}"


PROSE = [
    ("lowercase pronoun", "The result was clear. it was also cheap.", "It was"),
    ("after interrobang", "What?! yes it does.", "Yes it"),
    ("start of text", "it works well enough.", "It works"),
]


@pytest.mark.parametrize(("label", "text", "expected"), PROSE, ids=[c[0] for c in PROSE])
def test_an_ordinary_word_still_gets_its_capital(label, text, expected):
    """Guards the guard: the shape check must not disable the correction this function exists for."""
    assert expected in _flatten_cliches(text), label


def test_a_cliche_deletion_still_restores_the_capital():
    assert _flatten_cliches("It is important to note that the system works.").startswith("The ")
