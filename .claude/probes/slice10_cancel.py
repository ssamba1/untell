"""Probe: cancel a slow in-flight call_tool; verify cancellation + server health after."""
import asyncio
import json
import time

from untell.mcp_server import _server

BIG = ("Furthermore, the system leverages robust methodologies to optimize outcomes. ") * 2000  # ~104KB


async def main():
    srv = _server()
    await srv.call_tool("tells", {"text": "warmup"})

    async def slow_call():
        return await srv.call_tool("tells", {"text": BIG})

    task = asyncio.create_task(slow_call())
    await asyncio.sleep(0.15)
    t0 = time.time()
    task.cancel()
    try:
        await task
        print("CALL COMPLETED before cancel (took %.2fs total)" % (time.time() - t0))
    except asyncio.CancelledError:
        print("CALL CANCELLED after %.2fs" % (time.time() - t0))

    # server must still answer correctly
    res = await srv.call_tool("tells", {"text": "Hello world this is a test sentence."})
    body = json.loads(res[0].text)
    print("HEALTHY after cancel:", body.get("words") == 7)

    # and a second big call still works (no leaked state)
    t0 = time.time()
    res = await srv.call_tool("tells", {"text": BIG})
    body = json.loads(res[0].text)
    print("SECOND BIG CALL OK:", body.get("words", 0) > 1000, "%.1fs" % (time.time() - t0))


asyncio.run(main())
