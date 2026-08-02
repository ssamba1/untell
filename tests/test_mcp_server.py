"""Tests for the MCP server — verifies tool registration, not network/MCP protocol.
Mocks the mcp package entirely before importing so we don't need it installed."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_server_tools_registered():
    """The _server() function registers tools without error and returns a FastMCP instance."""
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp_cls = MagicMock(return_value=mock_fastmcp_instance)
    fake_fastmcp_module = MagicMock(FastMCP=mock_fastmcp_cls)
    fake_fastmcp_module.__name__ = "mcp.server.fastmcp"

    fake_mcp_server = MagicMock()
    fake_mcp_server.fastmcp = fake_fastmcp_module

    fake_mcp = MagicMock()
    fake_mcp.server = fake_mcp_server

    patches = {
        "mcp": fake_mcp,
        "mcp.server": fake_mcp_server,
        "mcp.server.fastmcp": fake_fastmcp_module,
    }

    with patch.dict(sys.modules, patches, clear=False):
        if "untell.mcp_server" in sys.modules:
            del sys.modules["untell.mcp_server"]

        import untell.mcp_server as mcp_mod

        result = mcp_mod._server()
        mock_fastmcp_cls.assert_called_once_with("untell")
        assert len(mock_fastmcp_instance.tool.call_args_list) >= 5, (
            f"Expected at least 5 tools registered, got {len(mock_fastmcp_instance.tool.call_args_list)}"
        )
        assert result is mock_fastmcp_instance


def test_mcp_advertises_every_style_the_cli_accepts():
    """The MCP tool docstring is what a client reads to learn valid `style` values.

    It was hand-copied and had drifted to 6 of the 14 styles, so eight were invisible to every
    MCP caller. It is now generated from the same table `--style` uses.

    Registration order matters: `server.tool()` snapshots __doc__ as the advertised description,
    so patching the list in after an inline decorator had no effect on what a client sees.
    """
    import asyncio

    pytest.importorskip("mcp")
    from untell.mcp_server import _server
    from untell.rewriter.prompts import STYLE_NAMES

    tools = asyncio.run(_server().list_tools())
    described = next(t for t in tools if t.name == "untell").description or ""
    missing = [s for s in STYLE_NAMES if s not in described]
    assert not missing, f"MCP does not advertise these styles: {missing}"


def test_cli_style_choices_come_from_the_same_table():
    from untell.rewriter.prompts import STYLE_NAMES
    from untell.scripts.run import main as run_main

    with pytest.raises(SystemExit):
        run_main(["--style", "definitely-not-a-style", "text"])
    assert len(STYLE_NAMES) == 14


def _mcp_tools():
    """Register the MCP tools against a fake FastMCP and return them by name.

    The existing tests assert that >=5 tools register and that the style list matches the CLI, but
    never CALL one — a tool could raise on every invocation and the suite would stay green. This
    captures the actual callables so their behaviour can be asserted.
    """
    import sys
    import types

    recorded = {}

    class _FakeServer:
        def tool(self, *a, **k):
            def deco(fn):
                recorded[fn.__name__] = fn
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
    return recorded


class TestMcpToolsActuallyRun:
    TEXT = (
        "Furthermore, organizations leverage these robust technologies to optimize operational "
        "efficiency. Moreover, the impact continues to expand across various sectors."
    )

    @pytest.mark.parametrize("name", ["score", "sentences", "tells", "scrub"])
    def test_simple_tools_return_dicts(self, name):
        fn = _mcp_tools()[name]
        kwargs = {"text": self.TEXT}
        if name in ("score", "sentences"):
            kwargs["tier"] = "lite"
        result = fn(**kwargs)
        assert isinstance(result, dict) and result

    def test_untell_works_with_default_arguments(self):
        """MEASURED before the fix: calling this with defaults returned
        {"error": "no rewriter configured"} on any install without an API key.

        The default was `rewriter="auto"`, which is not in _FREE_REWRITERS, so it fell through
        unresolved and auto-select declined to pick a backend — even though `composite` is free and
        always available. The identical CLI invocation worked, because the CLI defaults to
        composite. The flagship MCP tool failed out of the box.
        """
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", max_iters=1)
        assert "error" not in result, result["error"]
        assert result["final"]

    def test_unknown_rewriter_names_the_rewriter(self):
        """A typo used to fall through to auto-selection, running a DIFFERENT technique and
        reporting the result as the requested one."""
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", rewriter="does_not_exist")
        assert "does_not_exist" in result.get("error", "")


def test_best_of_default_matches_the_cli_on_every_surface():
    """best-of-1 was identified as a root cause of understated evasion and the CLI moved to 3.
    MCP and the REST API were left on 1, so every non-CLI caller got the weak path.

    MEASURED over 6 real HC3 paragraphs: best_of=1 -> 33% still flagged, best_of=3 -> 0%.

    The ceiling surfaces are deliberately excluded — eval/ceiling.py's CLI also defaults to 1,
    because measuring the single-draw baseline is the point of that tool.
    """
    import inspect

    from untell.api_server import HumanizeRequest
    from untell.scripts.run import main as run_main  # noqa: F401

    mcp_untell = _mcp_tools()["untell"]
    assert inspect.signature(mcp_untell).parameters["best_of"].default == 3
    assert HumanizeRequest.model_fields["best_of"].default == 3


def test_rewriter_default_is_the_free_path_on_every_surface():
    """"auto" declines to pick a backend without an API key, so it cannot be the default on a
    tool that advertises a zero-dependency free path."""
    import inspect

    from untell.api_server import HumanizeRequest

    assert inspect.signature(_mcp_tools()["untell"]).parameters["rewriter"].default == "composite"
    assert HumanizeRequest.model_fields["rewriter"].default == "composite"


def test_untell_tool_exposes_polish():
    """The REST API's /humanize exposes `polish`; the MCP tool always called untell_text with the
    default False, so the same loop reached through MCP produced a strictly weaker result than
    through HTTP, with nothing to indicate a knob was missing."""
    import inspect

    import untell.mcp_server as mcp

    src = inspect.getsource(mcp)
    assert "polish: bool = False" in src
    assert "polish=polish" in src, "declared but not forwarded to untell_text"
