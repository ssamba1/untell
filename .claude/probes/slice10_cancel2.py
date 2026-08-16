"""Probe 2: cancel a genuinely slow call; verify cancellation + health after."""
import asyncio
import json
import time

from untell.mcp_server import _server

BIG = ("Furthermore, the system leverages robust methodologies to optimize outcomes. ") * 6000  # ~312KB


async def main():
    srv = _server()
    await srv.call_tool("tells", {"text": "warmup"})

    started = time.time()

    async def slow_call():
        return await srv.call_tool("tells", {"text": BIG})

    task = asyncio.create_task(slow_call())
    await asyncio.sleep(0.3)
    print("at 0.3s: task done?", task.done(), "elapsed %.2fs" % (time.time() - started))
    if not task.done():
        t0 = time.time()
        task.cancel()
        try:
            await task
            print("CALL COMPLETED (%.2fs after cancel)" % (time.time() - t0))
        except asyncio.CancelledError:
            print("CALL CANCELLED (%.2fs after cancel)" % (time.time() - t0))

    # server must still answer correctly
    res = await srv.call_tool("tells", {"text": "Hello world this is a test sentence."})
    body = json.loads(res[0].text)
    print("HEALTHY after cancel:", body.get("words") == 7)


asyncio.run(main())
