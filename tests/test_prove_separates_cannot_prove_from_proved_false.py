"""`untell prove` returned 1 whether the text failed or nothing had run.

`untell-verify` already draws this line. Its CHANGELOG entry: exiting 0 when no checker ran told a
gating CI job the text had passed every major AI checker when none was consulted — "now exit 2,
kept distinct from 1 (checkers ran and failed) because nothing running is a configuration problem,
not a verdict about the text."

`prove` is the same shape of command — verify, loop, re-verify — and did not draw it. With no API
keys it printed

    No commercial checkers configured. Set the API keys ... cannot prove 'passes all' without
    running the real checkers.

and returned 1. Both outcomes mean stop, and they need opposite fixes: one is "rewrite more", the
other is "set ORIGINALITY_API_KEY". A caller reading only the code cannot tell which.

`passes_all` is False in both cases, correctly — nothing was proved — so the configured-checker
count is what separates them.
"""
from __future__ import annotations

import json

import pytest

from eval.prove import main

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency across the evaluated corpus."
)


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_no_configured_checkers_exits_two(capsys):
    """The case that matters for CI: a configuration problem, not a verdict."""
    code = main([TEXT, "--max-iters", "1", "--best-of", "1"])
    capsys.readouterr()
    assert code == 2, "no checkers ran, so this is not a failed verdict"


def test_empty_input_still_exits_two(monkeypatch, capsys):
    """Empty input reaches this command through stdin, not as an empty argument.

    `elif args.text:` treats an empty string as absent and falls through to stdin — the same
    convention `untell humanize` uses, so `main([""])` blocks on a read rather than reporting empty
    input. That is repo-wide behaviour and a pipe is how empty input actually arrives, so the test
    was wrong rather than the code.
    """
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("   \n"))
    code = main(["--max-iters", "1"])
    assert code == 2
    assert "error" in capsys.readouterr().out


def test_the_message_says_what_to_do(capsys):
    """An exit code alone does not tell a user which of the two situations they are in."""
    main([TEXT, "--max-iters", "1", "--best-of", "1"])
    out = capsys.readouterr().out
    assert "API key" in out or "API_KEY" in out, out[:300]
    assert "cannot prove" in out, out[:300]


def test_a_failing_verdict_still_exits_one(monkeypatch, capsys):
    """The distinction is only worth anything if the other branch keeps its own code."""
    import eval.prove as prove_module

    monkeypatch.setattr(
        prove_module,
        "prove",
        lambda *a, **k: {
            "before": {"configured": ["x"], "results": {}, "n_passing": 0, "n_configured": 1},
            "after": {"configured": ["x"], "results": {}, "n_passing": 0, "n_configured": 1},
            "passes_all": False,
            "iterations": 1,
            "humanized": "text",
        },
    )
    code = main([TEXT, "--max-iters", "1", "--json"])
    capsys.readouterr()
    assert code == 1, "checkers ran and the text failed — that is a verdict, not a setup problem"


def test_a_passing_verdict_exits_zero(monkeypatch, capsys):
    import eval.prove as prove_module

    monkeypatch.setattr(
        prove_module,
        "prove",
        lambda *a, **k: {
            "before": {"configured": ["x"], "results": {}, "n_passing": 1, "n_configured": 1},
            "after": {"configured": ["x"], "results": {}, "n_passing": 1, "n_configured": 1},
            "passes_all": True,
            "iterations": 1,
            "humanized": "text",
        },
    )
    code = main([TEXT, "--max-iters", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["passes_all"] is True
