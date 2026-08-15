"""Rate-limit buckets are keyed by the caller's API key.

api_server.py:496: `_rate_limited(request, x_key or auth or "")` — a caller
with an X-API-Key gets a bucket keyed by THEIR key, so two clients don't share
a budget. The mutation or -> and turns the chain into `x_key and auth and ""`,
which always evaluates to "" (or a falsy operand): every credentialed caller
lands in the anonymous bucket, so one client's flood throttles all others.
Pinned by capturing the credential passed to _rate_limited.
"""
import os

from fastapi.testclient import TestClient

os.environ["UNTELL_API_KEY"] = "secret"

import untell.api_server as api_server  # noqa: E402


def test_rate_limit_keyed_by_api_key():
    captured = []
    original = api_server._rate_limited

    def spy(request, credential):
        captured.append(credential)
        return original(request, credential)

    api_server._rate_limited = spy
    client = TestClient(api_server.app)
    try:
        resp = client.post(
            "/score",
            json={"text": "hello world this is text", "tier": "lite"},
            headers={"X-API-Key": "secret"},
        )
    finally:
        api_server._rate_limited = original
    assert resp.status_code == 200
    assert captured == ["secret"], f"bucket must be keyed by the caller key, got {captured!r}"
