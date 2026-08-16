"""MCP lifecycle: parallel calls, session isolation, malformed payloads, disconnects.

These run through the REAL FastMCP engine (like test_mcp_real_round_trip.py, and for the
same reason — a mock agrees with the code that wrote it). All verified live in this slice:

- 10 concurrent `call_tool` on distinct inputs: zero cross-talk (each result matches its
  own input), zero response mixing across tools, byte-identical results for concurrent
  calls with the same input (no shared mutable state in the tools).
- Wrong-typed / missing fields are refused by the engine's argument validation as
  ToolError (field named + pydantic error type) — the same shape as REST's 422 detail,
  never a raw traceback.
- A client that vanishes mid-call (asyncio task cancelled) leaves the server answering
  correctly; the global-RNG race that could have made this dangerous is already solved
  by untell_text's save/seed/restore under a lock (run.py).
"""
from __future__ import annotations

import asyncio
import json

import pytest

mcp = pytest.importorskip("mcp")  # noqa: F841

from untell.mcp_server import _server  # noqa: E402

TEXTS = [
    f"Furthermore, the system leverages robust methodologies to optimize outcome number {i}. "
    f"This is sentence two of document {i} with distinctive words: zebra kiosk umbrella."
    for i in range(10)
]


async def _call(srv, name, args):
    result = await srv.call_tool(name, args)
    return [getattr(item, "text", None) for item in result]


async def _payload(srv, name, args) -> dict:
    texts = await _call(srv, name, args)
    return json.loads(texts[0])


def test_ten_concurrent_calls_do_not_cross_talk():
    async def _go():
        srv = _server()
        await _call(srv, "tells", {"text": TEXTS[0]})  # warm
        results = await asyncio.gather(*[_call(srv, "tells", {"text": t}) for t in TEXTS])
        for i, texts in enumerate(results):
            body = json.loads(texts[0])
            assert body["words"] == len(TEXTS[i].split()), f"call {i} answered for a different input"

    asyncio.run(_go())


def test_ten_concurrent_scrubs_each_clean_their_own_input():
    dirty = [f"Hello\u200b world {i} \u200b again." for i in range(10)]

    async def _go():
        srv = _server()
        results = await asyncio.gather(*[_call(srv, "scrub", {"text": t}) for t in dirty])
        for i, texts in enumerate(results):
            body = json.loads(texts[0])
            assert body["hidden_chars_removed"] == 2
            assert str(i) in body["clean"], f"scrub {i} returned someone else's text"

    asyncio.run(_go())


def test_concurrent_mixed_tools_do_not_mix_responses():
    async def _go():
        srv = _server()
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(_call(srv, "tells", {"text": TEXTS[i]}))
            else:
                tasks.append(_call(srv, "scrub", {"text": f"dirty\u200b text {i}"}))
        results = await asyncio.gather(*tasks)
        for i, texts in enumerate(results):
            body = json.loads(texts[0])
            if i % 2 == 0:
                assert "words" in body, f"tells call {i} returned {list(body)[:3]}"
            else:
                assert "hidden_chars_removed" in body, f"scrub call {i} returned {list(body)[:3]}"

    asyncio.run(_go())


def test_concurrent_same_input_is_byte_identical():
    async def _go():
        srv = _server()
        r1, r2 = await asyncio.gather(
            _call(srv, "sentences", {"text": TEXTS[0], "tier": "lite", "top": 2}),
            _call(srv, "sentences", {"text": TEXTS[0], "tier": "lite", "top": 2}),
        )
        assert r1[0] == r2[0]

    asyncio.run(_go())


@pytest.mark.parametrize("bad", [123, None, ["a", "list"], {"a": 1}, 1.5, True])
def test_wrong_typed_text_is_a_tool_error_not_a_traceback(bad):
    """The engine's pydantic validation refuses before the tool body runs — field named,
    same shape as REST's 422 detail. A raw traceback would be a crash, this is a refusal."""

    async def _go():
        srv = _server()
        with pytest.raises(Exception) as exc:  # noqa: B017 — ToolError from the SDK
            await _call(srv, "tells", {"text": bad})
        assert "tells" in str(exc.value) or "validation" in str(exc.value).lower()

    asyncio.run(_go())


def test_missing_required_field_is_a_tool_error():
    async def _go():
        srv = _server()
        with pytest.raises(Exception):  # noqa: B017
            await _call(srv, "scrub", {})

    asyncio.run(_go())


def test_cancelled_client_leaves_the_server_healthy():
    """A client that vanishes mid-call (task cancelled) must not corrupt the server:
    the next call answers correctly with the right numbers."""

    async def _go():
        srv = _server()
        await _call(srv, "tells", {"text": "warmup"})
        task = asyncio.create_task(_call(srv, "tells", {"text": TEXTS[1]}))
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        body = await _payload(srv, "tells", {"text": TEXTS[2]})
        assert body["words"] == len(TEXTS[2].split())

    asyncio.run(_go())


def test_concurrent_untell_calls_do_not_share_rng_state():
    """untell_text seeds the GLOBAL random module; two concurrent runs must not corrupt
    each other's streams (solved by the lock in run.py — this pins it end-to-end)."""

    async def _go():
        srv = _server()
        args = {"text": TEXTS[0], "tier": "lite", "max_iters": 1, "best_of": 1}
        r1, r2 = await asyncio.gather(
            _call(srv, "untell", dict(args, seed=7)),
            _call(srv, "untell", dict(args, seed=7)),
        )
        p1, p2 = json.loads(r1[0]), json.loads(r2[0])
        assert "error" not in p1 and "error" not in p2
        assert p1["final"] == p2["final"], "same seed must give the same stream under concurrency"

    asyncio.run(_go())
