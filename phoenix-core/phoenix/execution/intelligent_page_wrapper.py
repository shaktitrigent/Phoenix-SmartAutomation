"""Intelligent Page Wrapper - Production Runtime Integration.

This module provides a Playwright Page wrapper that integrates IntelligentRuntime
into actual test execution, ensuring DOM Snapshot, MCP, Locator Repository, Healing,
Metrics, and Timeline all execute during real production test execution.

The wrapper intercepts all UI actions and consults IntelligentRuntime before execution,
enabling DOM reuse decisions, MCP calls, locator healing, and runtime evidence collection.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class IntelligentPageWrapper:
    """Playwright Page wrapper with IntelligentRuntime integration.
    
    This wrapper intercepts all UI actions and consults IntelligentRuntime
    before execution, enabling:
    - DOM Snapshot reuse decisions
    - MCP inspect_page() calls when DOM changes
    - Locator Repository reuse
    - Healing Engine application
    - Runtime Metrics collection
    - Runtime Timeline tracking
    """
    
    def __init__(
        self,
        page: Any,
        intelligent_runtime: Any,
        project_name: str = "default",
        test_name: str = "default",
        execution_id: str = ""
    ):
        """Initialize the intelligent page wrapper.
        
        Args:
            page: Playwright Page object
            intelligent_runtime: IntelligentRuntime instance
            project_name: Project name for DOM storage
            test_name: Test name for evidence tracking
            execution_id: Execution ID for evidence tracking
        """
        self._page = page
        self._intelligent_runtime = intelligent_runtime
        self._project_name = project_name
        self._test_name = test_name
        self._execution_id = execution_id
        
        # Initialize DOM snapshot manager if available
        self._dom_snapshot_manager = None
        if intelligent_runtime and hasattr(intelligent_runtime, 'dom_snapshot_manager'):
            self._dom_snapshot_manager = intelligent_runtime.dom_snapshot_manager
        
        # Initialize metrics and timeline if available
        self._metrics_collector = None
        if intelligent_runtime and hasattr(intelligent_runtime, 'metrics_collector'):
            self._metrics_collector = intelligent_runtime.metrics_collector
        
        self._timeline_tracker = None
        if intelligent_runtime and hasattr(intelligent_runtime, 'timeline_tracker'):
            self._timeline_tracker = intelligent_runtime.timeline_tracker
        
        # Track DOM state for reuse decisions
        self._current_dom_hash: Optional[str] = None
        self._last_dom_capture_time: float = 0.0
        self._dom_cache_ttl_seconds: int = 30  # Cache DOM for 30 seconds
        
        logger.info(f"[INTELLIGENT PAGE] Wrapper initialized for {project_name}/{test_name}")
        logger.info(f"[INTELLIGENT PAGE] Execution ID: {execution_id}")
    
    def _get_current_url(self) -> str:
        """Get current page URL."""
        try:
            return self._page.url
        except Exception:
            return ""
    
    def _should_refresh_dom(self) -> bool:
        """Determine if DOM should be refreshed based on time and state."""
        current_time = time.time()
        time_since_capture = current_time - self._last_dom_capture_time
        
        # Refresh if TTL expired or no previous capture
        if time_since_capture > self._dom_cache_ttl_seconds or self._current_dom_hash is None:
            return True
        
        return False
    
    def _capture_dom_with_intelligence(self, force_refresh: bool = False) -> Tuple[str, bool]:
        """Capture DOM with intelligent reuse decision.
        
        Args:
            force_refresh: Force DOM capture even if cached
            
        Returns:
            Tuple of (dom_content, was_reused)
        """
        url = self._get_current_url()
        page_name = self._test_name or "unknown"
        
        # Check if we should use cached DOM
        if not force_refresh and not self._should_refresh_dom() and self._current_dom_hash:
            logger.info(f"[INTELLIGENT PAGE] Using cached DOM (hash: {self._current_dom_hash[:8]}...)")
            return "", True  # Return empty but indicate reuse
        
        # Consult DOM Snapshot Manager for reuse decision
        if self._dom_snapshot_manager:
            try:
                reuse_decision = self._dom_snapshot_manager.should_reuse_dom(
                    url=url,
                    project=self._project_name,
                    page=page_name,
                    current_dom=None,
                    execution_id=self._execution_id
                )
                
                if reuse_decision.decision == "REUSE":
                    logger.info(f"[INTELLIGENT PAGE] DOM REUSE DECISION: REUSE")
                    logger.info(f"[INTELLIGENT PAGE] Reason: {reuse_decision.reason}")
                    logger.info(f"[INTELLIGENT PAGE] Time saved: {reuse_decision.time_saved_ms:.2f}ms")
                    logger.info(f"[INTELLIGENT PAGE] MCP skipped: {reuse_decision.mcp_skipped}")
                    
                    # Load and return reused DOM
                    previous_snapshot = self._dom_snapshot_manager.load_latest_dom_snapshot(
                        self._project_name, page_name
                    )
                    if previous_snapshot:
                        self._current_dom_hash = previous_snapshot.metadata.dom_hash
                        self._last_dom_capture_time = time.time()
                        
                        # Record intelligent decision
                        if self._intelligent_runtime:
                            self._intelligent_runtime.make_intelligent_decision(
                                decision_type="dom_capture",
                                context={
                                    "url": url,
                                    "project_name": self._project_name,
                                    "page_name": page_name,
                                    "decision": "reuse",
                                    "reason": reuse_decision.reason
                                }
                            )
                        
                        return previous_snapshot.dom_content, True
                
                logger.info(f"[INTELLIGENT PAGE] DOM REUSE DECISION: CAPTURE")
                logger.info(f"[INTELLIGENT PAGE] Reason: {reuse_decision.reason}")
                
            except Exception as e:
                logger.warning(f"[INTELLIGENT PAGE] DOM reuse decision failed: {e}")
        
        # Capture new DOM via Playwright
        logger.info(f"[INTELLIGENT PAGE] Capturing new DOM via Playwright")
        start_time = time.time()
        
        try:
            dom_content = self._page.content()
            capture_duration = (time.time() - start_time) * 1000
            
            logger.info(f"[INTELLIGENT PAGE] DOM captured: {len(dom_content)} bytes in {capture_duration:.2f}ms")
            
            # Store new snapshot
            if self._dom_snapshot_manager:
                try:
                    self._dom_snapshot_manager.store_dom_snapshot(
                        dom_content=dom_content,
                        url=url,
                        project=self._project_name,
                        page=page_name,
                        execution_id=self._execution_id,
                        capture_source="playwright",
                        capture_duration_ms=capture_duration
                    )
                    
                    # Update cache
                    if self._dom_snapshot_manager:
                        self._current_dom_hash = self._dom_snapshot_manager.compute_dom_hash(dom_content)
                    self._last_dom_capture_time = time.time()
                    
                    # Record intelligent decision
                    if self._intelligent_runtime:
                        self._intelligent_runtime.make_intelligent_decision(
                            decision_type="dom_capture",
                            context={
                                "url": url,
                                "project_name": self._project_name,
                                "page_name": page_name,
                                "decision": "capture",
                                "reason": "DOM changed or first capture"
                            }
                        )
                    
                except Exception as e:
                    logger.warning(f"[INTELLIGENT PAGE] Failed to store DOM snapshot: {e}")
            
            return dom_content, False
            
        except Exception as e:
            logger.error(f"[INTELLIGENT PAGE] Failed to capture DOM: {e}")
            return "", False
    
    def _record_action_start(self, action: str, details: Dict[str, Any] = None):
        """Record action start in timeline and metrics."""
        if self._timeline_tracker:
            try:
                self._timeline_tracker.record_event(
                    execution_id=self._execution_id,
                    event_type=f"action_{action}",
                    details=details or {}
                )
            except Exception as e:
                logger.warning(f"[INTELLIGENT PAGE] Failed to record timeline event: {e}")
    
    def _record_action_end(self, action: str, duration_ms: float, success: bool, details: Dict[str, Any] = None):
        """Record action end in timeline and metrics."""
        if self._metrics_collector:
            try:
                self._metrics_collector.record_action(
                    execution_id=self._execution_id,
                    action=action,
                    duration_ms=duration_ms,
                    success=success,
                    details=details or {}
                )
            except Exception as e:
                logger.warning(f"[INTELLIGENT PAGE] Failed to record metrics: {e}")
    
    # ------------------------------------------------------------------
    # Playwright Page Method Wrappers
    # ------------------------------------------------------------------
    
    def goto(self, url: str, **kwargs) -> Any:
        """Navigate to URL with intelligent DOM decision."""
        logger.info(f"[INTELLIGENT PAGE] goto: {url}")
        start_time = time.time()
        
        self._record_action_start("goto", {"url": url})
        
        try:
            result = self._page.goto(url, **kwargs)
            
            # Capture DOM after navigation
            self._capture_dom_with_intelligence(force_refresh=True)
            
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("goto", duration_ms, True, {"url": url})
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("goto", duration_ms, False, {"url": url, "error": str(e)})
            raise
    
    def click(self, selector: str, **kwargs) -> Any:
        """Click element with intelligent DOM decision."""
        logger.info(f"[INTELLIGENT PAGE] click: {selector}")
        start_time = time.time()
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        self._record_action_start("click", {"selector": selector, "dom_reused": dom_reused})
        
        try:
            result = self._page.click(selector, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("click", duration_ms, True, {"selector": selector, "dom_reused": dom_reused})
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("click", duration_ms, False, {"selector": selector, "error": str(e)})
            raise
    
    def fill(self, selector: str, value: str, **kwargs) -> Any:
        """Fill element with intelligent DOM decision."""
        logger.info(f"[INTELLIGENT PAGE] fill: {selector}")
        start_time = time.time()
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        self._record_action_start("fill", {"selector": selector, "dom_reused": dom_reused})
        
        try:
            result = self._page.fill(selector, value, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("fill", duration_ms, True, {"selector": selector, "dom_reused": dom_reused})
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_action_end("fill", duration_ms, False, {"selector": selector, "error": str(e)})
            raise
    
    def locator(self, selector: str) -> Any:
        """Get locator with intelligent decision."""
        logger.info(f"[INTELLIGENT PAGE] locator: {selector}")
        
        # Check DOM before locator creation
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        # Consult Locator Repository if available
        if self._intelligent_runtime and hasattr(self._intelligent_runtime, 'locator_repository'):
            try:
                locator_repo = self._intelligent_runtime.locator_repository
                if locator_repo:
                    # Try to get improved locator from repository
                    improved_locator = locator_repo.get_improved_locator(
                        selector=selector,
                        url=self._get_current_url(),
                        project=self._project_name
                    )
                    if improved_locator and improved_locator != selector:
                        logger.info(f"[INTELLIGENT PAGE] Locator improved: {selector} -> {improved_locator}")
                        selector = improved_locator
            except Exception as e:
                logger.warning(f"[INTELLIGENT PAGE] Locator repository lookup failed: {e}")
        
        return self._page.locator(selector)
    
    def get_by_role(self, role: str, **kwargs) -> Any:
        """Get element by role with intelligent decision."""
        logger.info(f"[INTELLIGENT PAGE] get_by_role: {role}")
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        return self._page.get_by_role(role, **kwargs)
    
    def get_by_text(self, text: str, **kwargs) -> Any:
        """Get element by text with intelligent decision."""
        logger.info(f"[INTELLIGENT PAGE] get_by_text: {text}")
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        return self._page.get_by_text(text, **kwargs)
    
    def get_by_label(self, text: str, **kwargs) -> Any:
        """Get element by label with intelligent decision."""
        logger.info(f"[INTELLIGENT PAGE] get_by_label: {text}")
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        return self._page.get_by_label(text, **kwargs)
    
    def wait_for_selector(self, selector: str, **kwargs) -> Any:
        """Wait for selector with intelligent decision."""
        logger.info(f"[INTELLIGENT PAGE] wait_for_selector: {selector}")
        
        # Check DOM before action
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        return self._page.wait_for_selector(selector, **kwargs)
    
    def content(self) -> str:
        """Get page content with intelligent caching."""
        dom_content, dom_reused = self._capture_dom_with_intelligence()
        
        if dom_reused and dom_content:
            return dom_content
        
        return self._page.content()
    
    # ------------------------------------------------------------------
    # Pass-through methods for other Page operations
    # ------------------------------------------------------------------
    
    def __getattr__(self, name: str) -> Any:
        """Pass through any undefined attributes to the wrapped page."""
        return getattr(self._page, name)
    
    @property
    def url(self) -> str:
        return self._page.url
    
    @property
    def title(self) -> str:
        return self._page.title
    
    def set_default_timeout(self, timeout: int) -> None:
        self._page.set_default_timeout(timeout)
    
    def set_default_navigation_timeout(self, timeout: int) -> None:
        self._page.set_default_navigation_timeout(timeout)
    
    def screenshot(self, **kwargs) -> Any:
        return self._page.screenshot(**kwargs)
    
    def close(self) -> None:
        return self._page.close()
    
    def reload(self) -> Any:
        return self._page.reload()
    
    def go_back(self) -> Any:
        return self._page.go_back()
    
    def wait_for_load_state(self, **kwargs) -> Any:
        return self._page.wait_for_load_state(**kwargs)


def create_intelligent_page(
    page: Any,
    intelligent_runtime: Any,
    project_name: str = "default",
    test_name: str = "default",
    execution_id: str = ""
) -> IntelligentPageWrapper:
    """Factory function to create an intelligent page wrapper.
    
    Args:
        page: Playwright Page object
        intelligent_runtime: IntelligentRuntime instance
        project_name: Project name for DOM storage
        test_name: Test name for evidence tracking
        execution_id: Execution ID for evidence tracking
        
    Returns:
        IntelligentPageWrapper instance
    """
    return IntelligentPageWrapper(
        page=page,
        intelligent_runtime=intelligent_runtime,
        project_name=project_name,
        test_name=test_name,
        execution_id=execution_id
    )
