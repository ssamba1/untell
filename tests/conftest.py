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


# The scoring env as the session started, and the modules caught changing it while being imported.
#
# Five test modules once did `os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")` at module level.
# That runs at COLLECTION, so it pinned every module collected after them to the stdlib path, for
# the whole session. CI's full-tier job ran its torch tests with torch silently switched off and
# failed them as `_torch_ready() is False` and `'token_overlap' == 'embedding'`, while its own
# summary line printed the leaked `UNTELL_LITE_NO_TORCH=1` that explained them.
_SESSION_SCORING_ENV: dict[str, str | None] = {}
_COLLECTION_LEAKS: list[str] = []


def _scoring_env_snapshot() -> dict[str, str | None]:
    return {name: os.environ.get(name) for name in _SCORING_ENV}


def _restore_scoring_env(snapshot: dict[str, str | None]) -> list[str]:
    """Put the scoring env back to ``snapshot``; return the ``NAME: before -> after`` diffs undone."""
    changed = []
    for name, value in snapshot.items():
        now = os.environ.get(name)
        if now == value:
            continue
        changed.append(f"{name}: {value!r} -> {now!r}")
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    return changed


def pytest_sessionstart(session) -> None:
    _SESSION_SCORING_ENV.update(_scoring_env_snapshot())


def pytest_collectreport(report) -> None:
    """Name a module that changed the scoring env merely by being imported, and undo it."""
    if not _SESSION_SCORING_ENV or not report.nodeid.endswith(".py"):
        return
    changed = _restore_scoring_env(_SESSION_SCORING_ENV)
    if changed:
        _COLLECTION_LEAKS.append(f"{report.nodeid} ({'; '.join(changed)})")


def pytest_collection_finish(session) -> None:
    if _COLLECTION_LEAKS:
        raise pytest.UsageError(
            "test modules changed the scoring environment at import time, which would apply it "
            "to every module collected after them. Use monkeypatch.setenv in a fixture, or the "
            "`stdlib_lite` fixture:\n  " + "\n  ".join(_COLLECTION_LEAKS)
        )


@pytest.fixture(scope="module", autouse=True)
def _scoring_env_does_not_outlive_its_module():
    """A module that leaves the scoring env changed fails, and the next module starts clean."""
    before = _scoring_env_snapshot()
    yield
    changed = _restore_scoring_env(before)
    if changed:
        pytest.fail(
            "this module left the scoring environment changed after its last test, which applies "
            "it to every module after it: " + "; ".join(changed) + ". Use monkeypatch.setenv.",
            pytrace=False,
        )


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


@pytest.fixture(autouse=True)
def _isolate_score_cache():
    """The per-text score cache must not leak scores between tests.

    The cache is keyed on (text, detector names, tier, threshold), so two tests scoring
    the same string with the same NAMED fake detectors would otherwise share an entry —
    and a fake that changes behaviour between tests (the same name, a different value)
    would silently read the other test's result. Clearing per test keeps every scoring
    test hermetic; the cache is an optimisation, never a contract.
    """
    from untell.scripts import score as _score_mod

    _score_mod._score_cache.clear()
    yield
    _score_mod._score_cache.clear()


# The suite's verify/prove tests were written for a machine with NO commercial keys: their
# premises are "no checkers configured", "this configuration must run nothing". This machine's
# Windows user environment carries STALE commercial keys (originality 422, copyleaks 403 —
# MEASURED), which make verify() run the commercial detectors and flip every one of those
# premises. The keys are real credentials of the user's; they must not leak into test state
# any more than any other ambient secret.
_COMMERCIAL_KEY_VARS = (
    "ORIGINALITY_API_KEY",
    "WINSTON_API_KEY",
    "GPTZERO_API_KEY",
    "SAPLING_API_KEY",
    "ZEROGPT_API_KEY",
    "COPYLEAKS_EMAIL",
    "COPYLEAKS_API_KEY",
)


@pytest.fixture(autouse=True)
def _no_commercial_keys(monkeypatch):
    """Hide the ambient commercial API keys from tests that assume a keyless machine.

    Tests that deliberately exercise the keyed paths set their own (fake) values via
    monkeypatch, so a blanket clear cannot break them.
    """
    for name in _COMMERCIAL_KEY_VARS:
        monkeypatch.delenv(name, raising=False)


def pytest_configure(config):
    """Register the ``soak`` marker used by tests/test_server_soak.py.

    Registered here rather than in pyproject.toml because that file is AMBER
    (touching it demands a queue entry) and a one-line marker registration in the
    suite's own conftest achieves the same without an unknown-marker warning.
    """
    config.addinivalue_line(
        "markers",
        "soak: long-running server soak (500 sequential + 50 parallel REST calls "
        "against a live in-process uvicorn server); deselect with -m 'not soak'",
    )
