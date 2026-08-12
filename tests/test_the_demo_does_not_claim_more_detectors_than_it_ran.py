"""The demo's detector count must be what ran, not the size of the registry.

`untell --demo` step 3 described the closed loop as scoring "against 15 detectors". Fifteen is
`len(all_detectors())` — the number of registered CLASSES. What runs is `load_detectors(tier)`:
five at full, one on the zero-dependency lite path. So the first thing a new user saw on a clean
install claimed fifteen detectors had judged their text when one had.

Guarding the count alone is not enough. `untell humanize` defaults to tier full while the demo
scores at lite unless torch is importable, so a count that is honest about the demo can still be
wrong for the command the demo tells you to paste. Both are pinned here.

The lite path is forced with UNTELL_LITE_NO_TORCH=1 so the assertion does not depend on whether
the machine running the tests happens to have torch — the earlier version of a test in this repo
asserted something that was only true on the torch path and passed for the wrong reason.
"""
from __future__ import annotations

import re

import pytest

from untell.scripts.cli import _run_demo


def _demo_output(monkeypatch, capsys) -> str:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert _run_demo() == 0
    return capsys.readouterr().out


def test_the_demo_does_not_quote_the_registry_size_as_the_run_count(monkeypatch, capsys):
    out = _demo_output(monkeypatch, capsys)
    assert "against 15 detectors" not in out, (
        "the demo is quoting len(all_detectors()) as though every registered class had scored "
        "the text; on this path exactly one detector runs"
    )


def test_the_demo_reports_the_number_of_detectors_that_actually_answered(monkeypatch, capsys):
    out = _demo_output(monkeypatch, capsys)

    match = re.search(r"Score your text against the (\d+) detectors?\b", out)
    assert match, f"step 3 no longer states a detector count:\n{out}"
    claimed = int(match.group(1))

    from untell.scripts.score import score_text

    ran = len(score_text("Furthermore, this is a test of the system.", tier="lite")["detectors"])
    assert ran >= 1
    assert claimed == ran, (
        f"demo claims {claimed} detectors, but tier lite loads {ran}"
    )


def test_the_demo_pins_the_tier_it_measured_in_the_command_it_suggests(monkeypatch, capsys):
    """Otherwise the suggested command runs a different tier than the count describes."""
    out = _demo_output(monkeypatch, capsys)

    suggested = [ln for ln in out.splitlines() if "untell humanize" in ln and "--rewriter" in ln]
    assert suggested, f"demo no longer suggests a humanize command:\n{out}"
    assert "--tier lite" in suggested[0], (
        "the demo scored at lite but hands over a command that defaults to full — pasting it "
        f"runs five detectors against a count that promised one: {suggested[0]!r}"
    )

    assert re.search(r"loads at tier lite\b", out), (
        "the count must name the tier it belongs to; a bare number is true of only one install"
    )


def test_the_singular_is_used_for_a_single_detector(monkeypatch, capsys):
    """A count of one printed as '1 detectors' is the kind of seam that says nobody ran this."""
    out = _demo_output(monkeypatch, capsys)
    assert "the 1 detectors" not in out
    assert "the 1 detector " in out


@pytest.mark.parametrize("claim", ["15 detectors", "15 local detectors"])
def test_no_other_step_of_the_demo_revives_the_fifteen_claim(monkeypatch, capsys, claim):
    out = _demo_output(monkeypatch, capsys)
    assert claim not in out, f"{claim!r} is the registry size, not a run count"
