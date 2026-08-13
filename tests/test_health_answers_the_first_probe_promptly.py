"""The first `/health` on a cold process took 9.34 seconds.

`/health` reports the detector tier, and resolving that means calling `available()` on every
detector, which imports and probes the transformer stack. MEASURED on a cold process, no lifespan:

    first  /health   9.34s
    second /health   0.0026s      — 3,636x

The first call is exactly the one an orchestrator makes. Container starts, liveness probe fires,
and a 1-5 second timeout (the common defaults) expires before the answer arrives; the process is
restarted, and restarted again, having never served a request. `/health` was also the one endpoint
not offloaded, so those 9.34s blocked the event loop for everything else too.

Resolved during `lifespan`, off the event loop, before the server accepts traffic. uvicorn does not
accept connections until lifespan completes, so a probe now gets either no connection at all —
unambiguous, and what a startupProbe is for — or a fast answer. Never a slow one. After the change:

    startup (including the warm)   9.33s
    first  /health                 0.0052s
    second /health                 0.0031s

The warm is best-effort. `/tells` and `/scrub` need no detectors, so a broken transformers install
must not stop the server from starting.
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

# Far below the 9.34s this file exists for, and far above the 0.005s measured, so it fails on the
# defect without being a benchmark of the machine it runs on.
_BUDGET_S = 2.0


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("UNTELL_API_KEY", raising=False)
    from untell.api_server import app as _app

    return _app


def test_the_first_health_call_after_startup_is_prompt(app) -> None:
    with TestClient(app) as client:  # entering runs lifespan, which warms
        t0 = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - t0

    assert response.status_code == 200
    assert elapsed < _BUDGET_S, (
        f"the first /health took {elapsed:.2f}s; a liveness probe with a 1-5s timeout fails and "
        f"the container is restarted before it ever serves a request"
    )


def test_health_still_reports_the_detectors(app) -> None:
    """Guards the guard. Answering promptly by dropping the payload would pass the test above and
    remove the thing the endpoint is for."""
    with TestClient(app) as client:
        body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["detector_count"] >= 1
    assert body["detectors"], "no detectors named"
    assert body["detector_tier"]


def test_startup_warms_the_detectors(app, monkeypatch) -> None:
    """The mechanism, not just the timing. A machine fast enough to resolve detectors inside the
    budget would pass the timing test with the warm-up removed."""
    import untell.api_server as mod

    calls = []
    original = mod._warm_detectors

    async def counting():
        calls.append(1)
        await original()

    monkeypatch.setattr(mod, "_warm_detectors", counting)
    with TestClient(mod.app) as client:
        client.get("/health")

    assert calls, "lifespan did not warm the detectors; the first probe pays for it instead"


def test_a_failing_warm_up_does_not_stop_the_server(app, monkeypatch) -> None:
    """`/tells` and `/scrub` need no detectors at all. A user with a broken transformers install
    must still get a server."""
    import untell.api_server as mod

    async def boom():
        raise RuntimeError("simulated broken transformers install")

    monkeypatch.setattr(mod, "_warm_detectors", boom)
    with TestClient(mod.app) as client:
        assert client.post("/tells", json={"text": "Moreover, this is robust."}).status_code == 200
