"""Shared fixtures.

`stdlib_lite` exists because three tests assert numbers that are only true of the pure-Python
lite scorer, and they were reading that path out of the ambient environment instead of asking for
it. They passed locally with UNTELL_LITE_NO_TORCH=1 exported and failed under a plain `pytest` on
a machine with torch installed — which is exactly what CI's full-tier job runs.

Deliberately opt-in rather than autouse. Forcing the stdlib path for the whole suite would hide
the torch-backed scorer from every test that should be exercising it.
"""

from __future__ import annotations

import os

import pytest

# Environment variables that change what the detectors DO, and therefore what a numeric assertion
# about them means. Printed at session start so a failure is never read without them.
#
# This exists because I read two failures and reached the wrong conclusion. A file asserting
# full-tier separation failed twice, deterministically, in a file with no connection to the change I
# had just made — and its own messages said the documented measurement must be stale. It was not:
# `UNTELL_DISABLE_MAGE=1` removes a member of the full ensemble, which lowers the human side of the
# per-sentence scores further than the AI side, improves separation, and fires the two assertions
# that pin that file's finding. With the complete ensemble it passes 5/5.
#
# MEASURED afterwards across the suite: 26 files score at full or heavy tier, 14 of them assert a
# numeric threshold, and before this session 1 guarded on ensemble completeness. The header does not
# fix that. It makes the one fact needed to interpret a failure impossible to miss, which is what was
# actually absent — the variable was set in every command I ran and appeared in none of the output.
_SCORING_ENV = (
    "UNTELL_DISABLE_MAGE",
    "UNTELL_LITE_NO_TORCH",
    "UNTELL_ENABLE_RADAR",
    "UNTELL_ENABLE_LOCAL_JUDGE",
    "UNTELL_TIER",
    "UNTELL_THRESHOLD",
)


def _active_scoring_env() -> list[str]:
    return [f"{name}={os.environ[name]}" for name in _SCORING_ENV if os.environ.get(name)]


def pytest_report_header(config) -> list[str] | None:
    """Name any ambient setting that changes scoring, or say that none is set."""
    active = _active_scoring_env()
    if not active:
        return ["untell scoring env: none set (complete ensemble)"]
    return [
        "untell scoring env: " + ", ".join(active),
        "  numeric full-tier assertions are properties of the COMPLETE ensemble; a reduced one "
        "moves them",
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Repeat it at the end, where the failures are, and where `-q` cannot hide it.

    `pytest_report_header` is suppressed by `-q` — which is what CI runs and what every command in
    this repository's docs uses, so the header alone would be a note nobody reads. This one prints
    only when a setting is actually active, so a clean environment stays silent.
    """
    active = _active_scoring_env()
    if not active:
        return
    terminalreporter.write_line("")
    terminalreporter.write_line(
        "untell scoring env: " + ", ".join(active), yellow=True, bold=True
    )
    terminalreporter.write_line(
        "  a reduced ensemble moves every numeric full-tier figure — check this before "
        "concluding a measurement is stale"
    )


@pytest.fixture
def stdlib_lite(monkeypatch):
    """Pin the lite tier to its pure-Python implementation for the duration of one test."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.scripts import score as score_mod

    for name in ("score_text", "batch_score_texts"):
        fn = getattr(score_mod, name, None)
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()
    yield
    for name in ("score_text", "batch_score_texts"):
        fn = getattr(score_mod, name, None)
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()
