"""The MCP `compare` tool raised TypeError on every invocation.

It called `compare(tier=tier)` against a signature of
`compare(texts, tier=..., threshold=..., corpus=...)`, so the required first argument was never
supplied and the tool was dead on a shipped surface — an MCP client got a traceback rather than a
refusal it could act on.

Found by feeding every MCP tool a plausible bad argument. The other six handle it well: 9 of 13
cases came back as structured errors naming the value and the valid range ("unknown tier 'turbo' —
valid: lite, full, heavy, commercial"). `compare` was the one that could not run at all, with a
good argument or a bad one.

Registration happens inside `_server()` via a decorator, so the tools are not module attributes.
These tests capture them the way the probe did: stand in for FastMCP with a `.tool()` that records
each function and returns it unchanged.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="module")
def tools() -> dict:
    captured: dict = {}

    class _FakeFastMCP:
        def __init__(self, *a, **k):
            pass

        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

        def run(self, *a, **k):
            pass

    fastmcp = MagicMock()
    fastmcp.FastMCP = _FakeFastMCP
    server = MagicMock()
    server.fastmcp = fastmcp
    mcp = MagicMock()
    mcp.server = server

    # setitem, not setdefault, and re-import rather than reuse.
    #
    # tests/test_mcp_server.py installs its OWN MagicMock for these three modules. With
    # `setdefault` the first file to run wins, so run together this fixture kept that mock, whose
    # `.tool()` returns a MagicMock decorator that captures nothing — the fixture then asserted an
    # empty dict and errored. Alone it passed. Test order is not something a fixture should depend
    # on, so the entries are forced and restored, and `untell.mcp_server` is dropped from the cache
    # so its decorators re-run against the fake installed here.
    saved = {name: sys.modules.get(name) for name in
             ("mcp", "mcp.server", "mcp.server.fastmcp", "untell.mcp_server")}
    for name, mod in (("mcp", mcp), ("mcp.server", server), ("mcp.server.fastmcp", fastmcp)):
        sys.modules[name] = mod
    sys.modules.pop("untell.mcp_server", None)
    try:
        import untell.mcp_server as mcp_server

        mcp_server._server()
        assert captured, "no tools were registered"
        yield captured
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def test_compare_is_registered(tools):
    assert "compare" in tools, sorted(tools)


def test_compare_runs_with_its_default_arguments(tools):
    """The regression: every call raised TypeError for a missing `texts`."""
    result = tools["compare"](tier="lite")
    assert isinstance(result, dict), result
    assert "error" not in result, result
    assert result.get("techniques"), f"no per-technique scores returned: {sorted(result)}"


def test_compare_names_its_corpus(tools):
    """`_render` reads result["corpus"], and an unnamed comparison is unquotable.

    The underlying function's own docstring records that calling it directly produced a report
    headed "corpus=unknown" because only the CLI filled the label in. This tool is a second such
    caller, so it passes the label the CLI uses for the same texts.
    """
    result = tools["compare"](tier="lite")
    assert result.get("corpus") == "built-in sample", result.get("corpus")


def test_compare_refuses_an_unknown_tier(tools):
    """It accepted `tier` and validated nothing, unlike every other tool on this surface."""
    result = tools["compare"](tier="turbo")
    assert result.get("error"), result
    assert "turbo" in result["error"], result["error"]


@pytest.mark.parametrize(
    "tool,kwargs",
    [
        ("score", {"text": "Moreover, the framework leverages robust methodologies.", "tier": "turbo"}),
        ("sentences", {"text": "Moreover, the framework leverages methodologies.", "tier": "turbo"}),
        ("untell", {"text": "Moreover, the framework leverages methodologies.", "max_iters": -3}),
    ],
)
def test_the_other_tools_still_refuse_bad_arguments(tools, tool: str, kwargs: dict):
    """Guards the guard: if `_bad_args` stopped firing, `compare` would look fine by comparison."""
    result = tools[tool](**kwargs)
    assert isinstance(result, dict) and result.get("error"), result
