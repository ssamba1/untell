"""A caller who expected the hosted rewriter and got `composite` must learn it from the result.

The argument was already in the file, twelve lines below the branch that ignored it. The
voice-sample block says:

    "`untell humanize --voice-sample` warns about exactly this on stderr; REST and MCP take the
     sample as TEXT and said nothing, so the two network surfaces silently used a sample the CLI
     would have flagged."

— and sets `voice_warning` on the result. The free-rewriter fallback directly above it made the same
argument in its own comment ("silently substituting a weaker backend is the failure this repo keeps
finding on other surfaces") and kept only the stderr half. `_WARNED_FREE_FALLBACK` is a module
global, so a long-running server logs it for its first request and no caller after that hears
anything at all.

`rewriter_warning` mirrors `voice_warning`: same shape, same placement, kept separate from `warning`
because it is about which BACKEND ran rather than how to read the numbers.

The log line and the field read one constant, `FREE_FALLBACK_WARNING`. Two copies of a caveat
drifting apart is a defect this repo has found more than once.
"""

from __future__ import annotations

import logging

import pytest

import untell.scripts.run as run_module
from untell.scripts.run import FREE_FALLBACK_WARNING, untell_text

TEXT = (
    "It is worth noting that this pivotal approach leverages a robust framework for delivery "
    "today, and the comprehensive solution underscores a seamless outcome for every stakeholder."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def _no_configured_rewriter(monkeypatch):
    """`get_rewriter()` with no argument answers "is a hosted or local-policy backend configured".
    None is the honest answer on a keyless install and is what triggers the fallback."""
    real = run_module.get_rewriter
    monkeypatch.setattr(
        run_module, "get_rewriter", lambda *a, **k: None if not (a or k) else real(*a, **k)
    )


def test_the_fallback_is_reported_on_the_result(_no_configured_rewriter) -> None:
    result = untell_text(TEXT, tier="lite", max_iters=1, best_of=1)
    assert result.get("rewriter_warning") == FREE_FALLBACK_WARNING


def test_every_call_reports_it_not_just_the_first(_no_configured_rewriter, monkeypatch) -> None:
    """The defect. The stderr line is once per process by design; the field must not inherit that,
    or a server tells its first request and nobody else."""
    monkeypatch.setattr(run_module, "_WARNED_FREE_FALLBACK", True)  # as if already logged
    for _ in range(3):
        assert "rewriter_warning" in untell_text(TEXT, tier="lite", max_iters=1, best_of=1)


def test_an_explicit_rewriter_is_not_a_substitution() -> None:
    """Guards the guard. Asking for `composite` and getting it is not a fallback, and a caveat on
    every run is a caveat nobody reads."""
    result = untell_text(TEXT, tier="lite", max_iters=1, best_of=1, rewriter="composite")
    assert "rewriter_warning" not in result


def test_the_log_and_the_field_are_one_string() -> None:
    import inspect

    source = inspect.getsource(run_module._warn_free_rewriter_fallback)
    assert "FREE_FALLBACK_WARNING" in source
    assert "no hosted or local-policy" not in source, "the text must not be duplicated here"


def test_the_rest_surface_documents_it() -> None:
    pytest.importorskip("fastapi")
    from untell.api_server import app

    schema = (
        app.openapi()["paths"]["/humanize"]["post"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )
    assert "rewriter_warning" in schema.get("properties", {})
