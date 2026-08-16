"""Slice 10 probe 2: concurrency (10 parallel call_tool), no cross-talk, session isolation,
malformed payloads, huge strings, and client-disconnect (task cancellation) resilience."""
import asyncio
import json
import time

from untell.mcp_server import _server

TEXTS = [f"Furthermore, the system leverages robust methodologies to optimize outcome number {i}. "
         f"This is sentence two of document {i} with some distinctive words: zebra kiosk umbrella." 
         for i in range(10)]


async def call(srv, name, args):
    try:
        result = await srv.call_tool(name, args)
        texts = [getattr(item, "text", None) for item in result]
        return ("ok", texts)
    except Exception as exc:  # noqa: BLE001
        return ("raise", f"{type(exc).__name__}: {str(exc)[:200]}")


async def main():
    srv = _server()
    # warm-up (loads any cached models, no timing)
    await call(srv, "tells", {"text": TEXTS[0]})

    # ---- 1) 10 concurrent tells with distinct texts: no cross-talk ------------------
    t0 = time.time()
    results = await asyncio.gather(*[call(srv, "tells", {"text": t}) for t in TEXTS])
    dt = time.time() - t0
    cross_talk = 0
    for i, (status, payload) in enumerate(results):
        body = json.loads(payload[0]) if payload else {}
        words = body.get("words")
        expected = len(TEXTS[i].split())
        if words != expected:
            cross_talk += 1
            print(f"  CROSS-TALK? call {i}: words={words} expected={expected}")
    print(f"CONCURRENCY 10x tells: {dt:.2f}s, cross_talk={cross_talk}")

    # ---- 2) 10 concurrent scrub: each result must be its own input cleaned ---------
    dirty = [f"Hello\u200b world {i} \u200b again." for i in range(10)]
    results = await asyncio.gather(*[call(srv, "scrub", {"text": t}) for t in dirty])
    bad = 0
    for i, (status, payload) in enumerate(results):
        body = json.loads(payload[0]) if payload else {}
        if body.get("hidden_chars_removed") != 2 or str(i) not in body.get("clean", ""):
            bad += 1
            print(f"  SCRUB MISMATCH call {i}: {body}")
    print(f"CONCURRENCY 10x scrub: cross_talk={bad}")

    # ---- 3) 10 concurrent MIXED tools: response shapes must match the tool ---------
    mixed = []
    for i in range(10):
        if i % 2 == 0:
            mixed.append(call(srv, "tells", {"text": TEXTS[i]}))
        else:
            mixed.append(call(srv, "scrub", {"text": dirty[i]}))
    results = await asyncio.gather(*mixed)
    shape_ok = True
    for i, (status, payload) in enumerate(results):
        body = json.loads(payload[0]) if payload else {}
        if i % 2 == 0 and "words" not in body:
            shape_ok = False
            print(f"  MIXED: tells call {i} returned wrong shape {list(body)[:3]}")
        if i % 2 == 1 and "hidden_chars_removed" not in body:
            shape_ok = False
            print(f"  MIXED: scrub call {i} returned wrong shape {list(body)[:3]}")
    print(f"CONCURRENCY 10x mixed: shape_ok={shape_ok}")

    # ---- 4) same input twice concurrently: identical results (determinism) --------
    r1, r2 = await asyncio.gather(
        call(srv, "sentences", {"text": TEXTS[0], "tier": "lite", "top": 2}),
        call(srv, "sentences", {"text": TEXTS[0], "tier": "lite", "top": 2}),
    )
    same = r1[1][0] == r2[1][0]
    print(f"CONCURRENCY same-input determinism: {same}")

    # ---- 5) malformed text types ----------------------------------------------------
    for bad_text in (123, None, ["a", "list"], {"a": 1}, 1.5, True):
        status, payload = await call(srv, "tells", {"text": bad_text})
        print(f"MALFORMED tells text={bad_text!r}: {status} :: {(payload or [''])[0][:140] if payload else ''}")

    # ---- 6) huge strings -------------------------------------------------------------
    for label, n in (("60KB", 60_000), ("1MB", 1_000_000)):
        huge = ("Furthermore, the system leverages robust methodologies. ") * (n // 55)
        t0 = time.time()
        status, payload = await call(srv, "tells", {"text": huge})
        print(f"HUGE tells {label} ({len(huge)} chars): {status} {time.time()-t0:.2f}s :: "
              f"{(payload or [''])[0][:120] if payload else ''}")

    # ---- 7) client disconnect: cancel a call mid-flight, server must stay healthy ----
    long_text = ("Furthermore, the system leverages robust methodologies to optimize outcomes. ") * 3000

    async def canceller():
        await asyncio.sleep(0.05)
        raise asyncio.CancelledError

    async def run_cancelled():
        task = asyncio.create_task(call(srv, "sentences", {"text": long_text, "tier": "lite"}))
        c = asyncio.create_task(canceller())
        done, _ = await asyncio.wait({task, c}, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            if d is task:
                return ("completed", None)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        return ("cancelled", None)

    outcome, _ = await run_cancelled()
    status, payload = await call(srv, "tells", {"text": TEXTS[0]})
    healthy = status == "ok" and json.loads(payload[0]).get("words") == len(TEXTS[0].split())
    print(f"DISCONNECT mid-call: call {outcome}; server healthy after: {healthy}")


asyncio.run(main())
