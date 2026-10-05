"""Playwright MCP client — uses the MCP Python SDK over stdio to inspect pages."""

import asyncio
import logging
import re
import shutil
import time
from typing import Optional

from services.config import MCPSettings

logger = logging.getLogger(__name__)


def _redact_and_bound(text: str, max_chars: int = 2000) -> str:
    """Redact sensitive tokens and bound error/stderr output size."""
    if not text:
        return ""
    # Redact API keys, tokens, passwords
    redacted = re.sub(
        r"(sk-ant-[a-zA-Z0-9_-]{10,}|sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9_\-\.]{10,}|password[\"'\s:=]+[^\s\"',;]+)",
        "[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    if len(redacted) > max_chars:
        return redacted[:max_chars] + f"... [truncated {len(redacted) - max_chars} chars]"
    return redacted


def _extract_content_text(content) -> str:
    """Extract plain text from MCP tool result content blocks."""
    text = ""
    if content:
        for block in content:
            if hasattr(block, "text"):
                text += block.text
            elif isinstance(block, dict):
                text += block.get("text", "")
    return text


def _check_tool_result(result, tool_name: str) -> None:
    """Check if an MCP tool result returned an error status."""
    if result is None:
        return
    is_error = getattr(result, "isError", False) or getattr(result, "is_error", False)
    if is_error:
        err_text = _extract_content_text(getattr(result, "content", None))
        err_msg = _redact_and_bound(err_text.strip() or f"MCP tool {tool_name} returned isError=True")
        raise InspectionFailedError(f"MCP tool {tool_name} failed: {err_msg}")


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
        timeout_val = float(self.settings.timeout) if self.settings and hasattr(self.settings, "timeout") else 60.0
        try:
            result = self._run_async(self._inspect_page_async(url), timeout=timeout_val)
            duration = time.time() - start_time
            
            print(f"[PHOENIX MCP] Direct MCP call completed in {duration:.2f}s")
            print(f"[PHOENIX MCP] Snapshot size: {len(result) if result else 0} chars")

            if not result or not result.strip():
                print(f"[PHOENIX MCP] ✗ Empty DOM snapshot received")
                raise InspectionFailedError(
                    f"MCP inspection of {url!r} returned an empty DOM snapshot. "
                    "The page may require authentication or JavaScript to render content. "
                    "Verify the URL is correct and the page loads without login."
                )
            
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
        except InspectionFailedError:
            raise
        except Exception as exc:
            duration = time.time() - start_time
            safe_err = _redact_and_bound(str(exc))
            print(f"[PHOENIX MCP] ✗ MCP call FAILED after {duration:.2f}s: {safe_err}")
            
            # Store failed MCP response artifact
            if self.artifacts_manager:
                from phoenix.execution.artifacts import MCPResponseRecord
                mcp_record = MCPResponseRecord(
                    url=url,
                    snapshot_text="",
                    snapshot_size_bytes=0,
                    duration_seconds=duration,
                    success=False,
                    error_message=safe_err
                )
                self.artifacts_manager.save_mcp_response(mcp_record)
            
            raise InspectionFailedError(
                f"MCP browser connection failed while inspecting {url!r}: {safe_err}. "
                "Cannot generate automation without a DOM snapshot. "
                "Check that: (1) the page is accessible, (2) no authentication/CAPTCHA blocks "
                "the initial load, (3) the @playwright/mcp server is running."
            ) from exc

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
            nav_result = await session.call_tool("browser_navigate", {"url": url})
            _check_tool_result(nav_result, "browser_navigate")

            # Wait for page to fully load before taking snapshot
            logger.info("MCP: waiting for page load and SPA rendering")
            await asyncio.sleep(2)  # Initial wait for navigation
            
            # Additional intelligent wait for SPA rendering
            max_wait_attempts = 5
            for attempt in range(max_wait_attempts):
                await asyncio.sleep(0.5)  # Wait between checks
                logger.info(f"MCP: checking if page has rendered (attempt {attempt + 1}/{max_wait_attempts})")
                
                try:
                    dom_check_result = await session.call_tool("browser_evaluate", {
                        "function": "() => document.documentElement.outerHTML"
                    })
                    _check_tool_result(dom_check_result, "browser_evaluate")
                    
                    dom_text = _extract_content_text(getattr(dom_check_result, "content", None))
                    meaningful_elements = dom_text.count('<input') + dom_text.count('<button') + dom_text.count('<form') + dom_text.count('<a ')
                    
                    if len(dom_text) > 100 and meaningful_elements > 0:
                        logger.info(f"MCP: Page has rendered content ({len(dom_text)} bytes, {meaningful_elements} elements)")
                        break
                except InspectionFailedError:
                    raise
                except Exception as e:
                    logger.debug(f"MCP: DOM check failed: {e}")
            
            logger.info("MCP: taking accessibility snapshot")
            snapshot_result = await session.call_tool("browser_snapshot", {})
            _check_tool_result(snapshot_result, "browser_snapshot")

            text = _extract_content_text(getattr(snapshot_result, "content", None))

            logger.info(
                "MCP: snapshot received (%d chars)",
                len(text),
            )
            
            # If accessibility tree is too small, capture full HTML as fallback
            if len(text) < 2000:
                logger.warning(f"MCP: Accessibility tree too small ({len(text)} chars), capturing full HTML as fallback")
                try:
                    html_result = await session.call_tool("browser_evaluate", {
                        "function": "() => document.documentElement.outerHTML"
                    })
                    _check_tool_result(html_result, "browser_evaluate")
                    html_text = _extract_content_text(getattr(html_result, "content", None))
                    
                    if len(html_text) > len(text):
                        logger.info(f"MCP: Using full HTML instead ({len(html_text)} chars vs {len(text)} chars)")
                        text = html_text
                except InspectionFailedError:
                    raise
                except Exception as e:
                    logger.debug(f"MCP: HTML fallback failed: {e}")
            
            if not text or not text.strip():
                logger.warning("MCP: DOM snapshot is empty")
                raise InspectionFailedError(
                    f"MCP inspection of {url!r} returned an empty DOM snapshot. "
                    "The page may require authentication or JavaScript to render content. "
                    "Verify the URL is correct and the page loads without login."
                )

            logger.info("MCP: DOM captured successfully")
            # Ensure browser_close is called even if it fails
            try:
                await session.call_tool("browser_close", {})
            except Exception as e:
                logger.warning(f"MCP: browser_close failed: {e}")
            
            return text

    @staticmethod
    def _run_async(coro, timeout: Optional[float] = 60.0):
        """Run an async coroutine from synchronous code with optional timeout."""
        async def _with_timeout():
            if timeout and timeout > 0:
                return await asyncio.wait_for(coro, timeout=timeout)
            return await coro

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _with_timeout())
                return future.result()
        else:
            return asyncio.run(_with_timeout())

    def is_available(self) -> bool:
        """Check whether the MCP command is reachable on this system."""
        if not self.settings.enabled:
            return False
        return shutil.which(self.settings.command) is not None
