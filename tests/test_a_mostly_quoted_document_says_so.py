"""Ninety percent of a witness statement was locked, and the verdict said nothing about it.

FOUND by continuing the previous question — which input types has "can this tool actually answer?"
never been asked of? Code was one. Quotation is the other, and it reaches the same place by a
different mechanism: there the rewriter had no prose lines, here it has prose it is forbidden to
alter.

MEASURED at `tier=lite` on a two-quotation witness statement:

    locked 321/357 characters (90%), 2 spans
    flagged: True    changed: False    stopped: max_iters

The loop ran every iteration and adopted nothing — only a tenth of the document was editable — and
the result carried no hint of that. It is arguably worse than the code case, because the detectors
scored the quotations too: **the number describes somebody else's words.**

MEASURED over 120 corpus texts (HC3 and RAID, both halves), locked character share:

    median 0.023    p90 0.072    p99 0.137    max 0.177

against 0.899 for the probe. Nothing in the corpus passes 0.30, so the 0.50 bar sits in a wide empty
gap and means exactly what it says.

"Preserved material" rather than "quotations", because `lock` also holds citations, figures, dates
and URLs — a note naming only quotes would misdescribe a statistics-dense paragraph.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import _LOCKED_SHARE_BAR, _mostly_locked_warning, score_text

QUOTE_HEAVY = (
    'The witness stated: "I arrived at the building shortly before nine in the morning and '
    'noticed that the main door had been left open, which struck me as unusual given the hour." '
    'She continued: "There was nobody at the desk, and the lights on the upper floor were still '
    'off when I walked past the stairwell on my way to the office at the end of the corridor."'
)
PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead."
)
ONE_SHORT_QUOTE = (
    'Councils spread salt on roads in winter because it lowers the freezing point of water, and '
    'one engineer called it "the cheapest tool we have" during a review of the winter programme '
    'that ran across several counties and reported back in the spring of the following year.'
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_a_mostly_quoted_document_is_flagged_as_mostly_unrewritable() -> None:
    assert _mostly_locked_warning(QUOTE_HEAVY)


def test_ordinary_prose_says_nothing() -> None:
    """Guards the guard, and 0 of 120 corpus texts exceed 0.30 locked share."""
    assert _mostly_locked_warning(PROSE) is None


def test_a_single_quotation_is_not_enough() -> None:
    """The common case — a paragraph with one quote in it — must stay silent, or the note fires on
    every piece of journalism ever written."""
    assert _mostly_locked_warning(ONE_SHORT_QUOTE) is None


def test_the_bar_sits_between_the_two_measured_populations() -> None:
    """Corpus max 0.177, probe 0.899. A bar outside that gap either stops catching quote-heavy
    input or starts firing on ordinary prose."""
    assert 0.177 < _LOCKED_SHARE_BAR < 0.899


def test_it_reaches_a_real_score_result(stdlib_lite) -> None:
    """Wired, not merely defined.

    Pinned to the stdlib lite path (see test_a_document_with_no_prose_says_so): the
    assertion is about warning content, which the pure-Python path answers without
    loading GPT-2.
    """
    assert "preserved material" in (score_text(QUOTE_HEAVY, tier="lite").get("warning") or "")
    assert "preserved material" not in (score_text(PROSE, tier="lite").get("warning") or "")


def test_the_note_does_not_excuse_the_text() -> None:
    """It has to survive a reader whose quotations are themselves machine-written. The claim is
    about what the verdict covers, not about whether the text is innocent."""
    from untell.scripts.score import _MOSTLY_LOCKED_NOTE

    assert "cannot change" in _MOSTLY_LOCKED_NOTE
    for overclaim in ("is human", "not ai", "disregard"):
        assert overclaim not in _MOSTLY_LOCKED_NOTE.lower()


def test_a_broken_preserve_layer_does_not_break_scoring(monkeypatch) -> None:
    import untell.scripts.preserve as preserve

    def _boom(_text):
        raise RuntimeError("preserve is unavailable")

    monkeypatch.setattr(preserve, "lock", _boom)
    assert _mostly_locked_warning(QUOTE_HEAVY) is None
    assert score_text(PROSE, tier="lite").get("max") is not None
