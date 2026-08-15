"""A malformed payload must answer 422, not 500 — even when the offending value is NaN/Infinity.

Fuzz-found: Python's `json.loads` (which the request parser uses) accepts the
RFC-invalid literals NaN and Infinity, and a rejected value is echoed back inside the
validation error detail. starlette's JSONResponse then dies serialising it —
`json.dumps` cannot encode a non-finite float — so the 422 became a 500 on every
endpoint with a bounded float field:

    POST /score  {"text": "hello", "threshold": NaN}      -> 500 Internal Server Error
    POST /tells  {"text": "hello", "threshold": NaN}      -> 500 Internal Server Error
    POST /verify {"text": "hello", "threshold": Infinity} -> 500 Internal Server Error
    POST /sentences ...                                   -> 500 Internal Server Error
    POST /humanize {"threshold": NaN, ...}                -> 500 Internal Server Error

A 500 hides what was wrong and trips every client-side retry policy. The refusal the
range constraints were built for must actually render.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from untell.api_server import app  # noqa: E402


def _client():
    from fastapi.testclient import TestClient

    # raise_server_exceptions=False: the wrapper surfaces the same status a real HTTP client
    # would see instead of re-raising the server exception in the test process.
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "endpoint,body",
    [
        ("/score", b'{"text": "hello world", "tier": "lite", "threshold": NaN}'),
        ("/score", b'{"text": "hello world", "tier": "lite", "threshold": Infinity}'),
        ("/score", b'{"text": "hello world", "tier": "lite", "threshold": 1e999}'),
        ("/score", b'{"text": "hello world", "tier": "lite", "max_iters": NaN}'),
        ("/score", b'{"text": "hello world", "tier": "lite", "detector_thresholds": {"mage": NaN}}'),
        ("/tells", b'{"text": "hello world", "threshold": NaN}'),
        ("/verify", b'{"text": "hello world", "threshold": Infinity}'),
        ("/sentences", b'{"text": "hello world", "tier": "lite", "threshold": NaN}'),
        ("/humanize", b'{"text": "hello world", "tier": "lite", "rewriter": "surgical", "threshold": NaN}'),
        ("/humanize", b'{"text": "hello world", "tier": "lite", "rewriter": "surgical", "max_iters": 1e999}'),
    ],
)
def test_nonfinite_payload_is_422_not_500(endpoint, body):
    resp = _client().post(endpoint, content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 422, (
        f"{endpoint} {body[:60]!r} -> {resp.status_code} {resp.text[:100]}"
    )


def test_the_422_body_itself_is_valid_json():
    """The refusal must render: the sanitised detail parses, and names the offending field."""
    resp = _client().post(
        "/score",
        content=b'{"text": "hello world", "tier": "lite", "threshold": NaN}',
        headers={"Content-Type": "application/json"},
    )
    data = resp.json()
    assert data["detail"], "expected at least one validation error"
    locs = [tuple(e.get("loc", ())) for e in data["detail"]]
    assert ("body", "threshold") in locs