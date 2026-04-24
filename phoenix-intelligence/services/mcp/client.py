"""Playwright MCP client — uses the MCP Python SDK over stdio to inspect pages."""

import asyncio
import logging
import shutil
from typing import Optional

from services.config import MCPSettings

logger = logging.getLogger(__name__)


class MCPClient:
    """Connects to ``@playwright/mcp`` via stdio to inspect live pages.

    Usage::

        client = MCPClient()
        snapshot = client.inspect_page("https://example.com")
    """

    def __init__(self, settings: Optional[MCPSettings] = None):
        self.settings = settings or MCPSettings()
        self._session = None
        self._stdio_context = None
        self._read = None
        self._write = None

    def inspect_page(self, url: str) -> str:
        """Navigate to *url* and return an accessibility snapshot.

        This is the **synchronous** public API consumed by the agents.
        Internally it runs the async MCP protocol in a private event loop.

        Returns:
            The accessibility-tree text returned by the Playwright MCP
            ``browser_snapshot`` tool, or an empty string on failure.
        """
        if not self.settings.enabled:
            logger.info("MCP is disabled via configuration — skipping page inspection")
            return ""

        try:
            return self._run_async(self._inspect_page_async(url))
        except Exception:
            logger.exception("MCP page inspection failed for %s", url)
            return ""

    async def _inspect_page_async(self, url: str) -> str:
        """Async implementation: connect, navigate, snapshot, disconnect."""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters

        cmd_parts = self.settings.args.split()
        server_params = StdioServerParameters(
            command=self.settings.command,
            args=cmd_parts,
        )

        async with (
            stdio_client(server_params) as (
                read_stream,
                write_stream,
            ),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()

            logger.info("MCP: navigating to %s", url)
            await session.call_tool("browser_navigate", {"url": url})

            logger.info("MCP: taking accessibility snapshot")
            snapshot_result = await session.call_tool("browser_snapshot", {})

            text = ""
            if snapshot_result and snapshot_result.content:
                for block in snapshot_result.content:
                    if hasattr(block, "text"):
                        text += block.text
                    elif isinstance(block, dict):
                        text += block.get("text", "")

            logger.info(
                "MCP: snapshot received (%d chars)",
                len(text),
            )

            await session.call_tool("browser_close", {})

            return text

    @staticmethod
    def _run_async(coro):
        """Run an async coroutine from synchronous code."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return asyncio.run(coro)

    def is_available(self) -> bool:
        """Check whether the MCP command is reachable on this system."""
        if not self.settings.enabled:
            return False
        return shutil.which(self.settings.command) is not None
