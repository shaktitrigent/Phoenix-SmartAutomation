"""Playwright MCP client — uses the MCP Python SDK over stdio to inspect pages."""

import asyncio
import logging
import shutil
import time
from typing import Optional

from services.config import MCPSettings

logger = logging.getLogger(__name__)


class InspectionFailedError(RuntimeError):
    """Raised when MCP page inspection fails and no DOM snapshot can be obtained."""


class MCPClient:
    """Connects to ``@playwright/mcp`` via stdio to inspect live pages.

    Usage::

        client = MCPClient()
        snapshot = client.inspect_page("https://example.com")
    """

    def __init__(self, settings: Optional[MCPSettings] = None, artifacts_manager=None, dom_snapshot_manager=None):
        self.settings = settings or MCPSettings()
        self._session = None
        self._stdio_context = None
        self._read = None
        self._write = None
        self.artifacts_manager = artifacts_manager
        self.dom_snapshot_manager = dom_snapshot_manager

    def inspect_page(self, url: str, project: str = "default", page: str = "default", execution_id: str = "") -> str:
        """Navigate to *url* and return an accessibility snapshot with automatic DOM reuse.

        This is the **synchronous** public API consumed by the agents.
        Internally it runs the async MCP protocol in a private event loop.
        
        Now includes automatic DOM reuse from permanent storage to skip MCP calls
        when DOM is unchanged.

        Returns:
            The accessibility-tree text returned by the Playwright MCP
            ``browser_snapshot`` tool.

        Raises:
            InspectionFailedError: When the MCP connection fails or returns an
                empty snapshot. Callers must NOT silently swallow this — no DOM
                snapshot means no grounded locators, so generation must stop.
        """
        if not self.settings.enabled:
            logger.info("MCP is disabled via configuration — skipping page inspection")
            return ""

        # Check for DOM reuse if snapshot manager is available
        if self.dom_snapshot_manager and execution_id:
            logger.info(f"[MCP] Checking for reusable DOM snapshot before inspect_page")
            
            def capture_via_mcp(target_url: str):
                """Capture DOM via MCP."""
                start_time = time.time()
                result = self._run_async(self._inspect_page_async(target_url))
                duration = time.time() - start_time
                return result, "", duration
            
            try:
                dom_content, reuse_decision = self.dom_snapshot_manager.get_dom_with_automatic_reuse(
                    url=url,
                    project=project,
                    page=page,
                    execution_id=execution_id,
                    capture_func=capture_via_mcp,
                    current_dom=None
                )
                
                # Store MCP response artifact if artifacts manager is available
                if self.artifacts_manager and dom_content:
                    from phoenix.execution.artifacts import MCPResponseRecord
                    mcp_record = MCPResponseRecord(
                        url=url,
                        snapshot_text=dom_content,
                        snapshot_size_bytes=len(dom_content.encode('utf-8')),
                        duration_seconds=reuse_decision.time_saved_ms / 1000 if reuse_decision.mcp_skipped else 0.0,
                        success=True
                    )
                    self.artifacts_manager.save_mcp_response(mcp_record)
                    
                    if reuse_decision.mcp_skipped:
                        logger.info(f"[MCP] DOM reused from storage - MCP call skipped")
                        logger.info(f"[MCP] Time saved: {reuse_decision.time_saved_ms:.2f}ms")
                    else:
                        logger.info(f"[MCP] New DOM captured via MCP")
                
                return dom_content
                
            except Exception as exc:
                logger.warning(f"[MCP] DOM reuse failed, falling back to direct MCP: {exc}")
                # Continue to direct MCP call as fallback

        # Direct MCP call (original behavior)
        start_time = time.time()
        try:
            result = self._run_async(self._inspect_page_async(url))
            duration = time.time() - start_time
            
            # Store MCP response artifact if artifacts manager is available
            if self.artifacts_manager and result:
                from phoenix.execution.artifacts import MCPResponseRecord
                mcp_record = MCPResponseRecord(
                    url=url,
                    snapshot_text=result,
                    snapshot_size_bytes=len(result.encode('utf-8')),
                    duration_seconds=duration,
                    success=True
                )
                self.artifacts_manager.save_mcp_response(mcp_record)
                logger.info(f"[MCP] Snapshot saved to artifacts: {len(result)} chars in {duration:.2f}s")
            
            return result
        except Exception as exc:
            duration = time.time() - start_time
            
            # Store failed MCP response artifact
            if self.artifacts_manager:
                from phoenix.execution.artifacts import MCPResponseRecord
                mcp_record = MCPResponseRecord(
                    url=url,
                    snapshot_text="",
                    snapshot_size_bytes=0,
                    duration_seconds=duration,
                    success=False,
                    error_message=str(exc)
                )
                self.artifacts_manager.save_mcp_response(mcp_record)
            
            raise InspectionFailedError(
                f"MCP browser connection failed while inspecting {url!r}. "
                "Cannot generate automation without a DOM snapshot. "
                "Check that: (1) the page is accessible, (2) no authentication/CAPTCHA blocks "
                "the initial load, (3) the @playwright/mcp server is running."
            ) from exc

        if not result or not result.strip():
            raise InspectionFailedError(
                f"MCP inspection of {url!r} returned an empty DOM snapshot. "
                "The page may require authentication or JavaScript to render content. "
                "Verify the URL is correct and the page loads without login."
            )

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

            # Wait for page to fully load before taking snapshot
            logger.info("MCP: waiting for page load (3 seconds)")
            await asyncio.sleep(3)

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
