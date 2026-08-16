"""Slice 10 probe: enumerate every MCP tool refusal path + malformed payloads via the REAL engine."""
import asyncio
import json
import sys
import time

from untell.mcp_server import _server

TEXT = (
    "Furthermore, organizations leverage these robust technologies to optimize operational "
    "efficiency. Moreover, the impact continues to expand across various sectors."
)


async def call(srv, name, args):
    try:
        result = await srv.call_tool(name, args)
        texts = [getattr(item, "text", None) for item in result]
        return ("ok", texts)
    except Exception as exc:  # noqa: BLE001
        return ("raise", f"{type(exc).__name__}: {exc}")


async def main():
    srv = _server()
    tools = await srv.list_tools()
    print("ADVERTISED:", sorted(t.name for t in tools))

    # --- refusal-path matrix -------------------------------------------------
    probes = {
        "score": [
            ("valid", {"text": TEXT, "tier": "lite"}),
            ("unknown tier", {"text": TEXT, "tier": "fulll"}),
            ("threshold str", {"text": TEXT, "threshold": "abc"}),
            ("threshold 50", {"text": TEXT, "threshold": 50}),
            ("threshold -0.1", {"text": TEXT, "threshold": -0.1}),
            ("threshold inf", {"text": TEXT, "threshold": float("inf")}),
            ("tier None", {"text": TEXT, "tier": None}),
        ],
        "sentences": [
            ("valid", {"text": TEXT, "tier": "lite"}),
            ("top -1", {"text": TEXT, "tier": "lite", "top": -1}),
            ("top 10001", {"text": TEXT, "tier": "lite", "top": 10001}),
            ("top str", {"text": TEXT, "tier": "lite", "top": "abc"}),
            ("top None", {"text": TEXT, "tier": "lite", "top": None}),
        ],
        "tells": [
            ("valid", {"text": TEXT}),
            ("include_matches str", {"text": TEXT, "include_matches": "yes"}),
        ],
        "untell": [
            ("bad tier", {"text": TEXT, "tier": "bogus"}),
            ("bad max_iters", {"text": TEXT, "tier": "lite", "max_iters": 0}),
            ("bad best_of", {"text": TEXT, "tier": "lite", "best_of": 100000}),
            ("bad margin", {"text": TEXT, "tier": "lite", "margin": 1.5}),
            ("bad confirm", {"text": TEXT, "tier": "lite", "confirm": 33}),
            ("bad confirm neg", {"text": TEXT, "tier": "lite", "confirm": -1}),
            ("bad seed", {"text": TEXT, "tier": "lite", "seed": -5}),
            ("seed str", {"text": TEXT, "tier": "lite", "seed": "abc"}),
            ("bad style", {"text": TEXT, "tier": "lite", "style": "bogus"}),
            ("unknown rewriter", {"text": TEXT, "tier": "lite", "rewriter": "does_not_exist"}),
            ("missing text", {}),
        ],
        "verify_commercial": [
            ("valid", {"text": "This is a test sentence."}),
            ("tier bogus", {"text": "This is a test sentence.", "tier": "bogus"}),
            ("tier empty", {"text": "This is a test sentence.", "tier": ""}),
            ("threshold 50", {"text": "This is a test sentence.", "threshold": 50}),
            ("threshold str", {"text": "This is a test sentence.", "threshold": "abc"}),
            ("sandbox str", {"text": "This is a test sentence.", "sandbox": "yes"}),
            ("browser int", {"text": "This is a test sentence.", "browser": 42}),
        ],
        "ceiling": [
            ("valid", {"tier": "lite"}),
            ("tier bogus", {"tier": "bogus"}),
            ("threshold 50", {"threshold": 50}),
            ("n 0", {"n": 0}),
            ("n 101", {"n": 101}),
            ("n str", {"n": "abc"}),
            ("rewriter unknown", {"rewriter": "wat"}),
        ],
        "compare": [
            ("valid", {"tier": "lite"}),
            ("tier bogus", {"tier": "bogus"}),
        ],
        "scrub": [
            ("valid", {"text": TEXT}),
            ("missing text", {}),
        ],
    }

    for tool_name, cases in probes.items():
        for label, args in cases:
            t0 = time.time()
            status, payload = await call(srv, tool_name, args)
            dt = time.time() - t0
            if status == "raise":
                print(f"[{tool_name}] {label!r}: RAISED {payload}")
                continue
            joined = " | ".join(p[:200] for p in payload if p)
            print(f"[{tool_name}] {label!r}: {dt:.2f}s :: {joined[:220]}")

    # --- malformed payloads: wrong types for text -----------------------------
    for bad_text in (123, None, ["a", "list"], {"a": 1}, 1.5, True):
        status, payload = await call(srv, "tells", {"text": bad_text})
        print(f"[tells] text={bad_text!r}: {status} :: {(payload or [''])[0][:160] if payload else ''}")

    # --- huge strings ----------------------------------------------------------
    huge = "Furthermore, the system leverages robust methodologies. " * 200_000  # ~11MB
    status, payload = await call(srv, "scrub", {"text": huge})
    print(f"[scrub] 11MB text: {status} :: {len(payload or [])} items, {(payload or [''])[0][:80] if payload else ''}")


asyncio.run(main())
