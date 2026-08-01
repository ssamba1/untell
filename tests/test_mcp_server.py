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
