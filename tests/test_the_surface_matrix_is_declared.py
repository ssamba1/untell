"""Which OPERATIONS exist on which surface, declared rather than discovered.

`test_surface_parity.py` checks that a shared operation means the same thing everywhere — same
parameters, same defaults, same vocabularies. It never asked which operations each surface HAS, and
the surfaces had quietly diverged:

    REST only   health
    MCP only    compare, scrub
    both        ceiling, score, sentences, tells, humanize/untell, verify/verify_commercial

`scrub` was the one that cost a caller something. The CLI has `untell-scrub` and the MCP server has a
`scrub` tool; a REST client holding untrusted text had no way to strip hidden characters. Those
characters do not move THIS ensemble — normalised, verified at 0.0000 on both tiers — but the same
text took an external detector from 0.0002 to 0.7900 on those bytes alone. `POST /scrub` closes it.

What remains is declared below with a reason, and the check runs BOTH ways: an operation added to one
surface fails until it is either mirrored or listed, and a listed asymmetry that no longer exists
fails too. A one-directional version of this test is what let `warning` go undocumented on two
endpoints for as long as it did.
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("fastapi")

# MCP and REST spell two operations differently; the pair is the same operation.
ALIASES = {"untell": "humanize", "verify_commercial": "verify"}

# operation -> (surfaces it is on, why it is not on the others)
DECLARED_ASYMMETRIES = {
    "health": (
        {"rest"},
        "a liveness probe for an HTTP server; there is nothing for an MCP client to probe",
    ),
    "compare": (
        {"mcp"},
        "a benchmark harness that runs every technique over a corpus — minutes of compute per "
        "call, which is why /ceiling caps `n` and why this one is not an endpoint at all",
    ),
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _surfaces() -> dict[str, set[str]]:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_surface_parity import _mcp_tools

    from untell.api_server import app

    rest = {p.strip("/") for p in app.openapi()["paths"]}
    mcp = {ALIASES.get(name, name) for name in _mcp_tools()}
    ops: dict[str, set[str]] = {}
    for name in rest | mcp:
        ops[name] = {s for s, v in (("rest", rest), ("mcp", mcp)) if name in v}
    return ops


def test_every_asymmetry_is_declared() -> None:
    ops = _surfaces()
    undeclared = {
        name: sorted(where)
        for name, where in ops.items()
        if len(where) < 2 and name not in DECLARED_ASYMMETRIES
    }
    assert not undeclared, f"operations on one surface only, with no stated reason: {undeclared}"


def test_no_declared_asymmetry_has_quietly_been_fixed() -> None:
    """The other direction. A reason that outlives its call site is the decay this repo keeps
    finding — most recently in an API schema that documented a field the endpoint stopped
    returning."""
    ops = _surfaces()
    stale = {
        name: sorted(ops.get(name, set()))
        for name, (where, _) in DECLARED_ASYMMETRIES.items()
        if ops.get(name, set()) != where
    }
    assert not stale, f"declared asymmetries that no longer match reality: {stale}"


def test_scrub_reached_the_rest_surface() -> None:
    """The gap this file was written for, pinned so it cannot reopen."""
    assert "rest" in _surfaces().get("scrub", set())


def test_the_rest_scrub_agrees_with_the_mcp_one() -> None:
    """Same operation, same answer. Parity is about the result, not the route."""
    from fastapi.testclient import TestClient

    from untell.api_server import app
    from untell.attacks import count_hidden, scrub_hidden

    text = "he​llo wor­ld"
    response = TestClient(app).post("/scrub", json={"text": text})
    assert response.status_code == 200
    assert response.json() == {
        "clean": scrub_hidden(text),
        "hidden_chars_removed": count_hidden(text),
    }
    assert response.json()["hidden_chars_removed"] == 2, "premise: the sample must be dirty"


def test_every_declared_reason_is_a_sentence() -> None:
    """A reason list without reasons is a suppression file."""
    for name, (where, reason) in DECLARED_ASYMMETRIES.items():
        assert where, name
        assert len(reason.split()) >= 8, f"{name}: {reason!r}"
