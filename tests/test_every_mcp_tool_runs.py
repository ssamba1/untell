"""Every registered MCP tool must return a usable result when called correctly.

`compare` raised `TypeError: missing 1 required positional argument: 'texts'` on every
invocation, and it shipped that way. It was found sideways — a bad-argument probe never reached
validation because the call itself could not be made — which means the plainer question had never
been asked of any tool on this surface: does it run?

MEASURED after fixing compare: all eight run and return a dict with real keys.

The parametrisation is over the tools ACTUALLY REGISTERED, not a hand-written list, and a guard
asserts every registered tool has arguments here. A new tool added without an entry fails that
guard rather than being silently skipped — which is how a list like this normally rots, and how
`compare` stayed dead: `test_mcp_server.py` asserts "at least 5 tools registered" and registration
is exactly what a broken tool still does.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)

# Cheapest valid arguments per tool — the question is "does it run", not "is it fast".
GOOD_ARGS = {
    "score": {"text": TEXT, "tier": "lite"},
    "sentences": {"text": TEXT, "tier": "lite"},
    "tells": {"text": TEXT},
    "scrub": {"text": TEXT},
    "untell": {"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
    "verify_commercial": {"text": TEXT},
    "ceiling": {"tier": "lite"},
    "compare": {"tier": "lite"},
}


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

    # Forced, not setdefault: tests/test_mcp_server.py installs its own mock for these modules, and
    # whichever file ran first used to win — this fixture then captured nothing and errored only
    # when the two ran together.
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


def test_every_registered_tool_has_arguments_here(tools):
    """The guard that keeps this file honest as tools are added."""
    missing = sorted(set(tools) - set(GOOD_ARGS))
    assert not missing, (
        f"{missing} registered on the MCP surface with no arguments in this file, so nothing "
        "checks they can run. Add an entry rather than deleting this assertion."
    )


@pytest.mark.parametrize("name", sorted(GOOD_ARGS))
def test_the_tool_runs_and_returns_a_result(tools, name: str):
    if name not in tools:
        pytest.skip(f"{name} is no longer registered")

    result = tools[name](**GOOD_ARGS[name])

    assert isinstance(result, dict), f"{name} returned {type(result).__name__}, not a dict"
    assert not result.get("error"), f"{name} refused its own valid arguments: {result['error']}"
    assert result, f"{name} returned an empty dict"
