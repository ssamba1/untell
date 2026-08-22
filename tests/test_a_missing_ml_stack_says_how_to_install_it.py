"""Asking for `--tier full` without torch got advice to ask for `--tier full`.

Issue #51. On a base install the full detectors cannot load, `score_text` falls back to the
stdlib lite path, and the note it attaches ends:

    ...weak evidence in both directions - re-run at --tier full before trusting a flag OR a clear.

which is what the user just did. The chain that picks the note is an if/elif, and the stdlib
branch sits ABOVE the downgrade branch, so it claimed the message first and the only actionable
sentence in the module - how to obtain the full tier - was unreachable for exactly the people who
needed it. `tier_requested=full ran=lite` appeared in the JSON, but nothing said `pip install`.

The measurement in the stdlib note is the part worth keeping, so the fix prepends the instruction
rather than replacing the note. Prepended for the reason `test_the_specific_caveat_comes_first`
records: the standing caveat is wallpaper, and the sentence specific to this run has to come first
or it is not read.

Fakes throughout - a base install cannot be simulated by uninstalling torch inside a test, so the
detector roster is what gets replaced.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts import score as score_mod
from untell.scripts.score import score_text

PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead. "
    "The grit itself does a second job once the ice has gone soft, which matters more on a hill "
    "than it does on the flat, and councils plan their routes around exactly that difference."
)

INSTALL_HINT = "pip install 'untell[full]'"
STDLIB_MARK = "lite tier on the stdlib path"


class _StdlibOnlyDetector:
    """The single detector a base install actually gets: pure-stdlib perplexity/burstiness."""

    name = "perplexity_burstiness"

    def score(self, text: str) -> float:
        return 0.42

    def mode(self) -> str:
        return "stdlib"


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def base_install(monkeypatch):
    """No ML stack: one stdlib detector loads whatever tier is asked for."""
    monkeypatch.setattr(score_mod, "load_detectors", lambda tier: [_StdlibOnlyDetector()])
    monkeypatch.setattr(score_mod, "resolved_tier", lambda live: "lite")


def test_asking_for_full_without_torch_says_how_to_install_it(base_install):
    """The acceptance criterion from #51, stated as an assertion."""
    result = score_text(PROSE, tier="full")

    assert result["tier"] == "lite" and result["tier_requested"] == "full", (
        "premise: this fixture must produce the silent downgrade the issue is about"
    )
    warning = result.get("warning") or ""
    assert INSTALL_HINT in warning, (
        f"a downgraded full-tier run must name the install command; got: {warning[:220]!r}"
    )


def test_the_instruction_comes_before_the_standing_caveat(base_install):
    """A note that arrives 500 characters in is a note nobody reads."""
    warning = score_text(PROSE, tier="full").get("warning") or ""

    assert STDLIB_MARK in warning, "premise: the stdlib measurement must still be there"
    assert warning.index(INSTALL_HINT) < warning.index(STDLIB_MARK), (
        "the instruction specific to this run must precede the standing caveat"
    )


def test_the_measurement_is_not_dropped_to_make_room_for_the_instruction(base_install):
    """Reordering the branches would have been the cheap fix and would have lost this."""
    warning = score_text(PROSE, tier="full").get("warning") or ""

    assert "64% of HUMAN text" in warning
    assert "every miss against a full-tier score of 1.000" in warning


def test_a_deliberate_lite_run_is_not_told_to_install_anything(monkeypatch):
    """Someone who ASKED for lite got what they asked for; an install prompt there is noise.

    This is the branch that makes the fix conditional rather than unconditional, and without it
    the instruction would fire on every lite run in the project - including the ones the README
    tells people to make.
    """
    monkeypatch.setattr(score_mod, "load_detectors", lambda tier: [_StdlibOnlyDetector()])
    monkeypatch.setattr(score_mod, "resolved_tier", lambda live: "lite")

    result = score_text(PROSE, tier="lite")

    assert result["tier"] == result["tier_requested"] == "lite", "premise: no downgrade happened"
    warning = result.get("warning") or ""
    assert STDLIB_MARK in warning, "the standing caveat still applies to a lite run"
    assert INSTALL_HINT not in warning, f"nothing was downgraded: {warning[:200]!r}"


def test_the_names_of_detectors_that_failed_to_load_travel_with_the_instruction(
    base_install, monkeypatch
):
    """Knowing WHICH member died is what turns 'install the extra' into a diagnosis."""

    class _Exploding(_StdlibOnlyDetector):
        name = "roberta_openai"

        def score(self, text: str) -> float:
            raise RuntimeError("no module named torch")

    monkeypatch.setattr(
        score_mod, "load_detectors", lambda tier: [_StdlibOnlyDetector(), _Exploding()]
    )

    warning = score_text(PROSE, tier="full").get("warning") or ""

    assert INSTALL_HINT in warning
    assert "roberta_openai" in warning, f"the failed member is not named: {warning[:220]!r}"
