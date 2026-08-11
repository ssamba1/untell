"""untell-prove end-to-end tests — offline (rewriter + commercial HTTP mocked)."""

from __future__ import annotations

import pytest

from eval.prove import main, prove
from untell.detectors import commercial as C

_ENV = [
    "ORIGINALITY_API_KEY",
    "WINSTON_API_KEY",
    "GPTZERO_API_KEY",
    "SAPLING_API_KEY",
    "ZEROGPT_API_KEY",
    "COPYLEAKS_EMAIL",
    "COPYLEAKS_API_KEY",
]


class _NoopRW:
    """A rewriter double. It must satisfy the whole protocol, not the part currently exercised.

    `available()` was missing. That went unnoticed while `prove()` passed no rewriter at all —
    `untell_text` took the object branch and never asked. Once `prove` gained a `rewriter` name
    (defaulting to "composite", so the tool works without a hosted-LLM key), the string branch runs
    and calls `available()` on whatever `get_rewriter` returns. A double that implements less than
    the interface it stands in for only works until the caller uses the rest of it.
    """

    name = "noop"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    for v in _ENV:
        monkeypatch.delenv(v, raising=False)
    C._CL_TOKEN["token"] = None
    C._CL_TOKEN["exp"] = 0.0
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _NoopRW())


def test_prove_no_checkers_configured():
    v = prove("some text to untell and prove")
    assert v["passes_all"] is False  # nothing to verify against


def test_prove_passes_when_checker_low(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.05})
    v = prove("A sufficiently long AI-sounding paragraph for the detector to chew on.", threshold=0.30, margin=0.0)
    assert v["passes_all"] is True
    assert "humanized" in v
    assert v["after"]["results"]["sapling"]["passes"] is True


def test_prove_fails_when_checker_high(monkeypatch):
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.95})
    v = prove("text", threshold=0.30, margin=0.0, max_iters=1)
    assert v["passes_all"] is False


def test_prove_cli_exit_codes(monkeypatch, capsys):
    rc = main(["some text"])  # no keys -> non-zero
    assert rc == 1
    capsys.readouterr()  # flush the first (non-JSON) output before the JSON run
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"score": 0.02})
    rc = main(["--json", "text long enough for the checker"])
    assert rc == 0
    import json

    assert json.loads(capsys.readouterr().out)["passes_all"] is True


class TestProveRunsTheStrongLoop:
    """untell-prove is the "does it actually pass the REAL detectors" button, and every run spends
    paid credits. It called untell_text without best_of, inheriting that function's default of 1 —
    the weak single-draw path the CLI moved off after best-of-1 was identified as a root cause of
    understated evasion (measured: 33% still flagged at 1, 0% at 3).

    An understated result here is bought twice: a worse number, paid for.
    """

    def test_best_of_defaults_to_three(self):
        import inspect

        from eval.prove import prove

        assert inspect.signature(prove).parameters["best_of"].default == 3

    def test_it_reaches_the_loop(self, monkeypatch):
        import eval.prove as prove_mod

        seen: dict = {}
        monkeypatch.setattr(
            prove_mod, "untell_text",
            lambda text, **kw: seen.update(kw) or {"final": text, "iterations": 1},
        )
        monkeypatch.setattr(prove_mod, "verify", lambda t, **kw: {
            "configured": [], "results": {}, "passes_all": False, "n_configured": 0, "n_passing": 0,
        })
        prove_mod.prove("some text")
        assert seen["best_of"] == 3
        assert seen["tier"] == "commercial"

    def test_the_cli_exposes_and_forwards_it(self, monkeypatch):
        import eval.prove as prove_mod

        seen: dict = {}
        monkeypatch.setattr(prove_mod, "prove", lambda text, **kw: seen.update(kw) or {
            "passes_all": True, "before": {}, "after": {"configured": []}, "humanized": text,
            "iterations": 0,
        })
        prove_mod.main(["--best-of", "5", "--json", "some text"])
        assert seen["best_of"] == 5

    def test_the_cli_default_matches_untell_humanize(self, monkeypatch):
        """Read both defaults rather than restating either — that is how they drift apart."""
        import eval.prove as prove_mod
        from untell.scripts.run import build_parser

        seen: dict = {}
        monkeypatch.setattr(prove_mod, "prove", lambda text, **kw: seen.update(kw) or {
            "passes_all": True, "before": {}, "after": {"configured": []}, "humanized": text,
            "iterations": 0,
        })
        prove_mod.main(["--json", "some text"])
        cli_default = next(a for a in build_parser()._actions if a.dest == "best_of").default
        assert seen["best_of"] == cli_default
