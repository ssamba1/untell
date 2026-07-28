"""Tests for the MCP server — verifies tool registration, not network/MCP protocol.
Mocks the mcp package entirely before importing so we don't need it installed."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


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
