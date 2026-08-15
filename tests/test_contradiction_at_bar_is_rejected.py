"""Contradiction at EXACTLY the bar must fail the meaning gate.

entailment.py:511: `not (sim >= relaxed_sim_bar and con < contradiction_bar and
ent >= entailment_floor)` — a contradiction score equal to the 0.5 bar is a
contradiction, not a pass. The mutation < -> <= flips a score of exactly 0.5
into a pass. Prior 'exact 0.5 bar is a model artifact boundary, unreachable'
note was wrong — contradiction_score is a call, pinable by monkeypatch.
"""
from unittest.mock import patch

from untell.scripts.entailment import meaning_preserved

SRC = "some source words here"
CAND = "some candidate here"


def test_contradiction_at_bar_is_rejected():
    with patch("untell.scripts.hedges.polarity_kept", return_value=True), \
         patch("untell.scripts.entailment.available", return_value=True), \
         patch("untell.scripts.entailment.contradiction_score", return_value=0.5), \
         patch("untell.scripts.entailment.entailment_score", return_value=0.9), \
         patch("untell.scripts.roles.role_swap", return_value=None):
        assert meaning_preserved(SRC, CAND, sim=0.99, strict_sim_bar=0.5) is False


def test_contradiction_just_below_bar_passes():
    with patch("untell.scripts.hedges.polarity_kept", return_value=True), \
         patch("untell.scripts.entailment.available", return_value=True), \
         patch("untell.scripts.entailment.contradiction_score", return_value=0.49), \
         patch("untell.scripts.entailment.entailment_score", return_value=0.9), \
         patch("untell.scripts.roles.role_swap", return_value=None):
        assert meaning_preserved(SRC, CAND, sim=0.99, strict_sim_bar=0.5) is True
