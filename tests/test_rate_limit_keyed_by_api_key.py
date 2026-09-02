"""Rate-limit buckets are keyed by the caller's API key.

api_server.py:496: `_rate_limited(request, x_key or auth or "")` — a caller
with an X-API-Key gets a bucket keyed by THEIR key, so two clients don't share
a budget. The mutation or -> and turns the chain into `x_key and auth and ""`,
which always evaluates to "" (or a falsy operand): every credentialed caller
lands in the anonymous bucket, so one client's flood throttles all others.
Pinned by capturing the credential passed to _rate_limited.
"""

import pytest

# `import fastapi` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[server]'`
# to run it.
pytest.importorskip("fastapi")
import os

import pytest
from fastapi.testclient import TestClient

import untell.api_server as api_server  # noqa: E402


@pytest.fixture(autouse=True)
def _api_key_env():
    """Set the key for this test and REMOVE it afterwards.

    The key used to be set at MODULE level, which runs at collection time — before any test in
    the process — and nothing removed it. MEASURED: running this file alongside
    test_the_openapi_schema_matches_the_response.py failed 14 of that file's tests (every keyless
    request got 401: `AssertionError: /tells -> 401`), and alongside the error-path file every
    endpoint answered 401 instead of its 4xx. Order-dependent suite failures are the worst kind:
    green alone, red together. `_api_key()` is read per request, so nothing here needs the
    variable at import time.
    """
    previous = os.environ.get("UNTELL_API_KEY")
    os.environ["UNTELL_API_KEY"] = "secret"
    yield
    if previous is None:
        os.environ.pop("UNTELL_API_KEY", None)
    else:
        os.environ["UNTELL_API_KEY"] = previous


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
