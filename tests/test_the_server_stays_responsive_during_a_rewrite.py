"""An 11-second rewrite served zero health checks.

Every endpoint is `async def` and used to call its blocking worker DIRECTLY, so the work ran on the
event loop and nothing else could be served until it returned. MEASURED against an 11.20s
/humanize with /health polled every 20ms throughout:

    before          during          after
    2 responses     0 responses     1 response

A liveness probe with any timeout under eleven seconds fails, and an orchestrator acting on that
restarts the process mid-request. After offloading the workers with `asyncio.to_thread`: 324
responses DURING, longest gap 0.08s.

Per-call LATENCY cannot detect this, and the first attempt to measure it used exactly that
statistic. A blocked loop makes the polls queue and then complete quickly once the rewrite returns,
which reads as a healthy 2.8ms median — the number that looks like success. What separates the two
cases is WHEN each response lands relative to the rewrite, so that is what this asserts.

This does not make concurrent rewrites parallel. `untell_text` holds a process-wide lock around its
seeded region, because it seeds the global `random` module, so two rewrites still serialise — they
now serialise off the event loop instead of on it. Offloading before that lock existed would have
traded a blocked server for irreproducible output, which is why the two changes are adjacent.
"""

from __future__ import annotations

import asyncio
import time

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

import httpx  # noqa: E402

AI_PARAGRAPH = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder involved. Furthermore, it underscores the pivotal integration of "
    "modern methodologies across the entire landscape of the discipline."
)
LONG = " ".join([AI_PARAGRAPH] * 4)


@pytest.fixture
def client_app(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.delenv("UNTELL_API_KEY", raising=False)
    from untell.api_server import app

    return app


async def _run_probe(app, payload: dict) -> tuple[int, int, float]:
    """Return (health responses during the call, total, rewrite seconds)."""
    # Boot the app the way uvicorn boots it. ASGITransport never runs the lifespan, so without
    # this the probe measures a server that never started: the first /health pays the cold
    # detector-stack import (~4.3s measured) INSIDE the rewrite window, zero polls land, and the
    # test reports a blocked loop that isn't blocked. In production uvicorn blocks connections
    # until lifespan completes, so a probe always sees a warm /health. Model that here.
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://probe") as client:
            stamps: list[float] = []
            stop = False

            async def poll() -> None:
                while not stop:
                    r = await client.get("/health")
                    assert r.status_code == 200
                    stamps.append(time.perf_counter())
                    await asyncio.sleep(0.02)

            task = asyncio.create_task(poll())
            await asyncio.sleep(0.05)  # let polling establish before the work starts
            started = time.perf_counter()
            resp = await client.post("/humanize", json=payload, timeout=300.0)
            finished = time.perf_counter()
            stop = True
            await task

            assert resp.status_code == 200, resp.text[:300]
            during = [s for s in stamps if started < s < finished]
            return len(during), len(stamps), finished - started


def test_health_is_served_while_a_rewrite_runs(client_app) -> None:
    payload = {"text": LONG, "tier": "lite", "max_iters": 3, "best_of": 3, "threshold": 0.001}
    during, total, seconds = asyncio.run(_run_probe(client_app, payload))

    assert seconds > 0.5, (
        f"the rewrite finished in {seconds:.2f}s, too fast to prove anything about blocking; "
        f"the fixture needs to be longer or slower"
    )
    assert during > 2, (
        f"only {during} of {total} health responses landed during a {seconds:.2f}s rewrite — the "
        f"event loop is blocked, so a liveness probe shorter than that fails"
    )


def test_the_poll_itself_works_when_nothing_is_running(client_app) -> None:
    """Guards the guard. If /health were simply broken or the poller never scheduled, the test
    above would fail for a reason that has nothing to do with blocking."""

    async def idle() -> int:
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://probe") as client:
            n = 0
            deadline = time.perf_counter() + 0.5
            while time.perf_counter() < deadline:
                r = await client.get("/health")
                assert r.status_code == 200
                n += 1
                await asyncio.sleep(0.02)
            return n

    assert asyncio.run(idle()) > 2
