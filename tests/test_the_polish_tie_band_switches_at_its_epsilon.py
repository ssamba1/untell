"""The last boundary survivor: the polish stage's tie band in `untell/scripts/run.py`.

`_TELLS_EPS` is the width of the detector noise band. Inside it the two candidates are treated as
scoring the same, and the AI-tell count breaks the tie. The comparison is `<=`, so a polished
candidate scoring EXACTLY `_TELLS_EPS` worse is still a tie — and that single input is the only
place a `<=` / `<` swap shows.
"""

from __future__ import annotations

from untell import attacks
from untell.scripts import run as run_mod
from untell.scripts.run import _TELLS_EPS

_INPUT = "The committee reviewed the proposal carefully. It then issued a short statement."
_POLISHED = "The committee reviewed that proposal carefully. It then issued a short statement."


def _drive(monkeypatch):
    """Run the loop with the polished candidate exactly `_TELLS_EPS` worse and carrying fewer tells.

    The incumbent scores 0.0 rather than some mid-range value on purpose: the band is compared with
    `abs(polished - best) <= _TELLS_EPS`, and `0.10 + 0.02 - 0.10` is 0.020000000000000004, not
    0.02. Anchoring the incumbent at zero makes the difference land exactly on the constant, which
    is the only input that distinguishes the two operators.
    """
    def fake_score_text(text, **kw):
        m = _TELLS_EPS if text == _POLISHED else 0.0
        return {"max": m, "mean": m, "scored": True, "detectors": {}, "flagged": False,
                "threshold": 0.30, "verdict_threshold": 0.45, "tier": "lite", "agreement": {}}

    def fake_score_tells(text, **kw):
        return {"tells": 1 if text == _POLISHED else 5, "tells_per_100w": 1.0,
                "by_category": {}, "burstiness_cv": 0.7, "words": 12,
                "language_supported": True}

    monkeypatch.setattr(run_mod, "score_text", fake_score_text)
    monkeypatch.setattr(run_mod, "score_tells", fake_score_tells)
    monkeypatch.setattr(run_mod, "similarity", lambda a, b: 1.0)
    monkeypatch.setattr(attacks, "surgical_substitute",
                        lambda text, *a, **kw: {"text": _POLISHED})
    return run_mod.untell_text(_INPUT, tier="lite", polish=True, best_of=1, max_iters=1,
                               scrub=False)


def test_a_polish_exactly_at_the_tie_band_edge_is_adopted_when_it_carries_fewer_tells(monkeypatch):
    """At exactly `_TELLS_EPS` worse, the candidate is inside the band and its lower tell count wins.

    Under `<`, the polished text is discarded: the run keeps a version with five tells instead of
    one, having spent the substitution work, and reports nothing about the near-miss. The band's
    whole purpose is that a difference this small is noise rather than a real regression.
    """
    out = _drive(monkeypatch)
    assert out["final"] == _POLISHED, (
        "a candidate exactly at the edge of the noise band, with fewer tells, must be adopted")


def test_the_incumbent_sits_at_zero_so_the_difference_is_exactly_the_constant():
    """Guard on the fixture: if the arithmetic stopped landing on the constant, the test above would
    exercise an ordinary in-band case and pass whichever way the comparison points."""
    assert abs(_TELLS_EPS - 0.0) == _TELLS_EPS


def test_a_polish_outside_the_tie_band_is_not_adopted(monkeypatch):
    """The neighbour: one ulp past the band and the polished text is refused, so the adoption above
    is the boundary rather than the stage adopting everything it is handed."""
    import math

    outside = math.nextafter(_TELLS_EPS, 1.0)

    def fake_score_text(text, **kw):
        m = outside if text == _POLISHED else 0.0
        return {"max": m, "mean": m, "scored": True, "detectors": {}, "flagged": False,
                "threshold": 0.30, "verdict_threshold": 0.45, "tier": "lite", "agreement": {}}

    monkeypatch.setattr(run_mod, "score_text", fake_score_text)
    monkeypatch.setattr(run_mod, "score_tells",
                        lambda text, **kw: {"tells": 1 if text == _POLISHED else 5,
                                            "tells_per_100w": 1.0, "by_category": {},
                                            "burstiness_cv": 0.7, "words": 12,
                                            "language_supported": True})
    monkeypatch.setattr(run_mod, "similarity", lambda a, b: 1.0)
    monkeypatch.setattr(attacks, "surgical_substitute",
                        lambda text, *a, **kw: {"text": _POLISHED})
    out = run_mod.untell_text(_INPUT, tier="lite", polish=True, best_of=1, max_iters=1,
                              scrub=False)
    assert out["final"] != _POLISHED
