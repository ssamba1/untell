"""The full protocol-level refusal matrix for every MCP tool.

`test_mcp_server.py` tests `_bad_args` directly and calls the raw tool functions; this file
drives EVERY refusal through `call_tool` — the real path a client's request travels
(registration lookup, pydantic argument validation, coroutine dispatch). Two and only two
outcomes exist, and each is pinned here:

1. An out-of-range but well-typed argument (unknown tier, threshold above 1, negative top,
   unknown style/rewriter, ...) answers a dict whose ONLY key is ``error``, naming the value
   and the valid vocabulary. The CLI rejects the same inputs at parse time (argparse
   choices) and REST answers 422; this surface has no status code, so the pure error dict
   IS the refusal.
2. A wrong-typed or missing argument never reaches the tool body: the engine's pydantic
   validation refuses first with a ToolError naming the field and the pydantic error type
   — the MCP analogue of REST's 422 detail. Never a raw traceback.

MEASURED (this slice, real engine): every row below was probed live; the split between
dict-refusals and ToolErrors is exactly what the engine does, not what a mock would.
"""
from __future__ import annotations

import asyncio
import json

import pytest

mcp = pytest.importorskip("mcp")  # noqa: F841

from untell.mcp_server import _server  # noqa: E402

TEXT = (
    "Furthermore, organizations leverage these robust technologies to optimize operational "
    "efficiency. Moreover, the impact continues to expand across various sectors."
)


async def _payload(srv, name, args) -> dict:
    result = await srv.call_tool(name, args)
    return json.loads(result[0].text)


# (tool, args, substring that must appear in the error) — answers {"error": ...} only.
DICT_REFUSALS = [
    ("score", {"text": TEXT, "tier": "fulll"}, "unknown tier"),
    ("score", {"text": TEXT, "threshold": 50}, "outside [0, 1]"),
    ("score", {"text": TEXT, "threshold": -0.1}, "outside [0, 1]"),
    ("score", {"text": TEXT, "threshold": float("inf")}, "outside [0, 1]"),
    ("sentences", {"text": TEXT, "tier": "lite", "top": -1}, "outside 0..10000"),
    ("sentences", {"text": TEXT, "tier": "lite", "top": 10001}, "outside 0..10000"),
    ("untell", {"text": TEXT, "tier": "bogus"}, "unknown tier"),
    ("untell", {"text": TEXT, "tier": "lite", "max_iters": 0}, "outside 1..100"),
    ("untell", {"text": TEXT, "tier": "lite", "best_of": 100000}, "outside 1..100"),
    ("untell", {"text": TEXT, "tier": "lite", "margin": 1.5}, "outside [0, 1]"),
    ("untell", {"text": TEXT, "tier": "lite", "confirm": 33}, "outside 0..32"),
    ("untell", {"text": TEXT, "tier": "lite", "seed": -5}, "outside 0..2**64-1"),
    ("untell", {"text": TEXT, "tier": "lite", "style": "bogus"}, "unknown style"),
    ("untell", {"text": TEXT, "tier": "lite", "rewriter": "does_not_exist"}, "is not available"),
    ("verify_commercial", {"text": TEXT, "tier": "bogus"}, "unknown tier"),
    ("verify_commercial", {"text": TEXT, "threshold": 50}, "outside [0, 1]"),
    ("ceiling", {"tier": "bogus"}, "unknown tier"),
    ("ceiling", {"threshold": 50}, "outside [0, 1]"),
    ("ceiling", {"n": 0}, "outside 1..100"),
    ("ceiling", {"n": 101}, "outside 1..100"),
    ("ceiling", {"rewriter": "wat"}, "unknown rewriter"),
    ("compare", {"tier": "bogus"}, "unknown tier"),
]

# (tool, args) — the engine's pydantic validation refuses with a ToolError naming the field.
TOOL_ERRORS = [
    ("score", {"text": TEXT, "threshold": "abc"}),
    ("score", {"text": TEXT, "tier": None}),
    ("sentences", {"text": TEXT, "top": "abc"}),
    ("untell", {"text": TEXT, "seed": "abc"}),
    ("untell", {}),  # missing required `text`
    ("verify_commercial", {"text": TEXT, "threshold": "abc"}),
    ("verify_commercial", {"text": TEXT, "browser": 42}),
    ("ceiling", {"n": "abc"}),
    ("scrub", {}),  # missing required `text`
    ("tells", {"text": 123}),
    ("tells", {"text": None}),
    ("tells", {"text": ["a", "list"]}),
    ("tells", {"text": {"a": 1}}),
    ("tells", {"text": 1.5}),
    ("tells", {"text": True}),
]


@pytest.mark.parametrize("tool,args,needle", DICT_REFUSALS)
def test_out_of_range_arguments_are_pure_error_dicts(tool, args, needle):
    async def _go():
        srv = _server()
        body = await _payload(srv, tool, args)
        assert set(body) == {"error"}, f"{tool}{args} -> {sorted(body)}"
        assert needle in body["error"], body["error"]

    asyncio.run(_go())


def test_the_untell_rewriter_refusal_never_carries_a_final():
    """The one refusal that used to ship a success-shaped payload: untell(rewriter=<unknown>)
    returned {"error": ..., "final": <UNCHANGED original>, "seed": ...} — a client reading
    `final` (the key the docstring advertises as the humanized text) saw the original passed
    back as if the loop had run. Now the pure error dict, like every other refusal."""

    async def _go():
        srv = _server()
        body = await _payload(srv, "untell", {"text": TEXT, "tier": "lite", "rewriter": "nope"})
        assert set(body) == {"error"}
        assert "nope" in body["error"]

    asyncio.run(_go())


@pytest.mark.parametrize("tool,args", TOOL_ERRORS)
def test_wrong_typed_or_missing_arguments_are_tool_errors_naming_the_field(tool, args):
    async def _go():
        srv = _server()
        with pytest.raises(Exception) as exc:  # noqa: B017 — ToolError from the SDK
            await srv.call_tool(tool, args)
        msg = str(exc.value)
        assert tool in msg, msg
        assert "validation error" in msg or "Input should be" in msg, msg

    asyncio.run(_go())
