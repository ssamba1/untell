"""ceiling must refuse an unknown rewriter NAME instead of measuring nothing and
reporting the bogus name as the rewriter that ran.

MEASURED (this slice, real FastMCP engine): `ceiling(rewriter="wat")` ran the FULL
measurement (106.59 s on the default full tier) and returned `"rewriter": "wat"` with
`rewriter_available: False`, `run_post_means: null` and NO error anywhere. untell_text
refused per text (`{"error": ...}`), but measure_ceiling's aggregation drops error dicts
(eval/ceiling.py:237 `if "error" not in res and "post" in res`), so the measurement
reported a rewriter that does not exist as the one that ran.

Every other surface refuses the same input: the CLI at parse time
(eval/ceiling.py:502 argparse `choices=[auto, surgical, structural, composite, targeted,
neural, ensemble, max, t5_paraphrase, mt_pivot]`) and REST with 422 ("unknown rewriter
{name}"). The MCP `untell` tool surfaces the same class of error. ceiling was the hole.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

mcp = pytest.importorskip("mcp")  # noqa: F841


def _real_server():
    from untell.mcp_server import _server

    return _server()


def _run(coro):
    return asyncio.run(coro)


def test_an_unknown_rewriter_name_is_refused_before_any_measurement():
    """The refusal must be instant — MEASURED before the fix the call ran 106 s first."""

    async def _go():
        srv = _real_server()
        result = await srv.call_tool("ceiling", {"rewriter": "wat", "tier": "lite"})
        return json.loads(result[0].text)

    payload = _run(_go())
    assert "error" in payload, f"ceiling ran a measurement for a nonexistent rewriter: {str(payload)[:160]}"
    assert "wat" in payload["error"]


def test_the_refusal_lists_the_valid_vocabulary():
    async def _go():
        srv = _real_server()
        result = await srv.call_tool("ceiling", {"rewriter": "does_not_exist"})
        return json.loads(result[0].text)

    payload = _run(_go())
    for name in ("composite", "surgical", "auto"):
        assert name in payload["error"], name


def test_a_valid_rewriter_still_runs():
    async def _go():
        srv = _real_server()
        result = await srv.call_tool("ceiling", {"tier": "lite", "n": 1, "rewriter": "surgical"})
        return json.loads(result[0].text)

    payload = _run(_go())
    assert "error" not in payload, payload.get("error")
    assert payload["rewriter"] == "surgical"


def test_an_unavailable_free_rewriter_is_refused_not_billed(monkeypatch):
    """A FREE name whose backend is not installed must refuse, not silently run a
    different technique and report it as the requested one. Patched, because on a
    machine with .[full] installed mt_pivot IS available and correctly runs."""

    def _no_rewriter(prefer=None):
        return None

    monkeypatch.setattr("untell.rewriter.get_rewriter", _no_rewriter)

    captured = {}

    class _FakeServer:
        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    fake = types.ModuleType("mcp.server.fastmcp")
    fake.FastMCP = lambda name: _FakeServer()
    saved = {k: sys.modules.get(k) for k in ("mcp", "mcp.server", "mcp.server.fastmcp")}
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    sys.modules["mcp.server.fastmcp"] = fake
    try:
        import untell.mcp_server as m

        m._server()
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    payload = captured["ceiling"](tier="lite", n=1, rewriter="mt_pivot")
    assert "error" in payload, payload
    assert "full" in payload["error"], payload["error"]


def test_the_cli_refuses_the_same_input_at_parse_time():
    """The consistency anchor: the CLI's --rewriter choices must reject 'wat' too."""
    from eval.ceiling import build_parser as ceiling_parser

    with pytest.raises(SystemExit) as exc:
        ceiling_parser().parse_args(["--rewriter", "wat"])
    assert exc.value.code != 0
