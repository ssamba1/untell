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

from untell.rewriter.structural import _inside_brackets, _semicolons_to_periods
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
