"""Meaning-gate boundaries that survived the boundary sweep, and two that cannot be killed.

The gates decide whether a rewrite is allowed to reach the user. An off-by-one here is not a
cosmetic error: it either admits a rewrite that contradicts the source or rejects a faithful one,
and both failures are silent.
"""

from __future__ import annotations

import json

import pytest

from untell.detectors import perplexity_burstiness as pb
from untell.humanness import (
    _BURSTY_FLOOR,
    _BURSTY_IDEAL,
    _BURSTY_RAMP,
    _MAX_BURSTY_PENALTY,
)
from untell.rewriter.local_policy import _SENTENCE_ENTAILMENT_FLOOR
from untell.scripts import entailment as ent_mod
from untell.scripts.entailment import DEFAULT_CONTRADICTION_BAR, DEFAULT_ENTAILMENT_FLOOR

# --- entailment.main: `con < BAR and ent >= FLOOR` ---

def _verdict(monkeypatch, con: float, ent: float, capsys) -> dict:
    monkeypatch.setattr(ent_mod, "contradiction_score", lambda a, b: con)
    monkeypatch.setattr(ent_mod, "entailment_score", lambda a, b: ent)
    code = ent_mod.main(["the original sentence", "the rewritten sentence"])
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    payload["exit_code"] = code
    return payload


def test_a_contradiction_exactly_at_the_bar_is_not_preserved(monkeypatch, capsys):
    """`con < DEFAULT_CONTRADICTION_BAR`: at the bar the rewrite is REJECTED.

    Under `<=`, a rewrite whose contradiction score sits exactly on the bar is passed through as
    meaning-preserving, and the exit code a shell step branches on flips from 1 to 0.
    """
    out = _verdict(monkeypatch, con=DEFAULT_CONTRADICTION_BAR, ent=0.9, capsys=capsys)
    assert out["preserved"] is False
    assert out["exit_code"] == 1


def test_a_hair_under_the_contradiction_bar_is_preserved(monkeypatch, capsys):
    """The neighbour, so the rejection above is the bar and not a blanket refusal."""
    import math
    under = math.nextafter(DEFAULT_CONTRADICTION_BAR, 0.0)
    out = _verdict(monkeypatch, con=under, ent=0.9, capsys=capsys)
    assert out["preserved"] is True and out["exit_code"] == 0


def test_entailment_exactly_at_the_floor_is_preserved(monkeypatch, capsys):
    """`ent >= DEFAULT_ENTAILMENT_FLOOR`: at the floor the rewrite is ACCEPTED.

    Under `>`, a rewrite sitting exactly on the floor is rejected — the gate refuses a rewrite it
    is documented to admit, which shows up as the loop silently returning the original.
    """
    out = _verdict(monkeypatch, con=0.01, ent=DEFAULT_ENTAILMENT_FLOOR, capsys=capsys)
    assert out["preserved"] is True
    assert out["exit_code"] == 0


def test_a_hair_under_the_entailment_floor_is_rejected(monkeypatch, capsys):
    """The neighbour on the other side of the floor."""
    import math
    under = math.nextafter(DEFAULT_ENTAILMENT_FLOOR, 0.0)
    out = _verdict(monkeypatch, con=0.01, ent=under, capsys=capsys)
    assert out["preserved"] is False and out["exit_code"] == 1


# --- local_policy._sentence_is_faithful: `score >= _SENTENCE_ENTAILMENT_FLOOR` ---

def _faithful(monkeypatch, score: float) -> bool:
    from untell.rewriter import local_policy
    from untell.scripts import entailment

    monkeypatch.setattr(entailment, "available", lambda: True)
    monkeypatch.setattr(entailment, "entailment_score", lambda source, candidate: score)
    policy = local_policy.LocalPolicyRewriter.__new__(local_policy.LocalPolicyRewriter)
    source = "The quarterly figures were revised upward by the finance team."
    # Same length band, so the mechanical word-ratio guard above cannot decide this.
    candidate = "The quarterly figures were revised upward by the finance group."
    return policy._sentence_is_faithful(source, candidate)


def test_a_sentence_exactly_on_the_entailment_floor_is_faithful(monkeypatch):
    """At the floor the candidate is admitted. Under `>`, a rewrite the policy documents as
    acceptable is vetoed, and the loop reports "nothing adopted" for a draft that was fine."""
    assert _faithful(monkeypatch, _SENTENCE_ENTAILMENT_FLOOR) is True


def test_a_hair_under_the_entailment_floor_is_not_faithful(monkeypatch):
    """The neighbour, so the acceptance above is the floor rather than a gate that never vetoes."""
    import math
    assert _faithful(monkeypatch, math.nextafter(_SENTENCE_ENTAILMENT_FLOOR, 0.0)) is False


# --- humanness: `cv < _BURSTY_FLOOR` ---

def test_the_burstiness_floor_is_a_continuity_point_not_a_switch():
    """`cv < _BURSTY_FLOOR` is a THIRD equivalent mutant, and the reason is worth writing down.

    The two branches are::

        if cv < _BURSTY_FLOOR:   penalty = _MAX_BURSTY_PENALTY
        elif cv < 0.50:          penalty = _MAX_BURSTY_PENALTY * (0.50 - cv) / _BURSTY_RAMP

    At `cv == _BURSTY_FLOOR` the ramp evaluates `MAX * (0.50 - 0.35) / 0.15` = `MAX * 1` = `MAX`.
    The ramp is CONSTRUCTED to meet the flat penalty at the floor, so the piecewise function is
    continuous there and the two arms return the same value. `<` and `<=` therefore select
    different branches that compute the same number.

    In IEEE arithmetic they differ by 5.55e-17, and `humanness` returns
    `round(human_score * 100.0, 1)`, which erases a difference seventeen orders of magnitude below
    its last printed digit. MEASURED: 69.0 on both sides.

    So this row can never leave the register, and that is a property of the design rather than a
    gap in the tests. Asserting the continuity keeps it that way: change the ramp's slope or the
    floor and this fails, which is exactly when the boundary would become real.
    """
    ramp_at_floor = _MAX_BURSTY_PENALTY * (0.50 - _BURSTY_FLOOR) / _BURSTY_RAMP
    assert ramp_at_floor == pytest.approx(_MAX_BURSTY_PENALTY, abs=1e-15), (
        "the ramp no longer meets the flat penalty at the floor — the branches now disagree and "
        "this boundary needs a real test")
    assert abs(ramp_at_floor - _MAX_BURSTY_PENALTY) < 1e-9, (
        "any difference this small is erased by round(score * 100.0, 1)")


# --- Two more equivalent mutants, recorded rather than faked ---

def test_the_repetition_signal_floor_cannot_be_killed_by_any_test():
    """`perplexity_burstiness._repetition_signal` reads::

        if ttr >= _TTR_FLOOR:
            return 0.0
        return clamp01((_TTR_FLOOR - ttr) / (_TTR_FLOOR - _TTR_SATURATION))

    Under `>`, a ttr exactly at the floor falls through instead of returning early — and the
    fall-through evaluates `(FLOOR - FLOOR) / (FLOOR - SATURATION)`, which is exactly 0.0, the same
    value the early return gives. The mutant is EQUIVALENT: observationally identical on every
    input, so it survives every sweep and always will.
    """
    assert pb._TTR_FLOOR != pb._TTR_SATURATION, "a zero denominator would change this analysis"
    fall_through = (pb._TTR_FLOOR - pb._TTR_FLOOR) / (pb._TTR_FLOOR - pb._TTR_SATURATION)
    assert max(0.0, min(1.0, fall_through)) == 0.0, (
        "the fall-through no longer equals the early return — the boundary is now reachable "
        "and needs a real test")


def test_the_burstiness_shape_label_boundary_is_unreachable():
    """`_dominant_signal` reads::

        if cv < 0.35:   penalty = MAX
        elif cv < 0.50: penalty = MAX * (0.50 - cv) / 0.15
        elif cv > 1.0:  penalty = MAX * 0.5
        else:           penalty = 0.0
        if penalty > 0:
            shape = "uniform" if cv < _BURSTY_IDEAL else "erratic"

    The label line is reached only when `penalty > 0`, which requires `cv < 0.50` or `cv > 1.0`.
    `cv == _BURSTY_IDEAL` (0.70) satisfies neither, so `<` and `<=` cannot differ there. EQUIVALENT.
    """
    reachable = [c / 1000 for c in range(0, 3001) if c / 1000 < 0.50 or c / 1000 > 1.0]
    assert _BURSTY_IDEAL not in reachable, (
        "the ideal is now a reachable cv — the shape label needs a real boundary test")
    assert not any((c < _BURSTY_IDEAL) != (c <= _BURSTY_IDEAL) for c in reachable)
