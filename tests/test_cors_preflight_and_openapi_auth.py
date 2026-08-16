"""Three REST-contract fixes pinned: CORS preflight vs auth, .env CORS origins, OpenAPI auth schemes.

1. CORS preflight (OPTIONS) is exempt from the API-key check. Browsers never send credentials on a
   preflight by spec — the preflight asks whether the real request MAY carry them — so a key check
   there 401s every cross-origin browser caller the moment UNTELL_API_KEY is set, and the
   documented CORS support silently stops working. MEASURED before the fix: OPTIONS /score with
   Origin + Access-Control-Request-Method, UNTELL_API_KEY=secret -> 401, no allow-origin header.
   The CORSMiddleware answers the preflight itself, so the bypass costs nothing and reveals
   nothing: OPTIONS can never reach a route handler.

2. UNTELL_CORS_ORIGINS is honoured when it lives only in .env. The origins are read from the
   environment at module import; lifespan's load_env() runs after import, so a .env-only value
   was invisible. Same bug class `_api_key()` documents and fixes for the auth key (per-request
   read); here load_env() is called at import so the module-level CORS read sees .env.
   MEASURED before the fix: .env with UNTELL_CORS_ORIGINS=https://good.example ->
   `_CORS_ORIGINS == []`, allow-origin `*` after lifespan.

3. The OpenAPI document declares the auth the docs promise. docs/api-server.md documents
   Authorization: Bearer and X-API-Key; the generated schema declared no securitySchemes, so a
   client generated from /openapi.json had no reason to send a key and the /docs UI showed no
   Authorize button. Each protected route now carries the optional form
   [{}, {HTTPBearer: []}, {APIKeyHeader: []}] — anonymous OR either scheme, which is exactly the
   runtime truth (unset key = open access, set key = either header). /health stays unsecured.
"""
from __future__ import annotations

import importlib
import sys

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

from fastapi.testclient import TestClient  # noqa: E402

EVIL = "https://evil.example"
GOOD = "https://good.example"


def _fresh_app(monkeypatch: pytest.MonkeyPatch, *, api_key: str | None = None,
               origins: str | None = None):
    """Reload the module so import-time reads see the patched environment, as in production."""
    if api_key is None:
        monkeypatch.delenv("UNTELL_API_KEY", raising=False)
    else:
        monkeypatch.setenv("UNTELL_API_KEY", api_key)
    if origins is None:
        monkeypatch.delenv("UNTELL_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("UNTELL_CORS_ORIGINS", origins)
    for module in [m for m in list(sys.modules) if m.startswith("untell.api_server")]:
        monkeypatch.delitem(sys.modules, module, raising=False)
    import untell.api_server as api_server

    return importlib.reload(api_server).app


def _preflight(client, path: str = "/score", origin: str = EVIL):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )


def test_preflight_is_not_401_when_a_key_is_configured(monkeypatch):
    app = _fresh_app(monkeypatch, api_key="secret")
    r = _preflight(TestClient(app))
    assert r.status_code == 200, f"preflight must pass without credentials: {r.status_code} {r.text[:120]}"


def test_preflight_still_gets_cors_headers_with_a_key_configured(monkeypatch):
    app = _fresh_app(monkeypatch, api_key="secret")
    r = _preflight(TestClient(app))
    # The wildcard default applies (credentials NOT allowed) — the point is the preflight is
    # answered by the CORS middleware at all.
    assert r.headers.get("access-control-allow-origin") == "*"


def test_preflight_with_explicit_origins_still_works_with_a_key(monkeypatch):
    app = _fresh_app(monkeypatch, api_key="secret", origins=GOOD)
    r = _preflight(TestClient(app), origin=GOOD)
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == GOOD


def test_an_actual_request_still_requires_the_key(monkeypatch):
    app = _fresh_app(monkeypatch, api_key="secret")
    r = TestClient(app).post("/score", json={"text": "hello world this is text", "tier": "lite"})
    assert r.status_code == 401, "the OPTIONS bypass must not weaken the real request's auth"


def test_options_cannot_reach_a_route_handler(monkeypatch):
    """The bypass only skips auth; OPTIONS still matches no route, so no handler logic runs."""
    app = _fresh_app(monkeypatch)  # no key: open access
    r = TestClient(app).options("/score")  # no CORS headers: not a preflight
    assert r.status_code == 405


def test_cors_origins_from_env_file_are_honoured(monkeypatch, tmp_path):
    """UNTELL_CORS_ORIGINS in .env reaches the middleware (the module reads it after load_env)."""
    (tmp_path / ".env").write_text(f"UNTELL_CORS_ORIGINS={GOOD}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UNTELL_CORS_ORIGINS", raising=False)
    for module in [m for m in list(sys.modules) if m.startswith("untell.api_server")]:
        monkeypatch.delitem(sys.modules, module, raising=False)
    import untell.api_server as api_server

    app = importlib.reload(api_server).app
    assert api_server._CORS_ORIGINS == [GOOD], api_server._CORS_ORIGINS
    r = TestClient(app).get("/health", headers={"Origin": GOOD})
    assert r.headers.get("access-control-allow-origin") == GOOD
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_openapi_declares_both_auth_schemes(monkeypatch):
    app = _fresh_app(monkeypatch)
    spec = TestClient(app).get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert set(schemes) == {"HTTPBearer", "APIKeyHeader"}
    assert schemes["HTTPBearer"]["type"] == "http" and schemes["HTTPBearer"]["scheme"] == "bearer"
    assert schemes["APIKeyHeader"] == {"type": "apiKey", "in": "header", "name": "X-API-Key"}


def test_every_protected_route_advertises_optional_auth(monkeypatch):
    app = _fresh_app(monkeypatch)
    spec = TestClient(app).get("/openapi.json").json()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if path == "/health":
                assert op["security"] == [], f"{method.upper()} {path} must stay unsecured"
            else:
                assert op["security"] == [{}, {"HTTPBearer": []}, {"APIKeyHeader": []}], (
                    f"{method.upper()} {path}: anonymous OR either scheme is the runtime truth"
                )
