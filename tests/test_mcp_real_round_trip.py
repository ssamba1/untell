"""Real MCP round-trip through the ACTUAL FastMCP engine — no mock.

`test_every_mcp_tool_runs.py` asserts each tool returns a dict by calling the captured
functions directly; `test_mcp_server.py` asserts registration against a fake FastMCP.
Neither ever hands a call to the real engine. The `compare` tool shipped with a
`TypeError: missing 1 required positional argument: 'texts'` that survived BOTH of those
files, because registration and dict-returning are exactly what a broken tool still does.

This file lives SEPARATELY on purpose: the module-scope fixture in
`test_every_mcp_tool_runs.py` installs `_FakeFastMCP` into ``sys.modules`` for the whole
module lifetime, which would shadow the real engine in the same process. The only judge
of whether registration, argument validation, call machinery and response formatting
line up is the real engine, in a process where nothing has mocked it.
"""

from __future__ import annotations

import asyncio
import json

import pytest

mcp = pytest.importorskip("mcp")  # declared optional dependency ([project.optional-dependencies].mcp)

from untell.mcp_server import _server  # noqa: E402  (after importorskip)


@pytest.mark.parametrize(
    "name,args,required_keys",
    [
        ("tells", {"text": "Furthermore, in conclusion, the data clearly shows a trend."}, {"tells", "words"}),
        ("score", {"text": "This is a perfectly ordinary sentence about nothing in particular.", "tier": "lite"}, {"max", "ai_percent"}),
        ("sentences", {"text": "This is one sentence. And this is another one.", "tier": "lite"}, {"sentences", "flagged"}),
    ],
)
def test_a_real_round_trip_through_the_actual_fastmcp_engine(name, args, required_keys):
    """Drive the REAL server through the REAL FastMCP call machinery.

    `call_tool` is the actual path a client's request travels: registration lookup,
    argument validation, coroutine dispatch, and response formatting into TextContent.
    A mock can agree with the code that wrote it; the real engine cannot.
    """

    async def _round_trip():
        srv = _server()
        return await srv.call_tool(name, args)

    result = asyncio.run(_round_trip())
    assert result, "call_tool returned nothing"
    assert all(hasattr(item, "text") for item in result), (
        f"expected TextContent items, got {type(result[0]).__name__}"
    )
    payload = json.loads(result[0].text)
    missing = sorted(required_keys - set(payload))
    assert not missing, f"real engine payload for {name} lacks {missing}: {result[0].text[:160]}"
