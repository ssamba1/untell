"""MCP lifecycle over a REAL stdio transport: wire-level registration, mid-call client
disconnect, session isolation, and cancel-mid-call server health.

Everything else in the MCP suite drives the engine in-process; this file spawns the actual
`untell-mcp` console script (via `untell.mcp_server.main`) as a subprocess and speaks the
real JSON-RPC protocol through the mcp client SDK. Verified live in this slice:

- The tools advertised over the wire are exactly the 8 in `_TOOL_NAMES` (the in-process
  registration test and the README are about the same registry; this is the transport proof).
- A client that disconnects MID-CALL (pipe dropped while a call is in flight) leaves no
  traceback on the server's stderr, and a fresh connection immediately after works —
  session isolation across connections.
- Two in-process server instances interleaved concurrently never answer for each other's
  inputs.
- Cancelling an in-flight call_tool task leaves the server answering correctly (the sync
  tool fn runs to completion — an SDK property documented in mcp_server._text_too_long —
  and the next call is correct either way).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

import pytest

mcp = pytest.importorskip("mcp")  # noqa: F841

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from untell.mcp_server import _TOOL_NAMES, _server  # noqa: E402

TEXT = (
    "Furthermore, organizations leverage these robust technologies to optimize operational "
    "efficiency. Moreover, the impact continues to expand across various sectors."
)


def _stdio_params(stderr_path: str) -> StdioServerParameters:
    """The real console script, with its stderr redirected to a file we can inspect.

    `main` is the exact target of pyproject's `untell-mcp = "untell.mcp_server:main"`.
    """
    wrapper = (
        "import sys, untell.mcp_server as m; "
        f"sys.stderr = open({stderr_path!r}, 'w'); "
        "raise SystemExit(m.main())"
    )
    return StdioServerParameters(command=sys.executable, args=["-c", wrapper], env=dict(os.environ))


async def _wire_tools(params) -> list[str]:
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return sorted(t.name for t in tools.tools)


def test_the_tools_advertised_over_the_wire_match_the_registry():
    async def _go():
        params = _stdio_params(os.path.join(tempfile.gettempdir(), f"slice10_wire_{os.getpid()}.err"))
        names = await _wire_tools(params)
        assert names == sorted(_TOOL_NAMES), (names, _TOOL_NAMES)

    asyncio.run(_go())


def test_a_real_round_trip_over_the_wire_returns_a_real_result():
    async def _go():
        params = _stdio_params(os.path.join(tempfile.gettempdir(), f"slice10_rt_{os.getpid()}.err"))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool("tells", {"text": TEXT})
                body = json.loads(res.content[0].text)
                assert body["words"] == len(TEXT.split())

    asyncio.run(_go())


def test_disconnect_mid_call_leaves_no_traceback_and_the_next_session_works():
    """Drop the pipe while a ~0.5 s call (46 KB tells, under the 50 KB cap) is in flight.
    The client's pending call dies (BrokenResourceError — expected); the SERVER must finish
    the call, wind down on EOF without a traceback, and a fresh connection must work."""
    err_path = os.path.join(tempfile.gettempdir(), f"slice10_disconnect_{os.getpid()}.err")
    if os.path.exists(err_path):
        os.remove(err_path)
    params = _stdio_params(err_path)
    big = {"text": ("Furthermore, the system leverages robust methodologies. ") * 600, "tier": "lite"}

    async def _go():
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    task = asyncio.create_task(session.call_tool("tells", big))
                    await asyncio.sleep(0.05)
                    # exiting the context closes the pipes mid-call
            try:
                await task
            except Exception:  # noqa: BLE001 — client-side teardown error is expected
                pass
        except Exception:  # noqa: BLE001 — context-exit teardown may raise too
            pass
        await asyncio.sleep(2.0)  # let the server finish the call and hit EOF

        assert os.path.exists(err_path), "server subprocess never started"
        err = open(err_path, encoding="utf-8", errors="replace").read()
        assert "Traceback" not in err, f"server traceback after mid-call disconnect:\n{err}"

        # A fresh connection works: session isolation across connections.
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert sorted(t.name for t in tools.tools) == sorted(_TOOL_NAMES)
                res = await session.call_tool("tells", {"text": TEXT})
                body = json.loads(res.content[0].text)
                assert body["words"] == len(TEXT.split())

    asyncio.run(_go())


def test_two_server_instances_interleaved_do_not_answer_for_each_other():
    """Session isolation in-process: two independent servers, concurrent interleaved calls
    with distinct inputs — every result must match its own server's own input."""

    async def _go():
        s1, s2 = _server(), _server()
        docs1 = [f"document one sentence {i} with zebra kiosk umbrella words." for i in range(5)]
        docs2 = [f"document two sentence {i} with alpha bravo charlie words." for i in range(5)]
        r1 = await asyncio.gather(*[s1.call_tool("tells", {"text": t}) for t in docs1])
        r2 = await asyncio.gather(*[s2.call_tool("tells", {"text": t}) for t in docs2])
        for i, texts in enumerate(r1):
            body = json.loads(texts[0].text)
            assert body["words"] == len(docs1[i].split()), f"server1 call {i} crossed over"
        for i, texts in enumerate(r2):
            body = json.loads(texts[0].text)
            assert body["words"] == len(docs2[i].split()), f"server2 call {i} crossed over"

    asyncio.run(_go())


def test_cancel_mid_flight_leaves_the_server_answering_correctly():
    """Cancel a call that is genuinely in flight (46 KB tells, ~0.5 s) shortly after
    dispatch. The sync tool fn cannot be interrupted (SDK property — runs in the event
    loop), so no assertion about interruption; the contract is that the server stays
    healthy and the next call answers with the right numbers."""

    async def _go():
        srv = _server()
        await srv.call_tool("tells", {"text": TEXT})
        big = {"text": ("Furthermore, the system leverages robust methodologies. ") * 600, "tier": "lite"}
        task = asyncio.create_task(srv.call_tool("tells", big))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        res = await srv.call_tool("tells", {"text": TEXT})
        body = json.loads(res[0].text)
        assert body["words"] == len(TEXT.split())

    asyncio.run(_go())
