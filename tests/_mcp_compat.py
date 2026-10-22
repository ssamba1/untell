"""Read an in-process ``call_tool`` result the same way on mcp 1.x and 2.x.

The suite calls the real SDK's ``server.call_tool(name, args)``. Its return shape changed:

    mcp 1.x   a sequence of content blocks, or a ``(content_blocks, structured)`` tuple
    mcp 2.x   a ``CallToolResult`` carrying the blocks on ``.content``

Every test here indexed the 1.x shape directly (``result[0].text``), so once ``mcp>=1.0`` resolved
to 2.x, 51 MCP tests failed with "'CallToolResult' object is not subscriptable" while the server
itself worked. untell supports both (``untell.mcp_server._server_class``), so the tests read both.
"""

from __future__ import annotations

from typing import Any


def content_blocks(result: Any) -> list:
    """The content blocks of a ``call_tool`` result, whichever SDK major version produced it."""
    if isinstance(result, tuple):
        result = result[0]
    return list(getattr(result, "content", result))
