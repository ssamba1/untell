"""Wrapping AI prose in markdown clears it on the stdlib path, with the prose untouched.

Found while checking that a structured document survives a rewrite. It does — headings, list
items, fenced code, tables and blockquotes all came back intact — but the loop had not rewritten
anything, because the document scored 0.2339 against a 0.30 threshold. The same prose flat scored
0.5331.

MEASURED over 10 HC3 documents, wrapping each in a heading, three list items and a fenced code
block and changing nothing else:

    scoring             mean max   flagged at 0.30   cleared at the 0.45 verdict cut
    flat                  0.5747        10/10                    —
    wrapped               0.3101         6/10                   9 of 9
    prose blocks only     0.4624        10/10                    —

Two thresholds are in play and they answer different questions: 0.30 is the loop's target, 0.45 is
the stdlib verdict cut. Both are quoted because the effect crosses both.

The full tier is untouched — 6 of 6 documents stayed at exactly 1.0000 wrapped — so this belongs
to the stdlib heuristic, which is the path a clean install runs. The last row names the cause:
`score_text` scores the raw document while `sentences.py` already splits with `layout.blocks()`
first, because scaffolding is not prose.

These tests pin the CURRENT behaviour, including the gap. Fixing it by block-scoring would move
every stdlib figure in the repository — the 64%/30% false-positive pair, the per-corpus table, and
the perplexity midpoints fitted against raw-document distributions — so it needs its own
measurement pass. A test that quietly encoded the desired behaviour instead would make that pass
harder, not easier.
"""
from __future__ import annotations

import pytest

from untell.layout import blocks
from untell.scripts.score import score_text

PROSE = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. It "
    "significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "Furthermore, organizations increasingly adopt these transformative technologies to optimize "
    "operational workflows across numerous sectors. In conclusion, these findings underscore the "
    "importance of a comprehensive approach here."
)

WRAPPED = (
    "# Overview\n\n"
    f"{PROSE}\n\n"
    "## Details\n\n"
    "- The first supporting point is listed here.\n"
    "- The second supporting point is listed here.\n"
    "- The third supporting point is listed here.\n\n"
    "```python\ndef parse(row):\n    return row.strip().split(\",\")\n```\n"
)


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    """The path this belongs to. On the model path the effect does not exist."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_the_flat_prose_is_flagged():
    """The premise. Without this the comparison below measures nothing."""
    assert score_text(PROSE, tier="lite")["max"] >= 0.30


def test_scaffolding_lowers_the_score_without_touching_the_prose():
    flat = score_text(PROSE, tier="lite")["max"]
    wrapped = score_text(WRAPPED, tier="lite")["max"]

    assert PROSE in WRAPPED, "the prose must be byte-identical, or this measures a rewrite"
    assert wrapped < flat, (
        f"structure-only change moved the score {flat:.4f} -> {wrapped:.4f}; if that stopped "
        "being true the docstring's table is stale"
    )


def test_the_prose_blocks_score_higher_than_the_whole_document():
    """The cause, and the shape of the fix: scaffolding dilutes, prose does not."""
    scaffold_start = ("#", "-", "|", "```", ">")
    prose_blocks = "\n\n".join(
        b for b in blocks(WRAPPED) if not b.lstrip().startswith(scaffold_start)
    )
    assert prose_blocks.strip(), "the block split kept no prose, so this proves nothing"

    assert score_text(prose_blocks, tier="lite")["max"] > score_text(WRAPPED, tier="lite")["max"]


def test_the_structure_itself_survives_a_rewrite():
    """The question this started as, kept because the answer is good and nothing pinned it."""
    from untell.scripts.run import untell_text

    result = untell_text(WRAPPED, tier="lite", threshold=0.0, max_iters=1,
                         rewriter="composite", seed=4)
    out = result["final"]

    assert out.count("```") == WRAPPED.count("```"), "fenced code block lost"
    assert 'return row.strip().split(",")' in out, "code body was rewritten"
    assert out.count("\n- ") == WRAPPED.count("\n- "), "list items lost"
    assert "# Overview" in out and "## Details" in out, "headings lost"
