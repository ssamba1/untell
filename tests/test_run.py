"""Headless untell-loop tests — offline (rewriter mocked; no network, no keys)."""

from __future__ import annotations

import json

from untell.scripts.run import main, untell_text

AI = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations utilize it to significantly improve operational efficiency. Overall, "
    "the impact continues to grow across various sectors according to Smith (2020), rising 47%."
)


class _GoodRW:
    """A rewriter that returns bursty, human-ish text while preserving the sentinels it is given."""

    name = "fake"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        # Keep any sentinels present in the input so restore still works.
        # Uses the PRODUCTION pattern rather than a hand-written `\d{4}`: lock() numbers sentinels
        # with a minimum width, so past 9999 spans they carry five digits. A test regex that only
        # matches four could not detect a regression of exactly that bug.
        from untell.scripts.preserve import SENTINEL_RE

        sentinels = SENTINEL_RE.findall(text)
        tail = (" " + " ".join(sentinels)) if sentinels else ""
        return "It shifted. Fast. Nobody saw it coming, and then everything was different." + tail


def test_untell_text_runs_loop_and_restores(monkeypatch):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    res = untell_text(AI, tier="lite", max_iters=3)
    assert "error" not in res
    assert res["iterations"] >= 1
    assert res["post"]["max"] <= res["pre"]["max"] + 1e-9
    # Locked facts must survive into the final output.
    assert "Smith (2020)" in res["final"]
    assert "47%" in res["final"]


def test_per_detector_threshold_blocks_pass(monkeypatch):
    """An impossible per-detector threshold forces the loop to run even when the global bar passes."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    res = untell_text(
        AI,
        tier="lite",
        threshold=1.0,  # global bar passes
        max_iters=2,
        detector_thresholds={"perplexity_burstiness": 0.0},  # can never be satisfied (score >= 0)
    )
    assert res["stopped"] == "max_iters"
    assert res["iterations"] == 2


def test_untell_text_no_rewriter_returns_error(monkeypatch):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: None)
    res = untell_text(AI, tier="lite")
    assert "error" in res
    assert res["final"] == AI  # unchanged


def test_untell_text_survives_rewriter_exception(monkeypatch):
    import untell.scripts.run as run_mod

    class _Boom:
        name = "boom"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            raise RuntimeError("api down")

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _Boom())
    # threshold=0.0 forces `flagged` at any tier (max >= 0 always), so the rewriter is invoked and
    # its exception path is exercised regardless of how the detectors happen to score this text.
    res = untell_text(AI, tier="lite", threshold=0.0)
    assert "error" in res and "rewriter failed" in res["error"]


def test_cli_json_output(monkeypatch, capsys):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    rc = main(["--tier", "lite", "--json", AI])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # ensure_ascii -> portable
    parsed = json.loads(out)
    assert "final" in parsed and parsed["iterations"] >= 1


def test_cli_no_rewriter_exits_nonzero(monkeypatch, capsys):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: None)
    # Explicitly request 'auto' rewriter (which fails without a key)
    rc = main(["--rewriter", "auto", "--tier", "lite", "some text to untell here please"])
    assert rc == 1
    assert "ERROR" in capsys.readouterr().out


def test_deterministic_rewriter_stops_early_on_stall(monkeypatch):
    import untell.scripts.run as run_mod

    class _Det:
        name = "det"
        deterministic = True  # identical input -> identical output

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            return text  # identity: keeps sentinels, sim 1.0, never improves -> must stall iter 1

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _Det())
    # threshold=0.0 => never "passes" (max >= 0 always), so only the stall guard can stop the loop.
    res = untell_text(AI, tier="lite", threshold=0.0, max_iters=5)
    assert res["stopped"] == "stalled"
    assert res["iterations"] == 1  # a deterministic no-op rewrite is caught on the first pass


def test_stochastic_rewriter_does_not_stall(monkeypatch):
    import untell.scripts.run as run_mod

    # _GoodRW has no `deterministic` flag, so the stall guard must never fire for it: it runs the
    # full budget (or passes), never stopping with "stalled".
    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    res = untell_text(AI, tier="lite", threshold=0.0, max_iters=3)
    assert res["stopped"] != "stalled"
    assert res["iterations"] == 3


def test_cli_rewriter_surgical_runs_with_no_key(monkeypatch, capsys):
    # The whole point of --rewriter surgical: the loop runs at $0 with NO API key and NO policy dir,
    # instead of the "no rewriter configured" error path. (lite tier keeps it fast and offline.)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UNTELL_POLICY_DIR", raising=False)
    rc = main(["--tier", "lite", "--rewriter", "surgical", "--json", AI])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert "error" not in parsed
    assert "final" in parsed
    # Locked facts still survive the surgical rewriter path.
    assert "Smith (2020)" in parsed["final"] and "47%" in parsed["final"]


def test_cli_empty_input_returns_2(capsys):
    rc = main(["--tier", "lite", "   "])
    assert rc == 2


def test_browser_scoring_loop_converges(monkeypatch):
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())

    calls = {"n": 0}

    class _FakeChk:
        def available(self):
            return True

        def check(self, text, **k):
            calls["n"] += 1
            return 0.9 if calls["n"] == 1 else 0.05  # flagged first, passes after one rewrite

    monkeypatch.setattr(bc, "get_browser_checker", lambda name: _FakeChk())
    # sim_bar=0.0 isolates the browser-scoring behaviour from the lite token-overlap quality gate.
    res = untell_text(AI, tier="lite", browser="zerogpt", threshold=0.30, max_iters=3, sim_bar=0.0,
                      veto_contradictions=False)
    assert "error" not in res
    assert res["tier"] == "browser:zerogpt"
    assert res["post"]["max"] <= 0.30
    assert res["stopped"] == "passed"
    assert calls["n"] >= 2  # actually drove the web checker each iteration


def test_browser_scoring_max_across_multiple(monkeypatch):
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())

    class _Chk:
        def __init__(self, val):
            self.val = val

        def available(self):
            return True

        def check(self, text, **k):
            return self.val

    # two detectors: one already low, one high -> max is high -> must keep going (drives "beat all")
    fakes = {"zerogpt": _Chk(0.05), "detecting-ai": _Chk(0.10)}
    monkeypatch.setattr(bc, "get_browser_checker", lambda name: fakes.get(name))
    res = untell_text(AI, tier="lite", browser="zerogpt,detecting-ai", threshold=0.30, max_iters=2, sim_bar=0.0)
    assert "error" not in res
    assert res["tier"] == "browser:zerogpt,detecting-ai"
    assert set(res["post"]["detectors"]) >= {"zerogpt", "detecting-ai"}
    assert res["post"]["max"] == 0.10  # max across both, both under threshold -> passes
    assert res["stopped"] == "passed"


def test_margin_blocks_borderline_pass(monkeypatch):
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())

    class _Chk:
        def available(self):
            return True

        def check(self, text, **k):
            return 0.28  # below threshold 0.30 but only just

    monkeypatch.setattr(bc, "get_browser_checker", lambda name: _Chk())
    # margin 0: 0.28 < 0.30 -> comfortable enough, passes
    r0 = untell_text(AI, tier="lite", browser="zerogpt", threshold=0.30, margin=0.0, max_iters=2, sim_bar=0.0)
    assert r0["stopped"] == "passed"
    # margin 0.10: needs < 0.20 -> 0.28 is a borderline pass -> keep iterating, hit the cap
    rm = untell_text(AI, tier="lite", browser="zerogpt", threshold=0.30, margin=0.10, max_iters=2, sim_bar=0.0)
    assert rm["stopped"] == "max_iters"


def test_confirm_demotes_a_noisy_pass(monkeypatch):
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    seq = iter([0.05, 0.05, 0.9])  # pre passes, first confirm passes, second confirm re-flags

    class _Chk:
        def available(self):
            return True

        def check(self, text, **k):
            try:
                return next(seq)
            except StopIteration:
                return 0.9

    monkeypatch.setattr(bc, "get_browser_checker", lambda name: _Chk())
    res = untell_text(
        AI, tier="lite", browser="zerogpt", threshold=0.30, margin=0.0, max_iters=1, sim_bar=0.0, confirm=2
    )
    assert res["stopped"] == "passed_unconfirmed"


def test_browser_scoring_unavailable_errors(monkeypatch):
    import untell.browser_check as bc
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _GoodRW())
    monkeypatch.setattr(bc, "get_browser_checker", lambda name: None)
    res = untell_text(AI, tier="lite", browser="zerogpt")
    assert "error" in res and "no browser checker available" in res["error"]


class _DropRW:
    """A rewriter that lowers the signal but DROPS the locked sentinels — the exact failure the
    quality gate must catch, so a citation/number is never silently lost on restore."""

    name = "drop"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        from untell.scripts.preserve import SENTINEL_RE

        return SENTINEL_RE.sub("", "It shifted fast, and nobody saw it coming at all.")


def test_loop_rejects_sentinel_dropping_rewrite(monkeypatch):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _DropRW())
    # threshold=0.0 forces the rewriter to be invoked every iteration (max >= 0 always flags).
    res = untell_text(AI, tier="lite", threshold=0.0, max_iters=3)
    assert "error" not in res
    assert res["rewrites"] >= 1  # the sentinel-dropping rewrite was actually attempted...
    # ...and rejected every time, so the locked facts survive into the final output.
    assert "Smith (2020)" in res["final"]
    assert "47%" in res["final"]


def test_best_of_n_draws_multiple_candidates_and_keeps_facts(monkeypatch):
    import untell.scripts.run as run_mod

    calls = {"n": 0}

    class _MultiRW:
        name = "multi"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            from untell.scripts.preserve import SENTINEL_RE

            calls["n"] += 1
            sentinels = SENTINEL_RE.findall(text)
            tail = (" " + " ".join(sentinels)) if sentinels else ""
            return f"It shifted, and people noticed. Variant {calls['n']}.{tail}"

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _MultiRW())
    # threshold=0.0 forces a rewrite; best_of=3 => exactly three candidates drawn in the one iteration.
    res = untell_text(AI, tier="lite", threshold=0.0, max_iters=1, best_of=3)
    assert "error" not in res
    assert calls["n"] == 3
    assert "Smith (2020)" in res["final"] and "47%" in res["final"]  # facts survive best-of selection


class TestRewriterByName:
    """`untell_text(rewriter="composite")` used to fail deep in the loop.

    The parameter is untyped, named after the thing users type on the command line, and every
    caller in the repo (CLI, MCP server, REST API) resolved the name before calling — so it was
    effectively object-only. Passing the obvious string produced:

        rewriter failed: AttributeError: 'str' object has no attribute 'rewrite'

    which says nothing about the cause. Found by making that exact mistake while measuring the loop.
    """

    def test_name_and_object_are_equivalent(self):
        from untell.rewriter import get_rewriter
        from untell.scripts.run import untell_text

        text = ("Furthermore, organizations increasingly leverage these robust technologies to "
                "optimize operational efficiency across sectors.")
        by_name = untell_text(text, tier="lite", rewriter="composite", max_iters=1, best_of=1)
        by_object = untell_text(text, tier="lite", rewriter=get_rewriter(prefer="composite"),
                                max_iters=1, best_of=1)
        assert "error" not in by_name, by_name.get("error")
        assert "error" not in by_object, by_object.get("error")
        assert by_name["pre"]["max"] == by_object["pre"]["max"]

    def test_unknown_name_is_a_clear_error_not_a_silent_substitution(self):
        """A caller who names a rewriter wants that one. Falling back to auto-selection would
        attribute results to the wrong technique."""
        from untell.scripts.run import untell_text

        r = untell_text("Some text here to rewrite.", tier="lite", rewriter="does_not_exist")
        assert "does_not_exist" in r["error"]
        assert r["final"] == "Some text here to rewrite."

    def test_missing_rewriter_error_names_the_library_form(self):
        """The message used to name only `--rewriter composite`, which a library caller cannot pass."""
        from untell.scripts.run import untell_text

        r = untell_text("Some text here.", tier="lite", rewriter=None, max_iters=1)
        if "error" in r:  # only when no API key / policy dir is configured
            assert "rewriter='composite'" in r["error"]


def _fixed_score(mapping, default=0.5):
    """score_text stand-in keyed on exact text."""
    def _s(text, tier="full", threshold=0.3):
        mx = mapping.get(text.strip(), default)
        return {"tier": tier, "detectors": {"perplexity_burstiness": mx}, "max": mx, "mean": mx,
                "threshold": threshold, "flagged": mx >= threshold, "scored": True}
    return _s


class _Same:
    name = "same"
    deterministic = True

    def available(self):
        return True

    def rewrite(self, text, score, threshold=0.3):
        return text


def test_polish_never_trades_a_pass_for_a_tie(monkeypatch):
    """The tie band is +/- _TELLS_EPS (0.02), so a polished candidate scoring UP TO 0.02 worse is
    adopted when it carries fewer tells. If the incumbent sits just under the threshold that band
    straddles it, and polish un-passes text the loop had already passed.

    MEASURED before: incumbent 0.28 (passing), polished 0.30 with fewer tells -> adopted, and the
    run returned stopped='passed' together with flagged=True and max exactly at the threshold. The
    same result said it had succeeded and that the text was still flagged.
    """
    import untell.attacks as attacks_mod
    import untell.scripts.run as run_mod

    src = "Furthermore, the organization leverages robust methodologies to optimize outcomes."
    polished = "The organization uses solid methods to improve outcomes."

    monkeypatch.setattr(run_mod, "score_text", _fixed_score({src: 0.28, polished: 0.30}, 0.28))
    monkeypatch.setattr(
        attacks_mod, "surgical_substitute", lambda t, tier=None, threshold=0.3: {"text": polished}
    )

    out = run_mod.untell_text(src, tier="lite", threshold=0.30, max_iters=1, rewriter=_Same(),
                              polish=True, scrub=False, sim_bar=0.0)
    assert out["stopped"] == "passed"
    assert out["post"]["max"] < 0.30, "polish pushed the score back over the threshold"
    assert out["final"].strip() != polished


def test_polish_is_still_adopted_when_it_genuinely_helps(monkeypatch):
    """The guard must not disable polish — only stop it from un-passing."""
    import untell.attacks as attacks_mod
    import untell.scripts.run as run_mod

    src = "Furthermore, the organization leverages robust methodologies to optimize outcomes."
    polished = "The organization uses solid methods to improve outcomes."

    monkeypatch.setattr(run_mod, "score_text", _fixed_score({src: 0.28, polished: 0.10}, 0.28))
    monkeypatch.setattr(
        attacks_mod, "surgical_substitute", lambda t, tier=None, threshold=0.3: {"text": polished}
    )

    out = run_mod.untell_text(src, tier="lite", threshold=0.30, max_iters=1, rewriter=_Same(),
                              polish=True, scrub=False, sim_bar=0.0)
    assert out["final"].strip() == polished
    assert out["post"]["max"] == 0.10


def test_already_clean_text_reports_zero_iterations(monkeypatch):
    """`iters = i` was set before the exit check, so text needing no work came back claiming a
    round of rewriting had happened — next to rewrites=0, contradicting itself."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _fixed_score({}, 0.05))
    out = run_mod.untell_text(
        "This sentence is already clean and needs no work at all today.",
        tier="lite", threshold=0.30, max_iters=5, rewriter=_Same(), scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] == "passed"
    assert out["iterations"] == 0
    assert out["rewrites"] == 0


def test_work_still_counts_its_iterations(monkeypatch):
    """Zero must mean zero, not "the counter is broken"."""
    import untell.scripts.run as run_mod

    src = "Furthermore, this text is flagged and will stay flagged throughout the run."
    monkeypatch.setattr(run_mod, "score_text", _fixed_score({}, 0.90))
    out = run_mod.untell_text(src, tier="lite", threshold=0.30, max_iters=3, rewriter=_Same(),
                              scrub=False, sim_bar=0.0)
    assert out["iterations"] >= 1


def test_tells_tiebreak_never_costs_a_pass(monkeypatch):
    """The near band is +/- _TELLS_EPS (0.02), so when the best candidate sits just under the
    threshold the band straddles it — and a fractionally worse, NON-passing candidate with fewer
    tells wins the tie-break. The loop then has nothing to stop on and burns every remaining
    iteration before reporting max_iters, having had a passing candidate in hand.

    Identical shape to the polish adoption bug above: a preference that is only meant to break ties
    was allowed to decide a loss.
    """
    import untell.scripts.run as run_mod

    src = "Furthermore, the organization leverages robust methodologies to optimize outcomes."
    passing = "Moreover, furthermore, the org leverages robust methodologies to optimize outcomes."
    clean = "The organization uses solid methods to improve outcomes for everyone involved."

    monkeypatch.setattr(
        run_mod, "score_text", _fixed_score({src: 0.90, passing: 0.28, clean: 0.30}, 0.90)
    )

    class _TwoDraws:
        name = "two"
        deterministic = False

        def __init__(self):
            self.n = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.n += 1
            return passing if self.n % 2 else clean

    out = run_mod.untell_text(src, tier="lite", threshold=0.30, max_iters=4, rewriter=_TwoDraws(),
                              best_of=2, scrub=False, sim_bar=0.0)
    assert out["stopped"] == "passed"
    assert out["post"]["max"] == 0.28
    assert out["final"].strip() == passing


def test_tells_tiebreak_still_applies_when_neither_passes(monkeypatch):
    """The preference must survive where it is legitimate — among equally non-passing candidates,
    fewer tells still wins."""
    import untell.scripts.run as run_mod

    src = "Furthermore, the organization leverages robust methodologies to optimize outcomes."
    telly = "Moreover, furthermore, it leverages robust methodologies to optimize outcomes daily."
    cleaner = "The organization uses solid methods to improve outcomes for everyone involved daily."

    monkeypatch.setattr(
        run_mod, "score_text", _fixed_score({src: 0.90, telly: 0.60, cleaner: 0.61}, 0.90)
    )

    class _TwoDraws:
        name = "two"
        deterministic = False

        def __init__(self):
            self.n = 0

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            self.n += 1
            return telly if self.n % 2 else cleaner

    # veto_contradictions=False isolates the tie-break: with the NLI gate live it rejects the
    # heavily-reworded draw before selection ever sees it, so the test would be measuring the gate.
    out = run_mod.untell_text(src, tier="lite", threshold=0.30, max_iters=1, rewriter=_TwoDraws(),
                              best_of=2, scrub=False, sim_bar=0.0, veto_contradictions=False)
    assert out["final"].strip() == cleaner, "fewer tells should still win among non-passing draws"



class TestAdoptedAndChangedAreReported:
    """`rewrites` counts draws, so it cannot answer "did anything happen to my text".

    MEASURED before these keys existed: a text the loop could not improve came back
    byte-identical while the result said rewrites=1 (and would say 3 at the default best_of=3).
    The only honest signal was similarity=1.0, which reads as a quality number, not a no-op flag.
    """

    def _run(self, text, threshold):
        from untell.rewriter import get_rewriter
        from untell.scripts.run import untell_text

        rw = get_rewriter(prefer="surgical")
        return untell_text(
            text, tier="lite", rewriter=rw, threshold=threshold, max_iters=2, best_of=3
        )

    def test_unimprovable_text_reports_no_adoption_and_no_change(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        text = "The cat sat on the mat. It was warm there. Later it moved to the sill and slept."
        r = self._run(text, 0.001)
        assert r["changed"] is False
        assert r["adopted"] == 0
        assert r["final"].strip() == text.strip()

    def test_already_passing_text_draws_nothing(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        r = self._run("The cat sat on the mat. It was warm there.", 0.99)
        assert r["rewrites"] == 0 and r["adopted"] == 0 and r["changed"] is False

    def test_changed_always_agrees_with_the_text(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        text = "Moreover, we leverage robust and seamless solutions to delve into the tapestry."
        r = self._run(text, 0.30)
        assert r["changed"] == (r["final"].strip() != text.strip())

    def test_adopted_never_exceeds_draws(self, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        r = self._run("Furthermore, this groundbreaking paradigm underscores the pivotal role.", 0.30)
        assert r["adopted"] <= r["rewrites"]


class TestStrongerRewriterHint:
    """A run that ends still flagged with a rewriter measured unable to clear real text should
    say so, because the user has no other way to discover the alternative.

    MEASURED on the same six real HC3 texts, full tier, best_of=3, max_iters=5, pre identical
    at 0.9994 for both:
        composite   post 0.8052   flagged 1.00   hc3_roberta 0.7559   sim 0.986/0.965
        neural      post 0.5017   flagged 0.50   hc3_roberta 0.4072   sim 0.941/0.884
    """

    class _RW:
        def __init__(self, name):
            self.name = name

    def test_fires_for_a_weak_rewriter_that_ended_flagged(self):
        from untell.scripts.run import _stronger_rewriter_hint

        for name in ("composite", "surgical", "structural", "targeted"):
            hint = _stronger_rewriter_hint(self._RW(name), True, "full")
            assert "suggestion" in hint, f"{name} should suggest a stronger rewriter"
            assert "neural" in hint["suggestion"]

    def test_silent_when_the_run_passed(self):
        from untell.scripts.run import _stronger_rewriter_hint

        assert _stronger_rewriter_hint(self._RW("composite"), False, "full") == {}

    def test_silent_on_tiers_the_measurement_does_not_cover(self):
        """The numbers quoted are full-tier. Repeating them under lite would be a false citation."""
        from untell.scripts.run import _stronger_rewriter_hint

        for tier in ("lite", "heavy", "commercial", "browser:zerogpt"):
            assert _stronger_rewriter_hint(self._RW("composite"), True, tier) == {}

    def test_silent_for_rewriters_that_are_already_the_advice(self):
        from untell.scripts.run import _stronger_rewriter_hint

        for name in ("neural", "ensemble", "max", "mt_pivot", None):
            assert _stronger_rewriter_hint(self._RW(name), True, "full") == {}

    def test_hint_reaches_the_rendered_output(self):
        from untell.scripts.run import _render

        result = {
            "pre": {"max": 0.99, "detectors": {}},
            "post": {"max": 0.80, "threshold": 0.30, "detectors": {}},
            "similarity": 0.98, "sim_bar": 0.76, "quality_metric": "cosine",
            "tier": "full", "iterations": 5, "stopped": "max_iters",
            "final": "some text", "suggestion": "try --rewriter neural",
        }
        out = _render(result)
        assert "try --rewriter neural" in out
        # Above the output text, where it will actually be read.
        assert out.index("try --rewriter neural") < out.index("--- humanized text ---")


class TestTheResultNamesTheFidelityGate:
    """`quality_metric` names the similarity backend and says nothing about the NLI axis — and the
    NLI axis is the one that catches inversions.

    MEASURED on "The new build runs faster than the old one." -> "...runs slower...", similarity
    0.983 against a 0.76 bar:

        NLI available    meaning_preserved -> False   (rejected)
        NLI unavailable  meaning_preserved -> True    (ADMITTED)

    The result shape was identical either way, so a run on an install without the NLI extra could
    adopt a meaning-INVERTED rewrite and look exactly like one where the gate was fully active.
    Same class as `detector_modes` on the score result: a guarantee that depends on an optional
    dependency has to say whether it was in force.
    """

    TEXT = "Furthermore, the system leverages robust methodologies to optimize outcomes today."

    def _run(self, **kw):
        from untell.rewriter import get_rewriter
        from untell.scripts.run import untell_text

        return untell_text(
            self.TEXT, tier="lite", threshold=0.30, max_iters=1,
            rewriter=get_rewriter(prefer="surgical"), **kw
        )

    def test_the_nli_gate_is_named_when_present(self):
        import untell.scripts.entailment as ent

        if not ent.available():
            pytest.skip("NLI model not installed here")
        assert self._run()["meaning_gate"] == "nli"

    def test_an_absent_nli_model_is_named(self, monkeypatch):
        import untell.scripts.entailment as ent

        monkeypatch.setattr(ent, "available", lambda: False)
        assert self._run()["meaning_gate"] == "similarity-only (NLI unavailable)"

    def test_disabling_the_veto_is_named_separately(self):
        """Deliberately off and unavailable are different facts about the same weaker gate, and a
        reader needs to know which — one is a choice, the other a missing dependency."""
        gate = self._run(veto_contradictions=False)["meaning_gate"]
        assert gate == "similarity-only (veto disabled)"

    def test_the_render_warns_when_the_veto_did_not_run(self, monkeypatch):
        import untell.scripts.entailment as ent
        from untell.scripts.run import _render

        monkeypatch.setattr(ent, "available", lambda: False)
        rendered = _render(self._run())
        assert "meaning gate: similarity-only" in rendered
        assert "did NOT run" in rendered
        assert "inversions" in rendered

    def test_the_render_is_quiet_when_the_gate_is_whole(self):
        import untell.scripts.entailment as ent
        from untell.scripts.run import _render

        if not ent.available():
            pytest.skip("NLI model not installed here")
        rendered = _render(self._run())
        assert "meaning gate: nli" in rendered
        assert "did NOT run" not in rendered

    def test_a_broken_availability_check_reports_unknown_rather_than_raising(self, monkeypatch):
        """The diagnostic must not be the thing that fails.

        Targets the helper directly: `available()` is consulted by the candidate path too, so
        patching it to raise would abort the loop before this ever ran — which tests the loop's
        error handling, not this guard.
        """
        import untell.scripts.entailment as ent
        from untell.scripts.run import _meaning_gate_mode

        monkeypatch.setattr(
            ent, "available", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        assert _meaning_gate_mode(True) == "unknown"
