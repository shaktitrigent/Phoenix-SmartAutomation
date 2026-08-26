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
        try:
            print(f"[PHOENIX MCP] === MCP INSPECTION STARTED ===")
            print(f"[PHOENIX MCP] URL: {url}")
            print(f"[PHOENIX MCP] Project: {project}")
            print(f"[PHOENIX MCP] Page: {page}")
            print(f"[PHOENIX MCP] Execution ID: {execution_id}")
        except (UnicodeEncodeError, OSError):
            # Fallback for console encoding issues
            pass
        
        logger.info(f"[PHOENIX MCP] MCP inspection started")
        logger.info(f"[PHOENIX MCP] URL: {url}")
        logger.info(f"[PHOENIX MCP] Project: {project}")
        logger.info(f"[PHOENIX MCP] Page: {page}")
        
        if not self.settings.enabled:
            logger.info("MCP is disabled via configuration — skipping page inspection")
            print("[PHOENIX MCP] MCP DISABLED - skipping inspection")
            return ""

        # Check for DOM reuse if snapshot manager is available
        if self.dom_snapshot_manager and execution_id:
            logger.info(f"[PHOENIX MCP] Checking for reusable DOM snapshot before inspect_page")
            print(f"[PHOENIX MCP] DOM reuse check started")
            
            def capture_via_mcp(target_url: str):
                """Capture DOM via MCP."""
                print(f"[PHOENIX MCP] Starting MCP capture for: {target_url}")
                start_time = time.time()
                result = self._run_async(self._inspect_page_async(target_url))
                duration = time.time() - start_time
                print(f"[PHOENIX MCP] MCP capture completed in {duration:.2f}s")
                # Return tuple of (dom_content, accessibility_tree) as expected by DOM snapshot manager
                # For now, accessibility tree is embedded in the result
                return result, result
            
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
                        logger.info(f"[PHOENIX MCP] DOM reused from storage - MCP call skipped")
                        logger.info(f"[PHOENIX MCP] Time saved: {reuse_decision.time_saved_ms:.2f}ms")
                        print(f"[PHOENIX MCP] ✓ DOM REUSED from storage")
                        print(f"[PHOENIX MCP] ✓ MCP call SKIPPED")
                        print(f"[PHOENIX MCP] ✓ Time saved: {reuse_decision.time_saved_ms:.2f}ms")
                    else:
                        logger.info(f"[PHOENIX MCP] New DOM captured via MCP")
                        print(f"[PHOENIX MCP] ✓ New DOM captured via MCP")
                
                print(f"[PHOENIX MCP] === MCP INSPECTION COMPLETED ===")
                print(f"[PHOENIX MCP] DOM size: {len(dom_content)} chars")
                print(f"[PHOENIX MCP] Cache result: {'HIT' if reuse_decision.mcp_skipped else 'MISS'}")
                
                return dom_content
                
            except Exception as exc:
                logger.warning(f"[PHOENIX MCP] DOM reuse failed, falling back to direct MCP: {exc}")
                print(f"[PHOENIX MCP] DOM reuse failed, falling back to direct MCP")
                # Continue to direct MCP call as fallback

        # Direct MCP call (original behavior)
        print(f"[PHOENIX MCP] Starting direct MCP call")
        start_time = time.time()
        try:
            result = self._run_async(self._inspect_page_async(url))
            duration = time.time() - start_time
            
            print(f"[PHOENIX MCP] Direct MCP call completed in {duration:.2f}s")
            print(f"[PHOENIX MCP] Snapshot size: {len(result)} chars")
            
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
                logger.info(f"[PHOENIX MCP] Snapshot saved to artifacts: {len(result)} chars in {duration:.2f}s")
                print(f"[PHOENIX MCP] ✓ Snapshot saved to artifacts")
            
            print(f"[PHOENIX MCP] === MCP INSPECTION COMPLETED ===")
            return result
        except Exception as exc:
            duration = time.time() - start_time
            print(f"[PHOENIX MCP] ✗ MCP call FAILED after {duration:.2f}s")
            
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
            print(f"[PHOENIX MCP] ✗ Empty DOM snapshot received")
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
            # Use intelligent waiting instead of fixed sleep for SPA support
            logger.info("MCP: waiting for page load and SPA rendering")
            await asyncio.sleep(2)  # Initial wait for navigation
            
            # Additional intelligent wait for SPA rendering
            max_wait_attempts = 5
            for attempt in range(max_wait_attempts):
                await asyncio.sleep(0.5)  # Wait between checks
                logger.info(f"MCP: checking if page has rendered (attempt {attempt + 1}/{max_wait_attempts})")
                
                # Check if page has meaningful content by checking the DOM
                try:
                    # Try to get page content to check if rendered
                    dom_check_result = await session.call_tool("browser_evaluate", {
                        "expression": "() => document.documentElement.outerHTML"
                    })
                    
                    if dom_check_result and dom_check_result.content:
                        dom_text = ""
                        for block in dom_check_result.content:
                            if hasattr(block, "text"):
                                dom_text += block.text
                            elif isinstance(block, dict):
                                dom_text += block.get("text", "")
                        
                        # Check for meaningful elements
                        meaningful_elements = dom_text.count('<input') + dom_text.count('<button') + dom_text.count('<form') + dom_text.count('<a ')
                        
                        if len(dom_text) > 100 and meaningful_elements > 0:
                            logger.info(f"MCP: Page has rendered content ({len(dom_text)} bytes, {meaningful_elements} elements)")
                            break
                except Exception as e:
                    logger.debug(f"MCP: DOM check failed: {e}")
            
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
            
            # If accessibility tree is too small, capture full HTML as fallback
            if len(text) < 2000:
                logger.warning(f"MCP: Accessibility tree too small ({len(text)} chars), capturing full HTML as fallback")
                try:
                    html_result = await session.call_tool("browser_evaluate", {
                        "expression": "() => document.documentElement.outerHTML"
                    })
                    
                    if html_result and html_result.content:
                        html_text = ""
                        for block in html_result.content:
                            if hasattr(block, "text"):
                                html_text += block.text
                            elif isinstance(block, dict):
                                html_text += block.get("text", "")
                        
                        if len(html_text) > len(text):
                            logger.info(f"MCP: Using full HTML instead ({len(html_text)} chars vs {len(text)} chars)")
                            text = html_text
                except Exception as e:
                    logger.debug(f"MCP: HTML fallback failed: {e}")
            
            # Log accessibility tree size for debugging
            if text:
                logger.info(f"MCP: DOM captured successfully")
            else:
                logger.warning(f"MCP: DOM is empty")

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
