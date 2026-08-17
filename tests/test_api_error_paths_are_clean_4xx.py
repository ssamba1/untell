"""Every REST endpoint answers a clean 4xx to a hostile body — never a traceback.

A network surface has an untrusted caller, and its error paths are part of the contract: a
malformed payload must come back as a structured 422/404/405, not as a 500 with a Python
traceback a client has to scrape. Probed live on 2026-08-15: every case below already returned a
clean 4xx; these tests pin it so the property cannot quietly rot.

Also pins the "requested free rewriter is unavailable" refusal on /humanize and /ceiling, which
used to fall through to auto-selection — MEASURED with a get_rewriter spy: HTTP 200, no
rewriter_warning, and `get_rewriter()` called with prefer=None, i.e. the paid hosted backend was
silently selected and billed. The MCP tools refuse this case; the REST surface now does too.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

from fastapi.testclient import TestClient  # noqa: E402

from untell.api_server import app  # noqa: E402
from untell.scripts.score import MAX_INPUT_CHARS  # noqa: E402

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency across the evaluated corpus."
)

# Cheapest valid request per POST endpoint (same shapes the OpenAPI staleness test uses).
REQUESTS = {
    "/score": {"text": TEXT, "tier": "lite"},
    "/tells": {"text": TEXT},
    "/sentences": {"text": TEXT, "tier": "lite"},
    "/scrub": {"text": TEXT},
    "/verify": {"text": TEXT, "tier": "lite"},
    "/ceiling": {"tier": "lite", "n": 1, "max_iters": 1, "best_of": 1},
    "/humanize": {"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
}

# The hostile bodies: each must be a 4xx on EVERY endpoint, with a JSON body and no traceback.
HOSTILE_BODIES = {
    "invalid JSON": ({"content": "{not json", "headers": {"content-type": "application/json"}},),
    "text/plain content-type": ({"content": '{"text": "hello"}', "headers": {"content-type": "text/plain"}},),
    "text is an int": ({"json": {"text": 123}},),
    "text is null": ({"json": {"text": None}},),
    "text is a list": ({"json": {"text": ["a", "b"]}},),
    "text is a bool": ({"json": {"text": True}},),
    "no body at all": ({"json": None},),
    "empty object": ({"json": {}},),
    "unknown extra field": ({"json": {"text": TEXT, "nonsense_field": 1}},),
    "oversized text": ({"json": {"text": "x" * (MAX_INPUT_CHARS + 1)}},),
}


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False: a genuine 500 would come back as a response so the
    # assertions below can fail on it instead of the test harness raising inside the handler.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    """This file fires ~90 requests in one process; the in-process 60/min limiter would 429
    the later tests (MEASURED: /humanize and /ceiling assertions got 429s mid-sweep). The
    limiter is read per call, so the env var is a per-test switch."""
    import os

    previous = os.environ.get("UNTELL_RATE_LIMIT")
    os.environ["UNTELL_RATE_LIMIT"] = "0"
    yield
    if previous is None:
        os.environ.pop("UNTELL_RATE_LIMIT", None)
    else:
        os.environ["UNTELL_RATE_LIMIT"] = previous


@pytest.mark.parametrize("path", sorted(REQUESTS))
@pytest.mark.parametrize("label", sorted(HOSTILE_BODIES))
def test_a_hostile_body_is_a_clean_4xx(client, path: str, label: str):
    kwargs = HOSTILE_BODIES[label][0]
    # /ceiling is the one endpoint with no required fields, so `{}` is a VALID request
    # (everything defaults) and would run a real measurement. Substitute an out-of-range
    # field that no valid call can contain: n=0 violates the ge=1 bound.
    if path == "/ceiling" and label == "empty object":
        kwargs = {"json": {"tier": "lite", "n": 0}}
    resp = client.post(path, **kwargs)
    assert 400 <= resp.status_code < 500, (
        f"{path} {label}: expected 4xx, got {resp.status_code}: {resp.text[:200]}"
    )
    assert resp.headers.get("content-type", "").startswith("application/json"), (
        f"{path} {label}: expected a JSON error body, got {resp.headers.get('content-type')}"
    )
    assert "Traceback" not in resp.text and "Error" not in resp.text, (
        f"{path} {label}: error body looks like a traceback: {resp.text[:200]}"
    )
    # The body must parse as JSON — a client reading it does not scrape text.
    resp.json()


def test_an_unknown_route_is_a_clean_404(client):
    resp = client.get("/definitely-not-a-route")
    assert resp.status_code == 404
    assert resp.headers.get("content-type", "").startswith("application/json")
    resp.json()


def test_a_wrong_method_is_a_clean_405(client):
    resp = client.get("/tells")
    assert resp.status_code == 405
    assert resp.headers.get("content-type", "").startswith("application/json")
    resp.json()


class TestRequestedFreeRewriterUnavailable:
    """D3: a free rewriter the install does not have must be a 422, not a silent paid fallback."""

    @pytest.mark.parametrize(
        "path,rewriter",
        [
            ("/humanize", "t5_paraphrase"),
            ("/humanize", "mt_pivot"),
            ("/ceiling", "mt_pivot"),
            ("/ceiling", "t5_paraphrase"),
        ],
    )
    def test_unavailable_free_rewriter_is_refused(self, client, path: str, rewriter: str):
        body = REQUESTS[path] | {"rewriter": rewriter}
        with patch("untell.rewriter.get_rewriter", return_value=None):
            resp = client.post(path, json=body)
        assert resp.status_code == 422, f"{path} {rewriter}: {resp.status_code} {resp.text[:200]}"
        assert "unavailable" in resp.json().get("error", ""), resp.text[:200]
        assert ".[full]" in resp.json().get("error", ""), resp.text[:200]

    def test_an_available_free_rewriter_still_runs(self, client):
        """The guard must not fire when the free backend IS available (composite/surgical)."""
        with patch("untell.api_server.untell_text") as mock_text:
            mock_text.return_value = {
                "final": "ok", "pre": {"max": 0.9}, "post": {"max": 0.2},
                "iterations": 1, "stopped": "passed", "changed": True,
            }
            resp = client.post(
                "/humanize",
                json={"text": TEXT, "tier": "lite", "max_iters": 1, "rewriter": "surgical"},
            )
        assert resp.status_code == 200, resp.text[:200]
