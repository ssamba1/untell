"""Every REST route must answer, and `/scrub` had no test at all.

The MCP surface shipped a tool that raised on every call while being registered, advertised and
documented. This is the same kind of surface with a worse failure mode — an HTTP 500 to whoever
sent the text — so the same plain question is asked of it: does each route run?

MEASURED, all eight answer 200 with valid input, and invalid input is refused with 422 rather than
crashing: an unknown tier, an out-of-range threshold, a negative max_iters, an unknown style, and a
body with no text at all.

Coverage in tests/test_api_server.py, counted per route:

    /score 23   /humanize 18   /tells 10   /ceiling 8   /verify 7   /sentences 5   /health 4
    /scrub 0

`/scrub` is the endpoint that strips watermark characters — the one a user reaches for when they
suspect their text carries something — and nothing exercised it over HTTP.

The parametrisation runs over the routes the app ACTUALLY registers, with a guard that each has a
request body here. A route added later without an entry fails that guard rather than being quietly
uncovered, which is how `/scrub` came to be the gap.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

from fastapi.testclient import TestClient  # noqa: E402

from untell.api_server import app  # noqa: E402

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)

# Cheapest valid request per route. `None` means GET.
REQUESTS: dict[str, dict | None] = {
    "/health": None,
    "/score": {"text": TEXT, "tier": "lite"},
    "/tells": {"text": TEXT},
    "/sentences": {"text": TEXT, "tier": "lite"},
    "/scrub": {"text": TEXT},
    "/humanize": {"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
    "/verify": {"text": TEXT, "tier": "lite"},
    "/ceiling": {"tier": "lite", "n": 1, "max_iters": 1, "best_of": 1},
}

DOCS = {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}


@pytest.fixture(scope="module")
def client(monkeypatch_session=None):
    import os

    os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
    return TestClient(app, raise_server_exceptions=False)


def _routes() -> set[str]:
    return {r.path for r in app.routes if getattr(r, "methods", None)} - DOCS


def test_every_route_has_a_request_here():
    """The guard. A new route with no entry is uncovered, and uncovered is how /scrub shipped."""
    missing = sorted(_routes() - set(REQUESTS))
    assert not missing, (
        f"{missing} registered on the REST surface with no request in this file, so nothing "
        "checks they answer. Add an entry rather than deleting this assertion."
    )


@pytest.mark.parametrize("path", sorted(REQUESTS))
def test_the_route_answers(client, path: str):
    if path not in _routes():
        pytest.skip(f"{path} is no longer registered")

    body = REQUESTS[path]
    response = client.get(path) if body is None else client.post(path, json=body)

    assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text[:200]}"
    assert response.json(), f"{path} answered 200 with an empty body"


def test_the_scrub_route_actually_scrubs(client):
    """The untested one, tested for what it is for rather than only for a 200."""
    dirty = "he​llo wor​ld here"
    response = client.post("/scrub", json={"text": dirty})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "​" not in payload["clean"], payload
    assert payload["clean"] == "hello world here"
    assert payload["hidden_chars_removed"], "scrubbed the text but reported nothing removed"


@pytest.mark.parametrize(
    "path,body",
    [
        ("/score", {"text": TEXT, "tier": "turbo"}),
        ("/score", {"text": TEXT, "threshold": 5.0}),
        ("/score", {}),
        ("/humanize", {"text": TEXT, "max_iters": -3}),
        ("/humanize", {"text": TEXT, "style": "pirate"}),
    ],
)
def test_bad_input_is_refused_rather_than_crashing(client, path: str, body: dict):
    """A 500 is the failure mode this surface has that MCP does not."""
    response = client.post(path, json=body)
    assert 400 <= response.status_code < 500, (
        f"{path} with {body} returned {response.status_code}: {response.text[:200]}"
    )
