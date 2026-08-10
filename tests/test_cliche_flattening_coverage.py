"""`cliche` is the strongest category in the catalogue, and the rewriter treated 28% of it.

Precision 0.902 on HC3 and 0.941 on RAID — it is the tell most worth acting on. AUDITED by probing
every pattern in `tells._CLICHES` through the structural rewriter: 41 of 57 fired as a tell and
survived every draw. Detection without treatment.

These tests pin the treated set and, more importantly, the two properties that make a flattening
safe: it must not itself be a catalogued tell, and it must not break the sentence.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import _CLICHE_FLATTEN, StructuralRewriter
from untell.scripts.tells import score_tells

_REWRITER = StructuralRewriter()

FLATTENED = [
    ("In conclusion, the team shipped the release on Friday.", "in conclusion"),
    ("It should be noted that the results were mixed.", "it should be noted"),
    ("At its core, the design favours simplicity.", "at its core"),
    ("The bottom line is that costs rose sharply.", "the bottom line is"),
    ("This is a game-changer for the industry.", "game-chang"),
    ("We will dive into the data next week.", "dive into"),
    ("The report will shed light on the discrepancy.", "shed light on"),
    ("In the world of finance, liquidity rules.", "in the world of"),
    ("That is only the tip of the iceberg here.", "tip of the iceberg"),
    ("Remote work is a double-edged sword for teams.", "double-edged sword"),
]


@pytest.mark.parametrize("text,phrase", FLATTENED, ids=[p for _, p in FLATTENED])
def test_the_cliche_is_gone(text: str, phrase: str) -> None:
    random.seed(0)
    assert phrase not in _REWRITER.rewrite(text, score_tells(text)).lower()


def test_no_replacement_is_itself_a_catalogued_tell() -> None:
    """The trap this repo has hit repeatedly: a fix whose output is another entry in the catalogue."""
    offenders = []
    for _pattern, replacement in _CLICHE_FLATTEN:
        if not replacement.strip():
            continue
        probe = f"The team said the plan was {replacement.strip()} and everyone agreed on it."
        fired = score_tells(probe)["by_category"]
        if fired:
            offenders.append((replacement.strip(), dict(fired)))
    assert not offenders, f"replacements that are themselves tells: {offenders}"


_SMELLS = {
    "lowercase sentence start": re.compile(r"[.!?]\s+[a-z]"),
    "doubled word": re.compile(r"\b(\w+)\s+\1\b", re.I),
    "space before punctuation": re.compile(r"\s+[,.;:!?]"),
    "leading punctuation": re.compile(r"^\s*[,.;]"),
    "doubled space": re.compile(r"\w  +\w"),
}


@pytest.mark.parametrize("text,_phrase", FLATTENED, ids=[p for _, p in FLATTENED])
def test_flattening_does_not_break_the_sentence(text: str, _phrase: str) -> None:
    """A deletion leaves a seam. "In conclusion, X" must become "X", capitalised, not ", X"."""
    random.seed(0)
    out = _REWRITER.rewrite(text, score_tells(text))
    for name, pattern in _SMELLS.items():
        assert not (pattern.search(out) and not pattern.search(text)), f"{name} in {out!r}"


def test_number_agreement_is_out_of_scope_and_stays_out() -> None:
    """"one of the most important rules" -> "a key rules" is why that entry is not in the table.

    A substitution table matches a string and cannot inflect what follows it. Asserted so the
    tempting entry is not added back by someone reading the coverage number as a target.
    """
    text = "In finance, one of the most important rules is liquidity."
    random.seed(0)
    out = _REWRITER.rewrite(text, score_tells(text))
    assert "a key rules" not in out.lower()


def test_assertive_closers_are_left_alone() -> None:
    """These are claims, not scaffolding. Removing one deletes a proposition the author made."""
    for text in [
        "The future looks bright for the sector.",
        "Only time will tell whether it works.",
        "One thing is certain: the market will change.",
    ]:
        random.seed(0)
        out = _REWRITER.rewrite(text, score_tells(text))
        assert "cliche" in score_tells(out)["by_category"], (
            f"{text!r} was flattened; if that is now wanted, it is a meaning edit and needs its "
            "own justification"
        )
