"""Probe v2: real stdio transport — mid-call disconnect; server stderr + second session."""
import asyncio
import json
import os
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TEXT = (
    "Furthermore, organizations leverage these robust technologies to optimize operational "
    "efficiency. Moreover, the impact continues to expand across various sectors."
)

ERR = os.path.join(tempfile.gettempdir(), "slice10_srv.err")


def make_params():
    # Wrapper that redirects the server's stderr to a file so we can inspect it after a
    # disconnect. `main` is the real console-script entry point (untell-mcp).
    wrapper = (
        "import sys, untell.mcp_server as m; "
        f"sys.stderr = open({ERR!r}, 'w'); "
        "raise SystemExit(m.main())"
    )
    return StdioServerParameters(command=sys.executable, args=["-c", wrapper])


async def full_session(params, label, do_call=True):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            if do_call:
                res = await session.call_tool("tells", {"text": TEXT})
                body = json.loads(res.content[0].text)
                print(f"{label}: tools={names} call_words={body.get('words')}")
            else:
                print(f"{label}: tools={names}")
            return names


async def main():
    params = make_params()
    if os.path.exists(ERR):
        os.remove(ERR)

    await full_session(params, "SESSION1")

    # Mid-call disconnect: start a call on 46KB (0.5s), drop the pipe while it runs.
    big = {"text": ("Furthermore, the system leverages robust methodologies. ") * 600, "tier": "lite"}
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                task = asyncio.create_task(session.call_tool("tells", big))
                await asyncio.sleep(0.05)
                # exiting the context closes the pipes mid-call
        try:
            await task
            print("MIDCALL: call completed")
        except Exception as exc:  # noqa: BLE001
            print(f"MIDCALL: client-side call error {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        print(f"MIDCALL: context exit error {type(exc).__name__}: {str(exc)[:100]}")

    await asyncio.sleep(2.0)  # let the server process wind down / hit EOF

    # Second connection: fresh server must work (session isolation across connections).
    await full_session(params, "SESSION2")

    if os.path.exists(ERR):
        err = open(ERR, encoding="utf-8", errors="replace").read()
        trace = "Traceback" in err
        print(f"SERVER STDERR: {len(err)} chars, traceback={trace}")
        print("STDERR TAIL:", err[-400:].replace("\n", " | "))
    else:
        print("SERVER STDERR: file not created")


asyncio.run(main())
