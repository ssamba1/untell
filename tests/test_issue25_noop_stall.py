"""Issue #25 — no-op-draw stop condition for rule-based (non-deterministic) rewriters.

The composite rewriter draws `best_of` candidates per outer-loop iteration under different seeds,
so the loop's existing stall guard (`deterministic` attr) never fires for it. MEASURED on 10 HC3
docs (lite tier): 15 draws/doc, 9-14 of them byte-identical no-ops on adopting docs, each paying a
full similarity+NLI-gate+rescore. The fix (in run.py) is twofold:

1. A byte-identical draw is a fixed point for any rewriter — its gate verdict and score are the
   incumbent's by definition — so its expensive gate is skipped while it is kept in the candidate
   pool with the incumbent's score+tells (preserving the tells tie-break byte-for-byte).
2. A rewriter that advertises `noop_stall_safe` (the rule-based CompositeRewriter) lets the loop
   stop at the first iteration whose every draw is a no-op and that adopted nothing, with
   `stopped="stalled_noop"`, instead of re-drawing guaranteed no-ops for the rest of max_iters.

These pin both halves, and that the flag is opt-in (not on unfixed/stochastic rewriters).
"""
from __future__ import annotations


def _num_score(mx: float, flagged: bool = True):
    def _s(text, tier="full", threshold=0.3):
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": mx},
            "max": mx,
            "mean": mx,
            "threshold": threshold,
            "flagged": flagged,
        }
    return _s


def _score_changed(changed_mx: float = 0.5, base_mx: float = 0.9):
    """0.5 for text the rewriter changed, 0.9 otherwise — so a changed candidate clearly wins."""
    def _s(text, tier="full", threshold=0.3):
        m = changed_mx if "CHANGED" in text else base_mx
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": m},
            "max": m,
            "mean": m,
            "threshold": threshold,
            "flagged": m >= threshold,
        }
    return _s


def test_composite_advertises_noop_stall_safe(monkeypatch):
    """The plain rule-based composite is safe to stop on an all-no-op iteration; its neural
    (T5 front-stage) variant is not (a later SAMPLE can differ), and neither is the ensemble."""
    from untell.rewriter.composite import CompositeRewriter

    plain = CompositeRewriter()
    assert plain.noop_stall_safe is True
    # T5 is (almost always) absent in CI, so use_t5 falls back to the rule-based chain -> still
    # safe. The point is the flag is computed, not hardcoded.
    assert isinstance(CompositeRewriter(use_t5=True).noop_stall_safe, bool)


def test_noop_stall_safe_rewriter_stops_after_adoption_plus_noop_iteration(monkeypatch):
    """Adopt a change in iteration 1, then return the input unchanged: the loop must stop at the
    first all-no-op iteration (2, not the full 5) with stopped='stalled_noop', keeping the adopted
    text byte-identical."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _score_changed())
    monkeypatch.setattr(run_mod, "meaning_preserved", lambda *a, **k: True)

    class _Stall:
        name = "stall"
        deterministic = False
        noop_stall_safe = True

        def __init__(self):
            self.calls = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.calls += 1
            return "CHANGED variant text here" if self.calls == 1 else text

    out = run_mod.untell_text(
        "Some AI generated paragraph that needs rewriting overall, in the end.",
        tier="lite", threshold=0.3, max_iters=5, best_of=3, rewriter=_Stall(),
        scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] == "stalled_noop"
    assert out["iterations"] == 2           # not the full 5
    assert out["rewrites"] == 6             # 3 (iter 1) + 3 (iter 2), not 15
    assert out["adopted"] == 1
    assert out["final"] == "CHANGED variant text here"


def test_noop_stall_safe_all_noop_stops_at_iteration_one(monkeypatch):
    """A rewriter with nothing to change returns the input byte-identical on every draw; the loop
    must stop at iteration 1 as stalled_noop, burning one iteration's draws, not all max_iters."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.6))
    monkeypatch.setattr(run_mod, "meaning_preserved", lambda *a, **k: True)

    class _NoopSafe:
        name = "noopsafe"
        deterministic = False
        noop_stall_safe = True

        def __init__(self):
            self.calls = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.calls += 1
            return text

    text = "This paragraph is already fairly clean prose that stays as it is."
    out = run_mod.untell_text(
        text, tier="lite", threshold=0.3, max_iters=5, best_of=3, rewriter=_NoopSafe(),
        scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] == "stalled_noop"
    assert out["iterations"] == 1
    assert out["rewrites"] == 3             # one iteration of best_of=3, not 15
    assert out["final"] == text


def test_noop_stall_is_opt_in_not_on_unflagged_rewriter(monkeypatch):
    """Without `noop_stall_safe` a rewriter (like the stochastic neural members) keeps drawing for
    all max_iters even when an iteration is all-no-op — the new stop must not fire on it."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.6))
    monkeypatch.setattr(run_mod, "meaning_preserved", lambda *a, **k: True)

    class _NoFlag:
        name = "noflag"
        deterministic = False
        # no noop_stall_safe

        def __init__(self):
            self.calls = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.calls += 1
            return text

    out = run_mod.untell_text(
        "Some text that stays the same every single draw here.",
        tier="lite", threshold=0.3, max_iters=5, best_of=3, rewriter=_NoFlag(),
        scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] != "stalled_noop"
    assert out["iterations"] == 5           # burned all iterations, as before

def test_all_changed_vetoed_draws_do_not_stall(monkeypatch):
    """A rewriter whose draws always CHANGE the text (but the gate always vetoes them) is not a
    no-op stall — every draw is a real, distinct candidate. It must NOT be stopped, because a later
    draw could be adopted. Pins that the stop requires ALL draws byte-identical, not just that
    nothing was adopted."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.6))
    monkeypatch.setattr(run_mod, "meaning_preserved", lambda *a, **k: False)  # veto every draw

    class _AlwaysChange:
        name = "alwayschange"
        deterministic = False
        noop_stall_safe = True

        def __init__(self):
            self.calls = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.calls += 1
            return f"CHANGED variant number {self.calls} of the text"  # always differs

    rw = _AlwaysChange()
    out = run_mod.untell_text(
        "Some AI text that keeps getting changed but never adopted overall.",
        tier="lite", threshold=0.3, max_iters=3, best_of=2, rewriter=rw,
        scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] != "stalled_noop"
    assert out["iterations"] == 3           # every draw differed, so no fixed point to stop on
    assert rw.calls == 6                    # all 2 draws x 3 iterations still drawn (not stopped)
