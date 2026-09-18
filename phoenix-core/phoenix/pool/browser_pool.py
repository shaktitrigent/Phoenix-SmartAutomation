"""Browser Pool - Efficient browser resource management.

Provides browser reuse, context reuse, and automatic cleanup to prevent
resource leaks and improve test execution performance.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BrowserInstance:
    """Represents a single browser instance with its contexts."""
    browser_id: str
    playwright_instance: Any
    contexts: List[Any] = field(default_factory=list)
    pages: List[Any] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    is_active: bool = True


@dataclass
class PoolMetrics:
    """Browser pool metrics."""
    total_browsers_created: int = 0
    total_browsers_closed: int = 0
    total_contexts_created: int = 0
    total_pages_created: int = 0
    active_browsers: int = 0
    active_contexts: int = 0
    active_pages: int = 0
    browser_reuse_count: int = 0
    context_reuse_count: int = 0
    page_reuse_count: int = 0


class BrowserPool:
    """Browser pool for efficient resource management.
    
    Features:
    - Browser reuse across tests
    - Context reuse within browsers
    - Automatic cleanup of idle resources
    - Resource leak detection
    - Comprehensive metrics tracking
    """
    
    def __init__(
        self,
        max_browsers: int = 5,
        max_contexts_per_browser: int = 5,
        max_pages_per_context: int = 10,
        idle_timeout_ms: int = 30000,  # 30 seconds
        enable_auto_cleanup: bool = True,
    ):
        self.max_browsers = max_browsers
        self.max_contexts_per_browser = max_contexts_per_browser
        self.max_pages_per_context = max_pages_per_context
        self.idle_timeout_ms = idle_timeout_ms
        self.enable_auto_cleanup = enable_auto_cleanup
        
        self.browsers: Dict[str, BrowserInstance] = {}
        self.metrics = PoolMetrics()
        self._lock = threading.Lock()
        
        logger.info(
            "Browser Pool initialized: max_browsers=%d, max_contexts=%d, "
            "max_pages=%d, idle_timeout=%dms, auto_cleanup=%s",
            max_browsers, max_contexts_per_browser, max_pages_per_context,
            idle_timeout_ms, enable_auto_cleanup
        )
    
    def get_browser(self, playwright_instance: Any) -> Tuple[str, Any]:
        """Get or create a browser instance.
        
        Args:
            playwright_instance: Playwright instance
            
        Returns:
            Tuple of (browser_id, browser object)
        """
        with self._lock:
            # Try to reuse an existing browser
            for browser_id, browser in self.browsers.items():
                if browser.is_active and len(browser.contexts) < self.max_contexts_per_browser:
                    self.metrics.browser_reuse_count += 1
                    browser.last_used_at = time.time()
                    logger.info("Browser Pool: Reusing browser %s (total reuse: %d)", 
                               browser_id, self.metrics.browser_reuse_count)
                    return browser_id, browser.playwright_instance
            
            # Create new browser if under limit
            if len(self.browsers) < self.max_browsers:
                browser_id = f"browser_{self.metrics.total_browsers_created}"
                
                try:
                    browser = playwright_instance.chromium.launch(headless=False)
                    
                    browser_instance = BrowserInstance(
                        browser_id=browser_id,
                        playwright_instance=browser,
                        contexts=[],
                        pages=[],
                        created_at=time.time(),
                        last_used_at=time.time(),
                        is_active=True
                    )
                    
                    self.browsers[browser_id] = browser_instance
                    self.metrics.total_browsers_created += 1
                    self.metrics.active_browsers += 1
                    
                    logger.info("Browser Pool: Created new browser %s (total: %d, active: %d)",
                               browser_id, self.metrics.total_browsers_created, self.metrics.active_browsers)
                    
                    return browser_id, browser
                    
                except Exception as e:
                    logger.error("Browser Pool: Failed to create browser: %s", str(e))
                    raise
            
            # Pool full - clean up idle browsers first
            if self.enable_auto_cleanup:
                self._cleanup_idle_browsers()
            
            # Still no available browser
            raise Exception("Browser pool exhausted - all browsers are at capacity")
    
    def get_context(self, browser_id: str, browser: Any) -> Tuple[str, Any]:
        """Get or create a context for a browser.
        
        Args:
            browser_id: Browser identifier
            browser: Browser object
            
        Returns:
            Tuple of (context_id, context object)
        """
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                raise ValueError(f"Browser {browser_id} not found in pool")
            
            # Try to reuse an existing context
            if browser_instance.contexts:
                context = browser_instance.contexts[0]
                self.metrics.context_reuse_count += 1
                browser_instance.last_used_at = time.time()
                logger.info("Browser Pool: Reusing context for %s (total reuse: %d)",
                           browser_id, self.metrics.context_reuse_count)
                return "reused_context", context
            
            # Create new context
            if len(browser_instance.contexts) < self.max_contexts_per_browser:
                context_id = f"context_{self.metrics.total_contexts_created}"
                
                try:
                    context = browser.new_context()
                    
                    browser_instance.contexts.append(context)
                    self.metrics.total_contexts_created += 1
                    self.metrics.active_contexts += 1
                    
                    logger.info("Browser Pool: Created new context %s for browser %s (total: %d)",
                               context_id, browser_id, self.metrics.total_contexts_created)
                    
                    return context_id, context
                    
                except Exception as e:
                    logger.error("Browser Pool: Failed to create context: %s", str(e))
                    raise
            
            raise Exception(f"Browser {browser_id} has reached maximum context limit")
    
    def get_page(self, context: Any, browser_id: str) -> Tuple[str, Any]:
        """Get or create a page for a context.
        
        Args:
            context: Browser context
            browser_id: Browser identifier
            
        Returns:
            Tuple of (page_id, page object)
        """
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                raise ValueError(f"Browser {browser_id} not found in pool")
            
            # Try to reuse an existing page
            if browser_instance.pages:
                page = browser_instance.pages[0]
                self.metrics.page_reuse_count += 1
                browser_instance.last_used_at = time.time()
                logger.info("Browser Pool: Reusing page for %s (total reuse: %d)",
                           browser_id, self.metrics.page_reuse_count)
                return "reused_page", page
            
            # Create new page
            if len(browser_instance.pages) < self.max_pages_per_context:
                page_id = f"page_{self.metrics.total_pages_created}"
                
                try:
                    page = context.new_page()
                    
                    browser_instance.pages.append(page)
                    self.metrics.total_pages_created += 1
                    self.metrics.active_pages += 1
                    
                    logger.info("Browser Pool: Created new page %s for browser %s (total: %d)",
                               page_id, browser_id, self.metrics.total_pages_created)
                    
                    return page_id, page
                    
                except Exception as e:
                    logger.error("Browser Pool: Failed to create page: %s", str(e))
                    raise
            
            raise Exception(f"Browser {browser_id} has reached maximum page limit")
    
    def release_page(self, browser_id: str, page: Any) -> None:
        """Release a page back to the pool."""
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                return
            
            if page in browser_instance.pages:
                browser_instance.pages.remove(page)
                self.metrics.active_pages -= 1
                logger.info("Browser Pool: Released page from browser %s (active pages: %d)",
                           browser_id, self.metrics.active_pages)
                
                # Close the page
                try:
                    page.close()
                except Exception as e:
                    logger.warning("Browser Pool: Failed to close page: %s", str(e))
    
    def release_context(self, browser_id: str, context: Any) -> None:
        """Release a context back to the pool."""
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                return
            
            if context in browser_instance.contexts:
                browser_instance.contexts.remove(context)
                self.metrics.active_contexts -= 1
                logger.info("Browser Pool: Released context from browser %s (active contexts: %d)",
                           browser_id, self.metrics.active_contexts)
                
                # Close the context
                try:
                    context.close()
                except Exception as e:
                    logger.warning("Browser Pool: Failed to close context: %s", str(e))
    
    def release_browser(self, browser_id: str) -> None:
        """Release a browser back to the pool."""
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                return
            
            # Mark as inactive
            browser_instance.is_active = False
            self.metrics.active_browsers -= 1
            self.metrics.total_browsers_closed += 1
            
            logger.info("Browser Pool: Released browser %s (active browsers: %d)",
                       browser_id, self.metrics.active_browsers)
    
    def close_browser(self, browser_id: str) -> None:
        """Close a browser instance completely."""
        with self._lock:
            browser_instance = self.browsers.get(browser_id)
            if not browser_instance:
                return
            
            # Close all pages
            for page in browser_instance.pages[:]:
                try:
                    page.close()
                except Exception as e:
                    logger.warning("Browser Pool: Failed to close page during browser close: %s", str(e))
            
            # Close all contexts
            for context in browser_instance.contexts[:]:
                try:
                    context.close()
                except Exception as e:
                    logger.warning("Browser Pool: Failed to close context during browser close: %s", str(e))
            
            # Close browser
            try:
                browser_instance.playwright_instance.close()
            except Exception as e:
                logger.warning("Browser Pool: Failed to close browser: %s", str(e))
            
            # Remove from pool
            del self.browsers[browser_id]
            self.metrics.active_browsers -= 1
            
            logger.info("Browser Pool: Closed browser %s (remaining: %d)",
                       browser_id, len(self.browsers))
    
    def _cleanup_idle_browsers(self) -> None:
        """Clean up idle browsers based on timeout."""
        current_time = time.time()
        idle_browsers = []
        
        for browser_id, browser in self.browsers.items():
            idle_time_ms = (current_time - browser.last_used_at) * 1000
            if idle_time_ms > self.idle_timeout_ms and len(browser.contexts) == 0:
                idle_browsers.append(browser_id)
        
        for browser_id in idle_browsers:
            logger.info("Browser Pool: Closing idle browser %s (idle: %.0fms)",
                       browser_id, (current_time - self.browsers[browser_id].last_used_at) * 1000)
            self.close_browser(browser_id)
    
    def cleanup_all(self) -> None:
        """Clean up all browser resources."""
        with self._lock:
            browser_ids = list(self.browsers.keys())
            for browser_id in browser_ids:
                self.close_browser(browser_id)
            
            logger.info("Browser Pool: Cleanup complete - all browsers closed")
    
    def get_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        with self._lock:
            return self.metrics
    
    def detect_leaks(self) -> Dict[str, Any]:
        """Detect potential resource leaks.
        
        Returns:
            Dictionary with leak detection results
        """
        with self._lock:
            leaks = {
                "leaked_browsers": [],
                "leaked_contexts": [],
                "leaked_pages": [],
                "total_leaked": 0,
            }
            
            for browser_id, browser in self.browsers.items():
                if browser.is_active:
                    if len(browser.contexts) > 0:
                        # Check for contexts without pages
                        for context in browser.contexts:
                            if len(browser.pages) == 0:
                                leaks["leaked_contexts"].append(browser_id)
                    
                    # Check for browsers without active use
                    idle_time = (time.time() - browser.last_used_at) * 1000
                    if idle_time > self.idle_timeout_ms * 2:  # Double timeout for leak detection
                        leaks["leaked_browsers"].append(browser_id)
            
            leaks["total_leaked"] = (
                len(leaks["leaked_browsers"]) + 
                len(leaks["leaked_contexts"]) + 
                len(leaks["leaked_pages"])
            )
            
            if leaks["total_leaked"] > 0:
                logger.warning(
                    "Browser Pool: Detected %d potential resource leaks: %s",
                    leaks["total_leaked"], leaks
                )
            else:
                logger.info("Browser Pool: No resource leaks detected")
            
            return leaks