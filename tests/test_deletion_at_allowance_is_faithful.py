"""Deletion at EXACTLY the allowance is faithful, not rejected.

entailment.py:500: `words_lost(source, candidate) > deletion_allowance(source)`.
The allowance is 10 + 10% of words, so with a 120-word source it is exactly
12.0; a candidate dropping exactly 12 words hits the boundary. The mutation
> -> >= rejects it, vetoing a faithful rewrite whose deletion equals the
measured allowance. Prior 'fractional allowance makes equality unreachable'
note was wrong: 0.1*n is an exact integer whenever n is a multiple of 10.
"""
from unittest.mock import patch

from untell.scripts.entailment import (
    deletion_allowance,
    meaning_preserved,
    words_lost,
)

SRC = " ".join(f"w{i}" for i in range(120))
CAND = " ".join(f"w{i}" for i in range(108))  # drops exactly 12 words


def test_boundary_is_exact():
    assert deletion_allowance(SRC) == 12.0
    assert words_lost(SRC, CAND) == 12


def test_deletion_at_allowance_passes_the_gate():
    # Deterministic: polarity kept (patched at the source module where the
    # function imports it), stdlib path (available -> False), sim well above
    # the strict bar. The ONLY thing that can reject the pair is the deletion
    # gate, so a False return means the >= mutation fired.
    with patch("untell.scripts.hedges.polarity_kept", return_value=True), \
         patch("untell.scripts.entailment.available", return_value=False):
        assert meaning_preserved(SRC, CAND, sim=0.99, strict_sim_bar=0.5) is True


def test_deletion_beyond_allowance_is_rejected():
    beyond = " ".join(f"w{i}" for i in range(100))  # drops 20 words > 12.0
    with patch("untell.scripts.hedges.polarity_kept", return_value=True), \
         patch("untell.scripts.entailment.available", return_value=False):
        assert meaning_preserved(SRC, beyond, sim=0.99, strict_sim_bar=0.5) is False
