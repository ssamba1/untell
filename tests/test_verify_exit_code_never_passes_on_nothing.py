"""`untell-verify` exited 0 when no checker ran. Exit 0 means PASS to everything that reads it.

The module docstring promises the opposite:

    "With no commercial keys set it reports that no checkers are configured (and exits non-zero),
     because 'passes all major checkers' cannot be asserted without running against them."

The code said `if not v["results"]: return 0`, commented "the user just got the empty report".
Reproduced: `untell-verify --tier commercial` on a machine with no API keys prints "No checkers
ran." and exits 0 — so a CI job gating on this command is told the text passed every major AI
checker when not one was consulted.

Same family as the defects this repo already guards: `_bypass_rate` counting a `max: 0.0`
placeholder as a pass, and the composite selector reporting a rewrite that never happened.
"""

from __future__ import annotations

import pytest

from untell.scripts.verify import main

HUMAN = (
    "I went down to the shop on Tuesday because we had run out of the good coffee again, "
    "and the woman behind the counter said they had stopped stocking it back in March."
)
AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus."
)


def test_nothing_ran_is_not_a_pass(capsys: pytest.CaptureFixture) -> None:
    """The defect. Commercial tier with no keys configured runs zero checkers."""
    code = main(["--tier", "commercial", AI])
    out = capsys.readouterr().out
    assert "No checkers ran" in out, f"premise: this configuration must run nothing\n{out}"
    assert code != 0, "exit 0 tells CI the text passed checkers that never ran"


def test_nothing_ran_is_distinguishable_from_a_failure(capsys: pytest.CaptureFixture) -> None:
    """2, not 1. A caller may reasonably respond to 1 by rewriting; nothing ran is a configuration
    problem, not a verdict about the text, and conflating them sends someone to rewrite text that
    was never checked."""
    assert main(["--tier", "commercial", AI]) == 2
    capsys.readouterr()


def test_a_real_failure_still_exits_one(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert main(["--tier", "lite", AI]) == 1
    assert "FAILS" in capsys.readouterr().out


def test_a_real_pass_still_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Guards the guard: if nothing can exit 0, the command is useless."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    code = main(["--tier", "lite", "--threshold", "0.99", HUMAN])
    capsys.readouterr()
    assert code == 0


def test_the_three_codes_are_distinct(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """pass / fail / nothing-ran must not collide, or a caller cannot tell them apart."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    codes = {
        "pass": main(["--tier", "lite", "--threshold", "0.99", HUMAN]),
        "fail": main(["--tier", "lite", AI]),
        "nothing": main(["--tier", "commercial", AI]),
    }
    capsys.readouterr()
    assert len(set(codes.values())) == 3, codes
