"""The same text, laid out one sentence per line, got 2.7x less out of the loop and no warning.

FOUND by asking what else the per-block scope costs, after two fixes in that family. Merge, split,
restatement-drop and burstiness targeting all need a PAIR of adjacent sentences, and a paragraph of
one has none. That gating is CORRECT — merging across a paragraph boundary would weld two paragraphs
together and destroy a transcript, a bullet list or a changelog — so there is nothing to fix in the
rewriter. What was missing is that nobody told the user.

MEASURED on 8 HC3 documents at `tier=lite`, `structural`, `max_iters=2`, seed fixed, the only
difference being the layout:

    as written              0.5501 -> 0.5097   (-0.0404)    flagged 6/8    changed 4/8
    one sentence per para   0.5501 -> 0.5349   (-0.0152)    flagged 7/8    changed 4/8

The `pre` scores are identical to four decimals, because detectors do not read paragraph breaks. The
entire difference is what the rewriter was able to do — **2.7x less improvement** — and one document
crossed back over the verdict threshold on the strength of the layout alone: 0.434 and clear as
written, 0.539 and flagged when split.

Sentence-length variance says the same thing. Document CV against a measured human 0.484:

    as written        0.304 -> 0.343
    3 sentences/para  0.306 -> 0.374
    1 sentence/para   0.328 -> 0.319      <- moves AWAY from human

MEASURED over 120 corpus texts (HC3 and RAID, both halves), share of prose blocks holding exactly one
sentence: median 0.000, p90 0.500, p99 0.667, max 0.667. Over the 61 texts with three or more prose
blocks the max is the same 0.667, and **0** exceed 0.80, while six real documents re-laid out one
sentence per line score 1.00 across 7 to 10 blocks. The bar sits in that gap.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import (
    _LONE_BLOCK_SHARE_BAR,
    _MIN_BLOCKS_FOR_LONE_NOTE,
    _line_per_sentence_warning,
    score_text,
)

PARAGRAPHS = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead.\n\n"
    "The grit itself does a second job. It gives tyres something to bite on once the ice has gone "
    "soft, which matters more on a hill than on the flat."
)
PER_LINE = (
    "Salt lowers the freezing point of water, which is why councils spread it in winter.\n\n"
    "It works down to about minus nine degrees, below which other chemicals are needed.\n\n"
    "The grit itself does a second job on the surface of the road once it is down.\n\n"
    "It gives tyres something to bite on once the ice has gone soft near the kerb.\n\n"
    "That matters more on a hill than it ever does on the flat part of the route."
)
TWO_BLOCKS = "One sentence here about the weather.\n\nAnother sentence here about the road."


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_document_laid_out_per_sentence_is_flagged_as_limited() -> None:
    assert _line_per_sentence_warning(PER_LINE)


def test_ordinary_paragraphs_say_nothing() -> None:
    """Guards the guard. 0 of 120 corpus texts exceed the bar, so this must not fire on prose."""
    assert _line_per_sentence_warning(PARAGRAPHS) is None


def test_a_short_document_is_left_to_the_short_text_note() -> None:
    """A two-block document is 1.00 by arithmetic as soon as both blocks are one sentence, and
    saying "your layout limited the rewrite" about four lines of text is noise. `_short_text_warning`
    is the note that applies there."""
    assert _line_per_sentence_warning(TWO_BLOCKS) is None
    assert _line_per_sentence_warning("Just the one sentence.") is None


def test_the_bar_sits_between_the_two_measured_populations() -> None:
    """Corpus max 0.667 over texts with three or more blocks, probe 1.00. A bar outside that gap
    either stops catching per-line input or starts firing on ordinary writing."""
    assert 0.667 < _LONE_BLOCK_SHARE_BAR < 1.0
    assert _MIN_BLOCKS_FOR_LONE_NOTE >= 3


def test_it_reaches_a_real_score_result() -> None:
    """Wired, not merely defined — the defect this log has hit most often is a function that works
    and is never called."""
    assert "one sentence per paragraph" in (score_text(PER_LINE, tier="lite").get("warning") or "")
    assert "one sentence per paragraph" not in (
        score_text(PARAGRAPHS, tier="lite").get("warning") or ""
    )


def test_the_note_does_not_disown_the_score() -> None:
    """It says the rewriter reached less, not that the verdict is wrong. The measurement behind it
    is about improvement delivered, and the `pre` scores were identical in both layouts."""
    from untell.scripts.score import _LINE_PER_SENTENCE_NOTE

    assert "The score is real" in _LINE_PER_SENTENCE_NOTE
    for overclaim in ("is human", "not ai", "ignore", "disregard"):
        assert overclaim not in _LINE_PER_SENTENCE_NOTE.lower()


def test_the_note_names_what_could_not_run() -> None:
    """A caveat the reader cannot act on is decoration. This one names the transforms and implies
    the remedy — the same words in ordinary paragraphs."""
    from untell.scripts.score import _LINE_PER_SENTENCE_NOTE

    assert "two adjacent sentences" in _LINE_PER_SENTENCE_NOTE
    assert "paragraphs" in _LINE_PER_SENTENCE_NOTE


def test_a_broken_layout_module_does_not_break_scoring(monkeypatch) -> None:
    """A caveat must never break the score it qualifies."""
    import untell.layout as layout

    def _boom(*_args, **_kwargs):
        raise RuntimeError("layout is unavailable")

    monkeypatch.setattr(layout, "apply_per_block", _boom)
    assert _line_per_sentence_warning(PER_LINE) is None
    assert score_text(PARAGRAPHS, tier="lite").get("max") is not None
