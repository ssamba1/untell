"""A 406-word document came back untouched with 41 tells, and nothing said the loop had tried.

FOUND by asking what the tool does on the input it is actually for. Every measurement in this log
uses corpus texts of about 120 words; the flagship use case is an essay. Run at four lengths,
`tier=lite`, `structural`, `best_of=1`, seed fixed:

    words   secs    pre      post     delta     tells      changed
      207  20.81  0.6239   0.6239   +0.0000   23 -> 23     False
      406   2.61  0.5987   0.5987   +0.0000   41 -> 41     False
      697   8.08  0.5335   0.4713   -0.0622   60 -> 49     True
     1136  20.53  0.4847   0.4351   -0.0496   98 -> 85     True

The 406-word row is the one worth chasing. `rewrites=2, adopted=0`: candidates were drawn and both
rejected. Scoring the candidate directly says why, and the loop is not at fault:

    tells          41 -> 34        the draft is better by this tool's own catalogue
    detector max   0.5987 -> 0.6203   worse, so correctly not adopted
    meaning gate   passed

The loop optimises the detector score, so discarding a draft that raises it is right. What was
missing is any account of it. `changed: false` alone reads as "the tool did nothing", which is
indistinguishable from "the tool tried and every draft was worse" — different situations with
different remedies, and the two fields that separate them, `rewrites` and `adopted`, are the ones
nobody reads.

(The 207-word row's 20.81s is first-call warm-up, not length — see Result 183.)
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import _nothing_adopted_warning, untell_text

MARK = "adopted none"
CLEAN = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_it_fires_when_drafts_were_drawn_and_all_refused() -> None:
    note = _nothing_adopted_warning(2, 0, False)
    assert note and "2 candidates" in note


def test_a_gate_veto_is_not_reported_as_a_worse_score() -> None:
    """The first version of this note said "every draft scored worse" unconditionally, and that is
    false whenever the meaning gate refused them: the gate `continue`s BEFORE scoring, so a vetoed
    draft is never compared on score at all. Two causes, two remedies — more draws of a rewriter
    that keeps changing the meaning is not the answer."""
    note = _nothing_adopted_warning(3, 0, False, 3) or ""
    assert "meaning gate refused every one" in note
    assert "None of them was scored" in note
    assert "scored worse" not in note


def test_a_mixed_run_reports_both_causes() -> None:
    note = _nothing_adopted_warning(3, 0, False, 1) or ""
    assert "1 changed the meaning" in note and "2 scored worse" in note


def test_a_gate_veto_points_somewhere_different() -> None:
    """The remedies have to diverge, or naming the cause was decoration. A score refusal suggests
    more draws; a gate refusal suggests another rewriter."""
    gate = _nothing_adopted_warning(3, 0, False, 3) or ""
    score = _nothing_adopted_warning(3, 0, False, 0) or ""
    assert "different --rewriter" in gate and "--best-of" not in gate
    assert "--best-of" in score


def test_it_says_nothing_when_a_draft_was_taken() -> None:
    assert _nothing_adopted_warning(2, 1, True) is None


def test_it_says_nothing_when_no_draft_was_drawn() -> None:
    """A run that never reached the rewriter has a different story, and this note would misdescribe
    it as "every draft was worse" when there were no drafts."""
    assert _nothing_adopted_warning(0, 0, False) is None


def test_it_says_nothing_when_the_text_changed() -> None:
    """Guards the arithmetic rather than the intent: a changed text cannot have adopted nothing, and
    if those ever disagree the note must defer to the visible outcome."""
    assert _nothing_adopted_warning(3, 0, True) is None


def test_the_note_does_not_read_as_a_malfunction() -> None:
    """The loop refusing a worse draft is the guard working. A caveat that sounds like a crash
    invites the reader to file a bug against correct behaviour."""
    note = _nothing_adopted_warning(2, 0, False) or ""
    assert "not a failure to run" in note
    for alarm in ("error", "crash", "broken", "failed to"):
        assert alarm not in note.lower()


def test_the_note_is_actionable() -> None:
    """Three remedies, all real: more draws, a different rewriter, or a tier where the score has
    more to respond to. A caveat with no next step is decoration."""
    note = _nothing_adopted_warning(2, 0, False) or ""
    assert "--best-of" in note and "--rewriter" in note and "--tier full" in note


def test_the_singular_reads_properly() -> None:
    assert "1 candidate and" in (_nothing_adopted_warning(1, 0, False) or "")


def test_it_reaches_a_real_run(monkeypatch) -> None:
    """Wired, not merely defined. The rewriter is stubbed to return the input so the loop draws and
    adopts nothing deterministically — the corpus document that produced this finding is 406 words
    and slow, and its behaviour is a property of that text rather than of the code under test."""
    import untell.rewriter.structural as structural

    monkeypatch.setattr(structural, "structural_rewrite", lambda text, *a, **k: text)
    result = untell_text(
        CLEAN, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1, seed=1
    )
    if result.get("rewrites") and not result.get("adopted"):
        assert MARK in (result.get("warning") or "")
    else:  # the loop declined to draw at all; a different state, covered above
        pytest.skip(f"no draw to refuse: rewrites={result.get('rewrites')}")
