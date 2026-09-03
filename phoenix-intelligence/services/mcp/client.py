"""Playwright MCP client — uses the MCP Python SDK over stdio to inspect pages."""

import asyncio
import logging
import shutil
import time
from typing import Optional, Tuple

from services.config import MCPSettings
from services.dom_grounding import combine_inspection_for_prompt, strip_noise_from_html

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
        # Last inspection pair (html, accessibility_tree) for callers that need both.
        self.last_html: str = ""
        self.last_accessibility_tree: str = ""

    def inspect_page(self, url: str, project: str = "default", page: str = "default", execution_id: str = "") -> str:
        """Navigate to *url* and return an LLM-ready DOM grounding snapshot.

        Captures **both** full HTML and an accessibility tree when possible.
        Stored snapshots keep HTML in ``dom_content`` and a11y separately.
        The returned string prefers an interactive-element map + HTML + a11y
        for locator grounding (application-agnostic).

        Raises:
            InspectionFailedError: When the MCP connection fails or returns an
                empty snapshot.
        """
        try:
            print(f"[PHOENIX MCP] === MCP INSPECTION STARTED ===")
            print(f"[PHOENIX MCP] URL: {url}")
            print(f"[PHOENIX MCP] Project: {project}")
            print(f"[PHOENIX MCP] Page: {page}")
            print(f"[PHOENIX MCP] Execution ID: {execution_id}")
        except (UnicodeEncodeError, OSError):
            pass

        logger.info("[PHOENIX MCP] MCP inspection started for %s", url)

        if not self.settings.enabled:
            logger.info("MCP is disabled via configuration — skipping page inspection")
            print("[PHOENIX MCP] MCP DISABLED - skipping inspection")
            return ""

        if self.dom_snapshot_manager and execution_id:
            logger.info("[PHOENIX MCP] Checking for reusable DOM snapshot before inspect_page")

            def capture_via_mcp(target_url: str):
                print(f"[PHOENIX MCP] Starting MCP capture for: {target_url}")
                start_time = time.time()
                html, a11y = self._run_async(self._inspect_page_async(target_url))
                duration = time.time() - start_time
                print(f"[PHOENIX MCP] MCP capture completed in {duration:.2f}s")
                print(
                    f"[PHOENIX MCP] HTML={len(html)} chars, a11y={len(a11y)} chars"
                )
                return html, a11y

            try:
                dom_content, reuse_decision = self.dom_snapshot_manager.get_dom_with_automatic_reuse(
                    url=url,
                    project=project,
                    page=page,
                    execution_id=execution_id,
                    capture_func=capture_via_mcp,
                    current_dom=None,
                )

                a11y = ""
                try:
                    snap = self.dom_snapshot_manager.load_latest_dom_snapshot(project, page)
                    if snap:
                        a11y = snap.accessibility_tree or ""
                        if not dom_content:
                            dom_content = snap.dom_content or ""
                except Exception:
                    pass

                self.last_html = dom_content or ""
                self.last_accessibility_tree = a11y or ""
                prompt_snapshot = combine_inspection_for_prompt(self.last_html, self.last_accessibility_tree)

                if self.artifacts_manager and prompt_snapshot:
                    from phoenix.execution.artifacts import MCPResponseRecord

                    mcp_record = MCPResponseRecord(
                        url=url,
                        snapshot_text=prompt_snapshot,
                        snapshot_size_bytes=len(prompt_snapshot.encode("utf-8")),
                        duration_seconds=reuse_decision.time_saved_ms / 1000 if reuse_decision.mcp_skipped else 0.0,
                        success=True,
                    )
                    self.artifacts_manager.save_mcp_response(mcp_record)

                print(f"[PHOENIX MCP] === MCP INSPECTION COMPLETED ===")
                print(f"[PHOENIX MCP] Prompt snapshot size: {len(prompt_snapshot)} chars")
                print(f"[PHOENIX MCP] Cache result: {'HIT' if reuse_decision.mcp_skipped else 'MISS'}")
                return prompt_snapshot

            except Exception as exc:
                logger.warning("[PHOENIX MCP] DOM reuse failed, falling back to direct MCP: %s", exc)
                print("[PHOENIX MCP] DOM reuse failed, falling back to direct MCP")

        print("[PHOENIX MCP] Starting direct MCP call")
        start_time = time.time()
        try:
            html, a11y = self._run_async(self._inspect_page_async(url))
            duration = time.time() - start_time
            self.last_html = html or ""
            self.last_accessibility_tree = a11y or ""
            prompt_snapshot = combine_inspection_for_prompt(self.last_html, self.last_accessibility_tree)

            print(f"[PHOENIX MCP] Direct MCP call completed in {duration:.2f}s")
            print(f"[PHOENIX MCP] Prompt snapshot size: {len(prompt_snapshot)} chars")

            if self.artifacts_manager and prompt_snapshot:
                from phoenix.execution.artifacts import MCPResponseRecord

                mcp_record = MCPResponseRecord(
                    url=url,
                    snapshot_text=prompt_snapshot,
                    snapshot_size_bytes=len(prompt_snapshot.encode("utf-8")),
                    duration_seconds=duration,
                    success=True,
                )
                self.artifacts_manager.save_mcp_response(mcp_record)

            print("[PHOENIX MCP] === MCP INSPECTION COMPLETED ===")
            if not prompt_snapshot.strip():
                raise InspectionFailedError(
                    f"MCP inspection of {url!r} returned an empty DOM snapshot. "
                    "The page may require authentication or JavaScript to render content."
                )
            return prompt_snapshot
        except InspectionFailedError:
            raise
        except Exception as exc:
            duration = time.time() - start_time
            print(f"[PHOENIX MCP] ✗ MCP call FAILED after {duration:.2f}s")

            if self.artifacts_manager:
                from phoenix.execution.artifacts import MCPResponseRecord

                mcp_record = MCPResponseRecord(
                    url=url,
                    snapshot_text="",
                    snapshot_size_bytes=0,
                    duration_seconds=duration,
                    success=False,
                    error_message=str(exc),
                )
                self.artifacts_manager.save_mcp_response(mcp_record)

            raise InspectionFailedError(
                f"MCP browser connection failed while inspecting {url!r}. "
                "Cannot generate automation without a DOM snapshot. "
                "Check that: (1) the page is accessible, (2) no authentication/CAPTCHA blocks "
                "the initial load, (3) the @playwright/mcp server is running."
            ) from exc

    async def _inspect_page_async(self, url: str) -> Tuple[str, str]:
        """Connect, navigate, capture HTML + accessibility tree, disconnect.

        Returns:
            ``(html, accessibility_tree)`` — either may be empty on partial failure.
        """
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

            logger.info("MCP: waiting for page load and SPA rendering")
            await asyncio.sleep(2)

            html_text = ""
            max_wait_attempts = 5
            for attempt in range(max_wait_attempts):
                await asyncio.sleep(0.5)
                logger.info(
                    "MCP: checking if page has rendered (attempt %d/%d)",
                    attempt + 1,
                    max_wait_attempts,
                )
                try:
                    html_text = await self._evaluate_outer_html(session)
                    meaningful = (
                        html_text.count("<input")
                        + html_text.count("<button")
                        + html_text.count("<form")
                        + html_text.count("<a ")
                    )
                    if len(html_text) > 100 and meaningful > 0:
                        logger.info(
                            "MCP: Page has rendered content (%d bytes, %d interactive tags)",
                            len(html_text),
                            meaningful,
                        )
                        break
                except Exception as exc:
                    logger.debug("MCP: DOM check failed: %s", exc)

            # Always capture a fresh HTML snapshot for attribute-accurate locators.
            try:
                fresh_html = await self._evaluate_outer_html(session)
                if len(fresh_html) >= len(html_text):
                    html_text = fresh_html
            except Exception as exc:
                logger.warning("MCP: final HTML capture failed: %s", exc)

            logger.info("MCP: taking accessibility snapshot")
            a11y_text = ""
            try:
                snapshot_result = await session.call_tool("browser_snapshot", {})
                a11y_text = self._tool_result_text(snapshot_result)
            except Exception as exc:
                logger.warning("MCP: accessibility snapshot failed: %s", exc)

            logger.info(
                "MCP: capture complete html=%d chars a11y=%d chars",
                len(html_text),
                len(a11y_text),
            )

            # Prefer storing cleaned HTML (scripts/styles removed) to keep artifacts smaller
            # while preserving ids/names/placeholders needed for locators.
            if html_text:
                html_text = strip_noise_from_html(html_text, max_chars=500_000)

            await session.call_tool("browser_close", {})
            return html_text, a11y_text

    @staticmethod
    def _tool_result_text(result) -> str:
        """Flatten MCP tool content blocks into a single string."""
        text = ""
        if result and getattr(result, "content", None):
            for block in result.content:
                if hasattr(block, "text"):
                    text += block.text or ""
                elif isinstance(block, dict):
                    text += block.get("text", "") or ""
        return text

    @staticmethod
    def _normalize_evaluate_html(raw: str) -> str:
        """Normalize browser_evaluate output; drop MCP error payloads."""
        import json
        import re

        text = (raw or "").strip()
        if not text:
            return ""
        # Never treat tool schema/runtime errors as HTML DOM.
        if text.startswith("### Error") or "Invalid arguments for tool" in text:
            return ""

        # @playwright/mcp wraps successful evaluates as: ### Result "<html...>"
        if text.startswith("### Result"):
            text = text[len("### Result") :].strip()

        if text.startswith('"'):
            # Prefer strict JSON; fall back to first..last quote slice (large HTML
            # may contain characters that break a naive loads of the full blob).
            decoded: Optional[str] = None
            try:
                value = json.loads(text)
                if isinstance(value, str):
                    decoded = value
            except Exception:
                end = text.rfind('"')
                if end > 0:
                    try:
                        value = json.loads(text[: end + 1])
                        if isinstance(value, str):
                            decoded = value
                    except Exception:
                        inner = text[1:end]
                        decoded = (
                            inner.replace("\\\\", "\0")
                            .replace('\\"', '"')
                            .replace("\\n", "\n")
                            .replace("\\r", "\r")
                            .replace("\\t", "\t")
                            .replace("\0", "\\")
                        )
            if decoded is not None:
                text = decoded

        # Drop any non-HTML prefix; keep from the document root tag.
        match = re.search(r"(?is)<(!DOCTYPE\s+html|html)\b", text)
        if match:
            text = text[match.start() :]
        if "<" not in text:
            return ""
        return text.strip()

    @classmethod
    async def _evaluate_outer_html(cls, session) -> str:
        """Return documentElement.outerHTML via MCP browser_evaluate.

        Current ``@playwright/mcp`` expects ``function`` (not ``expression``).
        Older builds used ``expression`` — try both for compatibility.
        """
        js = "() => document.documentElement.outerHTML"
        last_error = ""
        for args in ({"function": js}, {"expression": js}):
            try:
                result = await session.call_tool("browser_evaluate", args)
                html = cls._normalize_evaluate_html(cls._tool_result_text(result))
                if html:
                    return html
                # Keep raw text for diagnostics when both shapes fail
                raw = cls._tool_result_text(result)
                if raw:
                    last_error = raw[:300]
            except Exception as exc:
                last_error = str(exc)
                logger.debug("MCP browser_evaluate with %s failed: %s", list(args), exc)
        if last_error:
            logger.warning(
                "MCP browser_evaluate returned no usable HTML (%s)",
                last_error[:200],
            )
        return ""

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
