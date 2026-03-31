"""MCP server lifecycle management.

The ``@playwright/mcp`` server is now spawned on demand by the MCP Python SDK
inside ``MCPClient`` (stdio transport).  This module is retained for any
future need to manage a long-lived server process, but is currently a no-op.
"""

from typing import Dict, Any


class MCPServer:
    """Placeholder — the MCP subprocess is managed by the SDK stdio transport."""

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def is_running(self) -> bool:
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"status": "managed_by_sdk"}
