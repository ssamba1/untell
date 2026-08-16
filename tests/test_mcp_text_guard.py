"""The MCP text inputs must refuse oversized payloads the way REST refuses them with 422.

MEASURED (this slice, real FastMCP engine): `tells` accepted a 1,018,136-character text and
occupied the worker for 230.44 s before returning a result. The REST surface refuses the same
shape at the edge — every request model bounds `text` at MAX_INPUT_CHARS (50,000) with 422, and
api_server.py:300-321 documents why: "Rejecting at the edge turns an unbounded request into a
422 instead of a tied-up worker". MCP is equally a network surface with an untrusted caller, and
worse: mcp's SDK runs sync tool functions directly in the event loop, so a megabyte payload
blocks EVERY other call and cannot be interrupted by a client disconnect.

The guard reuses the SAME constant REST imports (untell.scripts.score.MAX_INPUT_CHARS) so the
two surfaces cannot drift apart — the same reasoning as the "the bound is the scorer's own
constant" comment in api_server.py.

The helper lives at module level (like `_bad_args`) so the checks run on machines without the
optional `mcp` package; the real-engine tests below prove the tools actually call it.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from untell.mcp_server import _text_too_long

OVER = "x" * 50_001
AT_LIMIT = "x" * 50_000


def test_under_the_limit_passes():
    assert _text_too_long("short text") is None
    assert _text_too_long(AT_LIMIT) is None


def test_over_the_limit_is_refused_with_the_bound_named():
    err = _text_too_long(OVER)
    assert err and "error" in err
    assert "50000" in err["error"]
    assert "50001" in err["error"], "the actual length should be named"


def test_the_field_name_is_reported_for_voice_sample():
    err = _text_too_long(OVER, name="voice_sample")
    assert err and "voice_sample" in err["error"]


def test_the_bound_is_the_same_constant_rest_uses():
    """If REST's bound moves, the MCP refusal must move with it — not drift."""
    from untell.scripts.score import MAX_INPUT_CHARS

    assert MAX_INPUT_CHARS == 50_000
    assert _text_too_long("x" * (MAX_INPUT_CHARS + 1)) is not None
    assert _text_too_long("x" * MAX_INPUT_CHARS) is None


# --- real engine: the tools actually refuse fast instead of running for minutes ------------

mcp = pytest.importorskip("mcp")  # noqa: F841


def _real_server():
    from untell.mcp_server import _server

    return _server()


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "tool,args",
    [
        ("score", {"tier": "lite"}),
        ("sentences", {"tier": "lite"}),
        ("tells", {}),
        ("scrub", {}),
        ("verify_commercial", {}),
        ("untell", {"tier": "lite"}),
    ],
)
def test_an_oversized_text_is_refused_instead_of_processing(tool, args):
    """MEASURED before the guard: tells with ~1 MB ran 230 s. The refusal must be instant."""

    async def _go():
        srv = _real_server()
        result = await srv.call_tool(tool, {"text": OVER, **args})
        return json.loads(result[0].text)

    payload = _run(_go())
    assert "error" in payload, f"{tool} processed a 50,001-char text: {str(payload)[:120]}"
    assert "50000" in payload["error"]


def test_an_oversized_voice_sample_is_refused():
    async def _go():
        srv = _real_server()
        result = await srv.call_tool("untell", {"text": "short", "tier": "lite", "voice_sample": OVER})
        return json.loads(result[0].text)

    payload = _run(_go())
    assert "error" in payload and "voice_sample" in payload["error"]


def test_a_text_at_the_limit_still_runs():
    """The guard must not refuse the documented maximum — boundary, not a fencepost."""
    from untell.scripts.score import MAX_INPUT_CHARS

    async def _go():
        srv = _real_server()
        text = ("Furthermore, the system leverages robust methodologies. ") * (MAX_INPUT_CHARS // 56)
        result = await srv.call_tool("scrub", {"text": text})
        return json.loads(result[0].text)

    payload = _run(_go())
    assert "error" not in payload, payload.get("error")
    assert "clean" in payload
