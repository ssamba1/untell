"""A markdown table row is structure and data. It was being rewritten as a paragraph.

A table row carries no line marker — no bullet, no `>`, no `#` — so `_segments` gathered it into the
surrounding block and handed it to the transform. MEASURED on a document ending in a results table,
at every seed tried:

    | Method | Score |   ->   | Way | Score |  /  | Approach | Score |  /  | Technique | Score |

A column heading is a label the surrounding text refers to, and often a term of art. Nothing
downstream can restore it, and the meaning gates cannot see it: no claim changed, a noun did.

The cells are worse in principle than the heading. Several rows gathered into one block are one
paragraph to a sentence-level transform, which is then free to merge or split across the pipes — the
difference between a relabelled table and a destroyed one.
"""

from __future__ import annotations

import random

import pytest

from untell.layout import apply_per_block
from untell.rewriter import get_rewriter
from untell.scripts.score import score_text

TABLE = """| Method | Score |
|---|---|
| Baseline | 0.42 |
| Ours | 0.91 |"""

DOC = f"""Moreover, the framework leverages robust methodologies to deliver outcomes at scale.

{TABLE}

In conclusion, these findings underscore the importance of a comprehensive approach.
"""


def test_no_table_line_reaches_the_transform() -> None:
    seen: list[str] = []
    apply_per_block(DOC, lambda block: (seen.append(block), block)[1])
    assert seen, "no prose reached the transform at all"
    for block in seen:
        assert "|" not in block, f"a table line was handed over as prose: {block!r}"


def test_the_prose_around_it_still_transforms() -> None:
    """Guards the guard. Excluding the table must not exclude the paragraphs beside it — the
    document is mostly prose and that is the whole job."""
    out = apply_per_block(DOC, lambda block: block.upper())
    assert "MOREOVER" in out and "IN CONCLUSION" in out
    assert "| Method | Score |" in out, "the table was altered"


def test_layout_round_trips_exactly() -> None:
    assert apply_per_block(DOC, lambda block: block) == DOC


@pytest.mark.parametrize("seed", range(6))
def test_the_loop_leaves_the_header_alone(seed: int) -> None:
    """End to end through the real rewriter, which is where this was found. A layout-only test
    would have passed before the fix too — `_segments` was never asked about tables."""
    rewriter = get_rewriter("composite")
    random.seed(seed)
    out = rewriter.rewrite(DOC, score_text(DOC, tier="lite"), 0.3)
    assert "| Method | Score |" in out, out
    assert "| Baseline | 0.42 |" in out
    assert "| Ours | 0.91 |" in out


@pytest.mark.parametrize(
    "line",
    ["| a | b |", "  | indented | row |", "|---|---|", "| :--- | ---: |"],
    ids=lambda s: s.strip()[:14],
)
def test_every_table_line_shape_is_layout(line: str) -> None:
    """Delimiter rows and alignment rows are table lines too, and an indented table is still a
    table."""
    doc = f"Prose before.\n\n{line}\n\nProse after."
    seen: list[str] = []
    apply_per_block(doc, lambda block: (seen.append(block), block)[1])
    assert all("|" not in b for b in seen), seen


def test_a_pipe_inside_prose_is_still_prose() -> None:
    """The rule is the LEADING pipe. A sentence that merely contains one — a shell pipeline, a
    regex alternation — must still be rewritten, or the guard would silently exempt prose."""
    doc = "Run the command foo | bar and then check the output carefully."
    seen: list[str] = []
    apply_per_block(doc, lambda block: (seen.append(block), block)[1])
    assert seen == [doc], seen
