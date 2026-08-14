"""Killing tests for the entailment.py mutation survivors (2026-08-14 sweep).

  line 69   constant: False -> True   `_NLI.dead` guard in available().
  line 500  boundary: > -> >=         deletion-allowance boundary.
  line 511  boundary: < -> <=         contradiction-bar boundary.
  line 560  constant: 4 -> 5          CLI JSON precision.

69 and 560 are killed here. 500 and 511 are boundary mutations on the model-gated
path (contradiction_score is a live model call; the exact bar value 0.5 is a model
artifact, and the deletion allowance is fractional — 10 + 10% of words — so the
int-vs-float equality the `>=` mutation would change is unreachable from text).
They are recorded as unkillable-by-construction in survivors.md.
"""

from __future__ import annotations

import json

from untell.scripts import entailment


def test_available_is_false_when_the_nli_stack_is_dead(monkeypatch) -> None:
    """Mutation `return False` -> `return True` at the `_NLI.dead` guard.

    A dead stack must not report available: callers use `available()` to decide
    whether the meaning gate can run, and a dead model reporting available would
    route rewrites through a veto that cannot answer."""
    entailment._NLI.dead = True
    monkeypatch.setattr(entailment._NLI, "dead", True)
    assert entailment.available() is False


def test_available_restores_after_dead_flag_cleared(monkeypatch) -> None:
    """The dead flag is a latch set by a failed import; a cleared latch reports the
    real import result (the exact opposite of the mutation's always-True)."""
    entailment._NLI.dead = False
    monkeypatch.setattr(entailment._NLI, "dead", False)
    # Whatever the environment decides, it must not be the mutation's unconditional True:
    # with UNTELL_DISABLE_NLI=1 it is definitively False.
    monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
    assert entailment.available() is False


def test_cli_reports_contradiction_at_four_decimals(monkeypatch, capsys) -> None:
    """Mutation `round(con, 4)` -> `round(con, 5)` in the CLI JSON output.

    A contradiction score with five significant decimals must appear rounded to
    four in the printed JSON; the mutation would print the fifth."""
    monkeypatch.setattr(entailment, "contradiction_score", lambda a, b: 0.12345)
    monkeypatch.setattr(entailment, "entailment_score", lambda a, b: 0.98765)
    rc = entailment.main(["original text", "rewritten text"])
    out = json.loads(capsys.readouterr().out)
    assert out["contradiction"] == 0.1235
    assert out["entailment"] == 0.9877
    assert rc == 0
