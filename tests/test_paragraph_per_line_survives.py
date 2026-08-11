"""One paragraph per line is a layout, not a soft wrap.

`apply_per_block` gathers consecutive plain lines so a soft-wrapped paragraph is transformed with
its whole self in view. For text that puts one paragraph per line — how chat models and forum
answers are usually pasted — that assumption deleted the paragraph breaks: the lines were joined
into one block, rejoined with " ", and the separators never came back.

MEASURED end to end on HC3 answers: 3 of 4 documents returned as a single paragraph (3 -> 1,
3 -> 1, 4 -> 1), while the module's docstring promised "preserving all layout". Nothing downstream
objects — the meaning gate compares meaning, the detectors score statistics, neither looks at
layout.
"""

from __future__ import annotations

import pytest

from untell.layout import apply_per_block, blocks

PARAGRAPH_PER_LINE = (
    "Salt melts ice on roads.\n"
    "It lowers the freezing point of water.\n"
    "Communities use it every winter."
)

# A real soft wrap breaks mid-clause, so no line ends on a sentence terminator.
SOFT_WRAPPED = (
    "The committee reviewed the proposal and found it broadly acceptable, though\n"
    "several members raised concerns about the timeline and the budget, which\n"
    "the chair agreed to revisit at the next meeting."
)


def test_paragraph_breaks_survive_a_transform_that_rejoins():
    """`" ".join` on the block is exactly what the rewriter does at the end of its pipeline."""
    out = apply_per_block(PARAGRAPH_PER_LINE, lambda b: " ".join(b.split()))
    assert out.count("\n") == PARAGRAPH_PER_LINE.count("\n")


def test_each_paragraph_is_its_own_unit():
    assert len(blocks(PARAGRAPH_PER_LINE)) == 3


def test_a_soft_wrapped_paragraph_is_still_gathered():
    """The behaviour this must not break: sentence-level work needs more than one sentence."""
    assert len(blocks(SOFT_WRAPPED)) == 1


def test_a_list_item_ending_in_a_full_stop_keeps_its_marker():
    """The bug the first version of this fix introduced.

    A list item ends in a full stop as often as a paragraph does. Testing the sentence terminator
    before the marker branch swallowed "- Furthermore, it is robust." into the prose buffer with
    its bullet attached, so `blocks()` and `apply_per_block` disagreed about the same document.
    """
    doc = "Intro line.\n- Furthermore, it is robust.\n- It also scales."
    seen: list[str] = []
    apply_per_block(doc, lambda b: seen.append(b) or b)
    assert "- Furthermore, it is robust." not in seen
    assert "Furthermore, it is robust." in seen


def test_the_document_round_trips_unchanged_under_identity():
    for src in (PARAGRAPH_PER_LINE, SOFT_WRAPPED, "one line only", "a.\n\nb.", ""):
        assert apply_per_block(src, lambda b: b) == src


def test_a_terminator_followed_by_a_closer_still_ends_the_line():
    doc = 'She said "it works."\nThen the meeting ended.'
    assert len(blocks(doc)) == 2


@pytest.mark.parametrize(
    "rewriter_name", ["structural", "surgical", "composite"]
)
def test_a_real_rewrite_keeps_the_paragraph_count(rewriter_name: str):
    from untell.rewriter import get_rewriter

    score = {"tier": "full", "max": 1.0, "detectors": {}}
    out = get_rewriter(rewriter_name).rewrite(PARAGRAPH_PER_LINE, score, 0.30)
    assert out.count("\n") == PARAGRAPH_PER_LINE.count("\n"), out
