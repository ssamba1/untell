"""Stripping a cliché from a marked line left the tell the repair exists to prevent.

FOUND by reading rewriter output on line-structured input rather than counting its lines. The line
counts were perfect — 3 -> 3, speaker labels and clause numbers all intact — and the text said:

    Alice: organizations must tap these smooth solutions.
    1.3 any defect shall be notified without delay.

`_flatten_cliches` deletes "In conclusion, " and then restores the capital it displaced. Its restore
pattern finds a sentence start at the beginning of the STRING or after a terminator, and a line
opening with a marker is neither, so the restore never fired.

MEASURED, one cliché stripped from the head of each line, through shipped `structural_rewrite`:

    speaker label   Alice: In conclusion, ...   ->  "Alice: organizations must adopt ..."
    dotted clause   1.3 In conclusion, ...      ->  "1.3 any defect shall be notified ..."
    bullet          - In conclusion, ...        ->  "- the team must use a sturdy approach"
    blockquote      > In conclusion, ...        ->  "> the team must use a solid approach"
    heading         ## In conclusion, ...       ->  "## the team must tap into a solid approach"
    paren clause    (a) In conclusion, ...      ->  "(a) the team must tap into a solid approach"

**6 of 7 marker kinds, not the 2 the output showed.** Only "1. " survived, and by accident rather
than by design: its dot reads as a sentence terminator to the existing pattern.

**The obvious fix is wrong, which is why the rule is narrower.** Widening the restore to every line
start breaks soft-wrapped prose, whose continuation lines legitimately begin mid-sentence in lower
case. Widening it to every MARKED line start is still wrong: plenty of marked lines are deliberately
lower case — "(a) the Seller shall deliver ..." is how legal sub-clauses are drafted, and list items
are routinely fragments. Either version would damage text that was never touched.

So the rule restores a capital that was there and never invents one: a line is corrected only when
the transform changed it AND the word it now begins with was capitalised before. The must-not-touch
half of this file is the half that decided the design.
"""

from __future__ import annotations

import logging
import random

import pytest

from untell.rewriter.structural import (
    _first_word_after_marker,
    _flatten_cliches,
    _restore_marker_capitals,
    structural_rewrite,
)

MARKED = {
    "speaker label": "Alice: In conclusion, organizations must adopt these robust solutions today.",
    "dotted clause": "1.3 In conclusion, any defect shall be notified to the vendor without delay.",
    "bullet": "- In conclusion, the team must leverage a robust approach to delivery.",
    "numbered list": "1. In conclusion, the team must leverage a robust approach to delivery.",
    "blockquote": "> In conclusion, the team must leverage a robust approach to delivery.",
    "heading": "## In conclusion, the team must leverage a robust approach to delivery.",
    "paren clause": "(a) In conclusion, the team must leverage a robust approach to delivery.",
}

# Lower case because that is how the author wrote it, with no deletion in front of it.
DELIBERATE = {
    "legal sub-clause": "(a) the Seller shall deliver the goods to the named place without delay.",
    "list fragments": "- apples\n- bananas\n- cherries",
    "continued quote": "> the quotation continues in lower case from the previous line of it.",
    "unnumbered clause": "1.3 any defect shall be notified to the vendor within thirty days.",
    "labelled note": "Note: see the appendix for the full derivation of the constant used above.",
}

SEEDS = (1, 7, 13)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _rewrites(source: str) -> set[str]:
    out = set()
    for seed in SEEDS:
        random.seed(seed)
        candidate = structural_rewrite(source)
        if candidate != source:
            out.add(candidate)
    return out


@pytest.mark.parametrize("marker", sorted(MARKED))
def test_the_cliche_is_actually_stripped(marker: str) -> None:
    """Premise. A line the transform declined to touch cannot show a missing capital, and would
    satisfy the assertion below without the repair existing at all."""
    assert _rewrites(MARKED[marker]), "nothing was rewritten; the capital check means nothing here"


@pytest.mark.parametrize("marker", sorted(MARKED))
def test_a_marked_line_keeps_its_capital(marker: str) -> None:
    """The defect: 6 of these 7 shipped a lower-case sentence start."""
    for out in _rewrites(MARKED[marker]):
        _, word = _first_word_after_marker(out)
        assert word[:1].isupper(), out


@pytest.mark.parametrize("case", sorted(DELIBERATE))
def test_a_deliberate_lower_case_line_is_left_alone(case: str) -> None:
    """Guards the guard, and it is the assertion that shaped the rule. Nothing was deleted from
    these lines, so there is no displaced capital to restore — inventing one edits the author."""
    assert _flatten_cliches(DELIBERATE[case]) == DELIBERATE[case]


def test_a_soft_wrapped_continuation_stays_lower_case() -> None:
    """The reason the repair is not simply run in multiline mode. A wrapped paragraph continues
    mid-sentence, and capitalising there is a worse tell than the cliché that was removed."""
    wrapped = "In conclusion, the team reviewed the plan and then\nchecked the results today."
    assert "\nchecked" in _flatten_cliches(wrapped)


def test_the_capital_must_have_existed_before() -> None:
    """Stated directly rather than only through the corpus of cases above: the rule restores, it
    does not invent. Same line, same marker, same edit — only the source capital differs."""
    assert _restore_marker_capitals("- In summary, the plan", "- the plan") == "- The plan"
    assert _restore_marker_capitals("- in summary, the plan", "- the plan") == "- the plan"


def test_an_untouched_line_is_never_corrected() -> None:
    """The change gate. Equal lines are skipped whatever their case, so the repair can only ever
    act on text this transform itself rewrote."""
    assert _restore_marker_capitals("- the plan", "- the plan") == "- the plan"


def test_a_line_count_change_falls_back_to_the_uncorrected_text() -> None:
    """Alignment is positional. If some future transform moves a line boundary, the pairing is a
    guess, and a wrong guess would capitalise an unrelated line."""
    assert _restore_marker_capitals("- In summary, a\n- In summary, b", "- a") == "- a"


def test_a_non_prose_token_is_still_not_capitalised() -> None:
    """The existing `_NOT_A_PROSE_WORD` guard has to survive the new path: an identifier is lower
    case because that is its spelling, and broken capitalisation is itself a catalogued tell."""
    assert _restore_marker_capitals("- In summary, untell.score", "- untell.score") == (
        "- untell.score"
    )


def test_line_structure_is_preserved() -> None:
    """The repair rewrites lines in place. A dropped or added newline would silently reflow a
    transcript or a numbered contract."""
    source = "\n".join(MARKED[k] for k in ("speaker label", "dotted clause", "bullet"))
    for out in _rewrites(source):
        assert len(out.split("\n")) == len(source.split("\n"))
