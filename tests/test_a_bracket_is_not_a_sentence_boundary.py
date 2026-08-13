"""A full stop inside a parenthesis, mid-sentence, is a shape no human writes.

`_semicolons_to_periods` promotes "; " to a sentence break where the right side can stand alone. It
had no idea about brackets, so a semicolon inside one was promoted too — and no clause inside a
bracket can stand alone however well-formed it is, because the sentence continues after the closing
bracket. MEASURED on five ordinary sentences through the shipped loop, 5 of 5 damaged:

    (the vote was seven to two; two members abstained)
        ->  (the vote was seven to two. Basically, two members abstained)
    (the effect was small; the interval was wide)
        ->  (the effect was small. The interval was wide)

    5 of 5 before. 0 of 5 after.

The opener is the second half of the damage: once the break exists, the later stages treat the
fragment as a sentence and give it one, which is how "Basically," ended up inside the brackets.

**Result 215's citation fix was this bug seen through one keyhole.** `(Smith, 2019; Jones, 2020)`
was damaged because it is a bracket, not because it is a citation — locking the citation fixed the
citations and left every other parenthetical in the language broken. Both changes are kept: the lock
protects author names and years from transforms that have nothing to do with semicolons.

Found by matrixing spans that fail to lock against six carrier sentences. The four rows that came
back damaged were damaged by ALL six carriers, which is the tell that the carrier was not doing it —
the interior semicolon was, and the damage had nothing to do with preservation at all.
"""

from __future__ import annotations

import logging
import re

import pytest

from untell.rewriter.structural import (
    _inside_brackets,
    _semicolons_to_periods,
    _split_lands_inside_brackets,
    _split_one,
)
from untell.scripts.run import untell_text

# A period followed by a capital, inside a bracket that opens and closes on the same line.
SPLIT_IN_BRACKET = re.compile(r"\([^()]*[.!?]\s+[A-Z][^()]*\)")
PROSE = (
    "Moreover, it is important to note that the follow-up work found the same pattern in every "
    "cohort. Furthermore, this underscores the robustness of the result across the sites."
)
BRACKETED = [
    "The council approved the plan (the vote was seven to two; two members abstained) at the meeting.",
    "The trial met its endpoint (the effect was small; the interval was wide) in every recruiting site.",
    "She kept the receipts (they were faded; the ink had run) in a box under the desk for years.",
    "The route was closed (a tree had fallen; the crew were slow) for most of the working week.",
    "The budget held (staff costs fell; energy rose) across the whole of the reporting period.",
]
UNBRACKETED = [
    "We shipped it; the customers were happy about that.",
    "The vote was seven to two; two members abstained today.",
    "Costs fell; revenue rose across the whole of the year.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("doc", BRACKETED, ids=lambda d: d.split("(")[0].strip()[:24])
def test_the_loop_does_not_split_inside_a_bracket(doc: str) -> None:
    final = untell_text(doc + " " + PROSE, tier="lite", max_iters=3)["final"]
    found = SPLIT_IN_BRACKET.search(final)
    assert not found, found.group(0) if found else final[:160]


@pytest.mark.parametrize("text", BRACKETED, ids=lambda d: d.split("(")[0].strip()[:24])
def test_the_transform_leaves_a_bracketed_semicolon_alone(text: str) -> None:
    assert ";" in _semicolons_to_periods(text)


@pytest.mark.parametrize("text", ["The plan passed [the vote was seven to two; two members abstained] here.",
                                  "The plan passed {the vote was seven to two; two members abstained} here."],
                         ids=["square", "brace"])
def test_other_bracket_shapes_count_too(text: str) -> None:
    assert ";" in _semicolons_to_periods(text)


@pytest.mark.parametrize("text", UNBRACKETED, ids=["shipped", "vote", "costs"])
def test_the_transform_still_fires_outside_brackets(text: str) -> None:
    """Guards the guard. A guard that swallowed every semicolon would pass every assertion above
    while disabling a transform this repository added deliberately — and `semicolon_crutch` is a
    tell it catalogues at 2+ per thousand words, so the transform stopping is a real cost."""
    result = _semicolons_to_periods(text)
    assert ";" not in result, result
    assert ". " in result


def test_a_stray_closing_bracket_does_not_freeze_the_rest() -> None:
    """Depth is clamped at zero rather than going negative, so a smiley cannot make everything after
    it untouchable. This is the failure mode of counting instead of parsing, and it is the one worth
    choosing: an unbalanced bracket is common in real text and nesting is not."""
    text = "A smiley :) then we shipped it; the customers were happy about that."
    assert ";" not in _semicolons_to_periods(text)


def test_an_unclosed_bracket_is_treated_as_open() -> None:
    """The other direction, recorded as chosen rather than accidental: after "(see over" the text
    really is inside a bracket as far as anything can tell, so the conservative reading applies."""
    text = "See over (continued and we shipped it; the customers were happy today."
    assert ";" in _semicolons_to_periods(text)


@pytest.mark.parametrize(
    "text,index,expected",
    [
        ("abc (def) ghi", 11, False),
        ("abc (def) ghi", 6, True),
        ("abc [def] ghi", 6, True),
        ("abc def ghi", 5, False),
        ("a ) b ( c", 8, True),
    ],
)
def test_the_depth_counter_itself(text: str, index: int, expected: bool) -> None:
    assert _inside_brackets(text, index) is expected


def test_the_prose_still_changes() -> None:
    """End to end: the bracket is protected, the sentence around it is not."""
    doc = BRACKETED[0] + " " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert final != doc
    assert "Moreover, it is important to note" not in final


# --- the same island, the other two splitters -------------------------------------------------
#
# The semicolon guard alone did not cover this. MEASURED over 40 HC3 halves containing a bracket,
# counted AGAINST THE SOURCE rather than against nothing — HC3 prose already contains 1 bracketed
# sentence break and 2 unbalanced brackets of its own, which an uncontrolled count reports as damage:
#
#     NEW sentence break inside a bracket   2   ->  0
#     NEW unbalanced bracket                0   ->  0
#
# Both were COMMAS, not semicolons:
#
#     (BSE, also known as "mad cow disease")        ->  (BSE. Also known as "mad cow disease")
#     (... Java Applets, but they're hardly used)   ->  (... Java Applets. They're hardly used)


@pytest.mark.parametrize(
    "sentence",
    [
        'The disease (BSE, also known as "mad cow disease" in the press) was traced to feed that '
        "had been rendered from infected carcasses over several years.",
        "Another such plugin is Java (which displays applets, but they are hardly in use anymore "
        "on the modern web) and it is usually disabled by default now.",
    ],
    ids=["appositive", "contrastive"],
)
def test_the_long_splitter_does_not_split_inside_a_bracket(sentence: str) -> None:
    """`_split_one` picks the comma nearest the midpoint, and a comma inside a parenthesis is the
    commonest comma there is. It already refused to split inside a QUOTATION for this exact reason —
    the sentence continues after the close — and a bracket is the same island."""
    parts = _split_one(sentence)
    for part in parts or []:
        assert not SPLIT_IN_BRACKET.search(part), part
        assert part.count("(") == part.count(")"), part


def test_a_closed_bracket_does_not_block_a_later_split() -> None:
    """The guard is about being INSIDE a bracket, not about the sentence containing one. MEASURED
    over 1177 long corpus sentences: 45.3% of bracket-free sentences split, and 36.1% of bracketed
    ones still do — targeted, not blanket."""
    sentence = (
        "The council (chaired by the deputy) approved the plan for the new depot last night, but "
        "the budget for the second phase was left undecided until the spring review meeting."
    )
    parts = _split_one(sentence)
    assert parts and len(parts) == 2, parts
    assert "(chaired by the deputy)" in parts[0]


@pytest.mark.parametrize(
    "words,index,expected",
    [
        (["a", "(b,", "c)", "d"], 2, True),
        (["a", "(b,", "c)", "d"], 3, False),
        (["a", "b,", "c"], 2, False),
    ],
)
def test_the_word_level_counter(words: list[str], index: int, expected: bool) -> None:
    assert _split_lands_inside_brackets(words, index) is expected
