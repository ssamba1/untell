"""A wildcard origin must never be paired with credentials.

`allow_origins=["*"]` with `allow_credentials=True` is the combination the CORS spec forbids, and
Starlette implements the forbidden case by REFLECTING the request's Origin header rather than
sending `*` — because `*` is invalid alongside credentials. Reflection means any page the user is
visiting can call this server cross-origin with credentials attached and read the response.

This server ships an `UNTELL_API_KEY` auth path and runs on localhost by default, so that is a
browser tab away from someone else's text.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from fastapi.testclient import TestClient

EVIL = "https://evil.example"
GOOD = "https://good.example"


def _app_with(monkeypatch: pytest.MonkeyPatch, origins: str | None):
    """Reload the module so the env var is read at import time, as it is in production."""
    if origins is None:
        monkeypatch.delenv("UNTELL_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("UNTELL_CORS_ORIGINS", origins)
    for module in [m for m in list(sys.modules) if m.startswith("untell.api_server")]:
        monkeypatch.delitem(sys.modules, module, raising=False)
    import untell.api_server as api_server

    return importlib.reload(api_server).app


def test_the_default_wildcard_does_not_allow_credentials(monkeypatch):
    """The defect: reflected origin plus credentials. The wildcard is fine on its own."""
    response = TestClient(_app_with(monkeypatch, None)).get("/health", headers={"Origin": EVIL})
    assert response.headers.get("access-control-allow-origin") == "*", (
        "a spec-legal wildcard is intended — the server is meant to be callable from a scratch page"
    )
    assert response.headers.get("access-control-allow-credentials") != "true"


def test_the_default_does_not_reflect_the_caller_origin(monkeypatch):
    """Reflection is what makes the pairing exploitable; `*` cannot carry credentials."""
    response = TestClient(_app_with(monkeypatch, None)).get("/health", headers={"Origin": EVIL})
    assert response.headers.get("access-control-allow-origin") != EVIL


def test_an_explicit_origin_gets_credentials(monkeypatch):
    """Guards the guard: a caller who names origins must still be able to use them."""
    response = TestClient(_app_with(monkeypatch, GOOD)).get("/health", headers={"Origin": GOOD})
    assert response.headers.get("access-control-allow-origin") == GOOD
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_an_unlisted_origin_is_refused_when_a_list_is_set(monkeypatch):
    response = TestClient(_app_with(monkeypatch, GOOD)).get("/health", headers={"Origin": EVIL})
    assert response.headers.get("access-control-allow-origin") is None


def test_several_origins_are_accepted(monkeypatch):
    app = _app_with(monkeypatch, f"{GOOD}, https://other.example")
    client = TestClient(app)
    for origin in (GOOD, "https://other.example"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin, origin


def test_credentials_are_never_allowed_alongside_the_wildcard(monkeypatch):
    """The invariant, stated directly against the module's own configuration."""
    for origins in (None, "", "   "):
        app = _app_with(monkeypatch, origins)
        import untell.api_server as api_server

        if api_server._CORS_ORIGINS:  # pragma: no cover - defensive
            continue
        response = TestClient(app).get("/health", headers={"Origin": EVIL})
        assert response.headers.get("access-control-allow-credentials") != "true", origins
