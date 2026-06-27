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
        import re

        sentinels = re.findall(r"⟦HZ\d{4}⟧", text)
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
    rc = main(["--tier", "lite", "some text to untell here please"])
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
    res = untell_text(AI, tier="lite", browser="zerogpt", threshold=0.30, max_iters=3, sim_bar=0.0)
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
        import re

        return re.sub(r"⟦HZ\d{4}⟧", "", "It shifted fast, and nobody saw it coming at all.")


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
            import re

            calls["n"] += 1
            sentinels = re.findall(r"⟦HZ\d{4}⟧", text)
            tail = (" " + " ".join(sentinels)) if sentinels else ""
            return f"It shifted, and people noticed. Variant {calls['n']}.{tail}"

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _MultiRW())
    # threshold=0.0 forces a rewrite; best_of=3 => exactly three candidates drawn in the one iteration.
    res = untell_text(AI, tier="lite", threshold=0.0, max_iters=1, best_of=3)
    assert "error" not in res
    assert calls["n"] == 3
    assert "Smith (2020)" in res["final"] and "47%" in res["final"]  # facts survive best-of selection
