"""Healing Engine - Comprehensive runtime healing for Phoenix Automation.

Provides automatic recovery from locator failures, stale elements, session issues,
and transient failures through multi-strategy healing with runtime verification.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HealingStrategy(Enum):
    """Healing strategy types."""
    RETRY = "retry"
    REFRESH_LOCATOR = "refresh_locator"
    DOM_REQUERY = "dom_requery"
    ALTERNATE_LOCATOR = "alternate_locator"
    SESSION_RECOVERY = "session_recovery"
    BROWSER_RECOVERY = "browser_recovery"


@dataclass
class HealingAttempt:
    """Record of a single healing attempt."""
    strategy: HealingStrategy
    timestamp: float
    success: bool
    duration_ms: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealingMetrics:
    """Aggregate healing metrics."""
    total_attempts: int = 0
    successful_healings: int = 0
    failed_healings: int = 0
    strategy_counts: Dict[str, int] = field(default_factory=dict)
    total_healing_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


class HealingEngine:
    """Comprehensive healing engine for Phoenix automation.
    
    Provides multi-strategy healing with:
    - Automatic retry with exponential backoff
    - Stale locator refresh
    - DOM re-query via MCP
    - Alternate locator fallback
    - Session recovery
    - Browser state recovery
    - Comprehensive metrics tracking
    - Flow-aware healing (Priority 21)
    - Component-aware healing (Priority 22)
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_ms: int = 1000,
        backoff_multiplier: float = 2.0,
        enable_dom_cache: bool = True,
        enable_session_recovery: bool = True,
        artifacts_manager=None,
        locator_repository=None,
        flow_discovery=None,
    ):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.enable_dom_cache = enable_dom_cache
        self.enable_session_recovery = enable_session_recovery
        self.artifacts_manager = artifacts_manager
        self.locator_repository = locator_repository
        self.flow_discovery = flow_discovery  # Priority 21: Flow Detection
        
        self.metrics = HealingMetrics()
        self.healing_history: List[HealingAttempt] = []
        
        # DOM cache
        self.dom_cache: Dict[str, Tuple[str, float]] = {}  # url -> (snapshot, timestamp)
        self.dom_cache_ttl_ms = 30000  # 30 seconds
        
        # Locator cache
        self.locator_cache: Dict[str, List[str]] = {}  # element_name -> [locators]
        
        # Session state
        self.session_state: Dict[str, Any] = {}
        
        logger.info(
            "Healing Engine initialized: max_retries=%d, retry_delay=%dms, "
            "backoff=%.1f, dom_cache=%s, session_recovery=%s, locator_repo=%s, flow_discovery=%s",
            max_retries, retry_delay_ms, backoff_multiplier,
            enable_dom_cache, enable_session_recovery,
            locator_repository is not None, flow_discovery is not None
        )
    
    def heal(
        self,
        element_name: str,
        locator: str,
        page: Any,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Heal a failed locator with comprehensive strategies.
        
        Args:
            element_name: Human-readable element name
            locator: The locator string that failed
            page: Playwright Page object
            context: Additional context (url, snapshot, etc.)
            
        Returns:
            True if healing succeeded, False otherwise
        """
        logger.info(f"[HEALING ENGINE] HEAL CALLED - Element: {element_name}, Locator: {locator}")
        context = context or {}
        logger.info(f"[HEALING] Attempting to heal locator: {element_name} -> {locator}")
        
        # Priority 22: Try component-aware healing first if semantic component is available
        semantic_component = context.get('semantic_component')
        if semantic_component:
            component_healed = self.heal_with_component_awareness(
                element_name, locator, page, semantic_component, context
            )
            if component_healed:
                return True
        
        self.metrics.total_attempts += 1
        healing_attempts = []
        last_error = None
        
        # Try different healing strategies
        strategies = self._apply_healing_strategies(locator, element_name, page, context)
        
        for strategy, strategy_func in strategies:
            attempt_start = time.time()
            
            try:
                # Apply the healing strategy
                improved_locator = strategy_func()
                
                if improved_locator and improved_locator != locator:
                    # Try the improved locator
                    logger.info(f"[HEALING] Trying improved locator: {improved_locator}")
                    
                    # Try a simple click with the improved locator
                    try:
                        page.click(improved_locator, timeout=5000)
                        
                        # Success - record metrics
                        duration_ms = (time.time() - attempt_start) * 1000
                        self.metrics.successful_healings += 1
                        self.metrics.total_healing_time_ms += duration_ms
                        
                        healing_attempt = HealingAttempt(
                            strategy=strategy,
                            timestamp=time.time(),
                            success=True,
                            duration_ms=duration_ms,
                            details={"original_locator": locator, "improved_locator": improved_locator}
                        )
                        healing_attempts.append(healing_attempt)
                        
                        # Persist the successful healing
                        self._persist_healing_success(element_name, improved_locator, context)
                        
                        logger.info(f"[HEALING] Successfully healed {element_name} using {strategy.value}")
                        return True
                        
                    except Exception as click_error:
                        logger.warning(f"[HEALING] Improved locator failed: {click_error}")
                        last_error = click_error
                        
                        healing_attempt = HealingAttempt(
                            strategy=strategy,
                            timestamp=time.time(),
                            success=False,
                            duration_ms=(time.time() - attempt_start) * 1000,
                            error_message=str(click_error),
                            details={"original_locator": locator, "improved_locator": improved_locator}
                        )
                        healing_attempts.append(healing_attempt)
                
            except Exception as e:
                logger.warning(f"[HEALING] Strategy {strategy.value} failed: {e}")
                last_error = e
                
                healing_attempt = HealingAttempt(
                    strategy=strategy,
                    timestamp=time.time(),
                    success=False,
                    duration_ms=(time.time() - attempt_start) * 1000,
                    error_message=str(e),
                    details={"original_locator": locator}
                )
                healing_attempts.append(healing_attempt)
        
        # All strategies failed
        self.metrics.failed_healings += 1
        self.healing_history.extend(healing_attempts)
        
        logger.error(f"[HEALING] Failed to heal {element_name} after {len(healing_attempts)} attempts")
        return False
    
    def heal_with_component_awareness(
        self,
        element_name: str,
        locator: str,
        page: Any,
        semantic_component: Any = None,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Heal using component-aware alternative locators (Priority 22).
        
        When a locator fails, this method uses component intelligence to find
        alternative locator strategies based on semantic understanding.
        
        Args:
            element_name: Human-readable element name
            locator: The locator string that failed
            page: Playwright Page object
            semantic_component: Semantic component with locator candidates
            context: Additional context
            
        Returns:
            True if healing succeeded, False otherwise
        """
        context = context or {}
        logger.info(f"[HEALING] Component-aware healing for {element_name}")
        
        if not semantic_component:
            logger.debug("[HEALING] No semantic component provided for component-aware healing")
            return False
        
        # Check if component has locator candidates (Priority 22)
        if not hasattr(semantic_component, 'locator_candidates') or not semantic_component.locator_candidates:
            logger.debug("[HEALING] Component has no locator candidates")
            return False
        
        # Try alternative locator candidates
        for candidate in semantic_component.locator_candidates:
            candidate_locator = candidate.get('locator')
            candidate_confidence = candidate.get('confidence', 0.0)
            
            if not candidate_locator or candidate_locator == locator:
                continue
            
            # Only try high-confidence candidates
            if candidate_confidence < 0.6:
                continue
            
            logger.info(f"[HEALING] Trying alternative locator (confidence: {candidate_confidence:.2f}): {candidate_locator}")
            
            try:
                page.click(candidate_locator, timeout=5000)
                
                # Success - record metrics
                self.metrics.successful_healings += 1
                self.metrics.total_healing_time_ms += 100  # Approximate time
                
                healing_attempt = HealingAttempt(
                    strategy=HealingStrategy.ALTERNATE_LOCATOR,
                    timestamp=time.time(),
                    success=True,
                    duration_ms=100,
                    details={
                        "original_locator": locator,
                        "alternative_locator": candidate_locator,
                        "confidence": candidate_confidence,
                        "strategy": "component_intelligence"
                    }
                )
                self.healing_history.append(healing_attempt)
                
                logger.info(f"[HEALING] Successfully healed {element_name} using component-aware locator")
                return True
                
            except Exception as e:
                logger.warning(f"[HEALING] Alternative locator failed: {e}")
                healing_attempt = HealingAttempt(
                    strategy=HealingStrategy.ALTERNATE_LOCATOR,
                    timestamp=time.time(),
                    success=False,
                    duration_ms=100,
                    error_message=str(e),
                    details={
                        "original_locator": locator,
                        "alternative_locator": candidate_locator,
                        "confidence": candidate_confidence,
                        "strategy": "component_intelligence"
                    }
                )
                self.healing_history.append(healing_attempt)
        
        # All component-aware locators failed
        self.metrics.failed_healings += 1
        logger.error(f"[HEALING] Component-aware healing failed for {element_name}")
        return False
    
    def heal_with_flow_awareness(
        self,
        element_name: str,
        locator: str,
        page: Any,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Heal using flow-aware alternative path discovery (Priority 21).
        
        When a test fails, this method uses discovered business flows to find
        alternative valid paths through the application.
        
        Args:
            element_name: Human-readable element name
            locator: The locator string that failed
            page: Playwright Page object
            context: Additional context
            
        Returns:
            Healing result with alternative path suggestions
        """
        context = context or {}
        result = {
            "healed": False,
            "alternative_locator": None,
            "alternative_path": None,
            "semantic_suggestion": None,
            "flow_context": None,
        }
        
        if not self.flow_discovery:
            logger.debug("[HEALING] Flow discovery not available for flow-aware healing")
            return result
        
        try:
            # Get current semantic context
            current_url = page.url if hasattr(page, 'url') else context.get('url', '')
            
            # Get discovered flows for the project
            project_name = context.get('project_name', 'default')
            flows = self.flow_discovery.get_discovered_flows(project_name)
            
            if not flows:
                logger.debug("[HEALING] No discovered flows available for healing")
                return result
            
            # Find flows that include the current page type
            current_page_type = context.get('page_type', 'unknown')
            relevant_flows = [
                flow for flow in flows
                if any(node.semantic_type == current_page_type for node in flow.nodes)
            ]
            
            if not relevant_flows:
                logger.debug(f"[HEALING] No flows found for page type: {current_page_type}")
                return result
            
            # Get high-confidence flows
            high_confidence_flows = [f for f in relevant_flows if f.confidence >= 0.7]
            
            if not high_confidence_flows:
                logger.debug("[HEALING] No high-confidence flows available")
                return result
            
            # Use the highest confidence flow
            best_flow = max(high_confidence_flows, key=lambda f: f.confidence)
            
            result["flow_context"] = {
                "flow_type": best_flow.flow_type.value,
                "flow_name": best_flow.flow_name,
                "confidence": best_flow.confidence,
                "current_position": current_page_type,
            }
            
            # Suggest semantic alternatives based on action type
            # This is a simplified version - in production, this would use
            # the full flow graph to find alternative paths
            if "submit" in element_name.lower() or "save" in element_name.lower():
                result["semantic_suggestion"] = "Consider semantic alternatives: 'Submit', 'Save', 'Confirm' buttons may represent the same action"
                result["alternative_path"] = "Try alternate form submission action"
            
            logger.info(f"[HEALING] Flow-aware healing: using flow {best_flow.flow_name} (confidence: {best_flow.confidence})")
            
        except Exception as e:
            logger.warning(f"[HEALING] Flow-aware healing failed: {e}")
        
        return result
    
    def heal_action(
        self,
        action: Callable,
        locator: str,
        element_name: str,
        page: Any,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Execute an action with comprehensive healing.
        
        Args:
            action: The action to execute (e.g., page.locator().click())
            locator: The locator string
            element_name: Human-readable element name
            page: Playwright Page object
            context: Additional context (url, snapshot, etc.)
            
        Returns:
            True if action succeeded, False otherwise
        """
        context = context or {}
        self.metrics.total_attempts += 1
        
        healing_attempts = []
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()
            
            try:
                # Try the action
                action()
                
                # Success - record metrics
                duration_ms = (time.time() - attempt_start) * 1000
                self.metrics.successful_healings += 1
                self.metrics.total_healing_time_ms += duration_ms
                
                healing_attempt = HealingAttempt(
                    strategy=HealingStrategy.RETRY,
                    timestamp=time.time(),
                    success=True,
                    duration_ms=duration_ms,
                    details={"attempt": attempt + 1}
                )
                healing_attempts.append(healing_attempt)
                
                logger.info(
                    "Healing SUCCESS: %s (attempt %d/%d, %.0fms)",
                    element_name, attempt + 1, self.max_retries + 1, duration_ms
                )
                
                self.healing_history.extend(healing_attempts)
                
                # Save healing report if artifacts manager is available
                if self.artifacts_manager:
                    self._save_healing_report(element_name, healing_attempts, locator, True)
                
                # Persist successful healing to locator repository
                if self.locator_repository and context:
                    self._persist_healing_success(element_name, locator, context)
                
                return True
                
            except Exception as e:
                last_error = e
                duration_ms = (time.time() - attempt_start) * 1000
                
                healing_attempt = HealingAttempt(
                    strategy=HealingStrategy.RETRY,
                    timestamp=time.time(),
                    success=False,
                    duration_ms=duration_ms,
                    error_message=str(e),
                    details={"attempt": attempt + 1}
                )
                healing_attempts.append(healing_attempt)
                
                logger.warning(
                    "Healing FAILED: %s (attempt %d/%d, %.0fms): %s",
                    element_name, attempt + 1, self.max_retries + 1, duration_ms, str(e)
                )
                
                # Try healing strategies
                if attempt < self.max_retries:
                    self._apply_healing_strategies(
                        locator, element_name, page, context, e, attempt
                    )
                
                # Exponential backoff
                if attempt < self.max_retries:
                    delay = self.retry_delay_ms * (self.backoff_multiplier ** attempt)
                    logger.info("Healing backoff: %.0fms before next attempt", delay)
                    time.sleep(delay / 1000.0)
        
        # All attempts failed
        self.metrics.failed_healings += 1
        self.healing_history.extend(healing_attempts)
        
        logger.error(
            "Healing EXHAUSTED: %s failed after %d attempts. Last error: %s",
            element_name, self.max_retries + 1, str(last_error)
        )
        
        # Save healing report if artifacts manager is available
        if self.artifacts_manager:
            self._save_healing_report(element_name, healing_attempts, locator, False)
        
        return False
    
    def _apply_healing_strategies(
        self,
        locator: str,
        element_name: str,
        page: Any,
        context: Dict[str, Any],
    ) -> List[Tuple[HealingStrategy, Callable]]:
        """Generate healing strategies to try.
        
        Returns:
            List of (strategy, function) tuples to try
        """
        strategies = []
        
        # Strategy 1: Try alternate locators from repository
        def try_alternate_locator():
            if self.locator_repository:
                improved = self.locator_repository.get_improved_locator(
                    selector=locator,
                    url=context.get("url", ""),
                    project=context.get("project_name", "default")
                )
                if improved:
                    logger.info(f"[HEALING] Found improved locator from repository: {improved}")
                    return improved
            return None
        
        strategies.append((HealingStrategy.ALTERNATE_LOCATOR, try_alternate_locator))
        
        # Strategy 2: Try DOM-based alternates
        def try_dom_alternates():
            alternates = self._get_alternate_locators(element_name, context)
            if alternates:
                for alt in alternates:
                    if alt != locator:
                        logger.info(f"[HEALING] Trying alternate locator: {alt}")
                        return alt
            return None
        
        strategies.append((HealingStrategy.DOM_REQUERY, try_dom_alternates))
        
        # Strategy 3: Try simple CSS variations
        def try_css_variations():
            # Try adding type attribute if it's an input
            if "input" in locator and "[name=" in locator:
                # Try by type instead
                import re
                name_match = re.search(r"name='([^']+)'", locator)
                if name_match:
                    name = name_match.group(1)
                    return f"input[name='{name}']"
            return None
        
        strategies.append((HealingStrategy.REFRESH_LOCATOR, try_css_variations))
        
        return strategies
        if self._is_browser_error(error):
            self._recover_browser(page, context)
            self.metrics.strategy_counts["browser_recovery"] = \
                self.metrics.strategy_counts.get("browser_recovery", 0) + 1
    
    def _is_stale_element_error(self, error: Exception) -> bool:
        """Check if error indicates stale element."""
        error_str = str(error).lower()
        stale_indicators = [
            "stale",
            "detached",
            "element not found",
            "not attached to the dom",
            "element is not visible",
        ]
        return any(indicator in error_str for indicator in stale_indicators)
    
    def _is_session_error(self, error: Exception) -> bool:
        """Check if error indicates session issue."""
        error_str = str(error).lower()
        session_indicators = [
            "unauthorized",
            "401",
            "403",
            "session expired",
            "not authenticated",
            "login required",
        ]
        return any(indicator in error_str for indicator in session_indicators)
    
    def _is_browser_error(self, error: Exception) -> bool:
        """Check if error indicates browser issue."""
        error_str = str(error).lower()
        browser_indicators = [
            "target closed",
            "browser has been closed",
            "session closed",
            "page crashed",
            "browser disconnected",
        ]
        return any(indicator in error_str for indicator in browser_indicators)
    
    def _refresh_locator(self, locator: str, element_name: str, page: Any) -> None:
        """Refresh a stale locator."""
        logger.info("Healing: Refreshing locator for %s", element_name)
        try:
            # Force re-evaluation of the locator
            page.locator(locator).count()
            logger.info("Healing: Locator refreshed successfully for %s", element_name)
        except Exception as e:
            logger.warning("Healing: Failed to refresh locator for %s: %s", element_name, str(e))
    
    def _requery_dom(self, url: str, mcp_client: Any) -> Optional[str]:
        """Re-query DOM via MCP."""
        if not self.enable_dom_cache:
            return None
        
        # Check cache first
        if url in self.dom_cache:
            snapshot, timestamp = self.dom_cache[url]
            age_ms = (time.time() - timestamp) * 1000
            if age_ms < self.dom_cache_ttl_ms:
                self.metrics.cache_hits += 1
                logger.info("Healing: DOM cache HIT for %s (age: %.0fms)", url, age_ms)
                return snapshot
            else:
                self.metrics.cache_misses += 1
                logger.info("Healing: DOM cache STALE for %s (age: %.0fms)", url, age_ms)
                del self.dom_cache[url]
        
        # Fetch fresh DOM
        try:
            logger.info("Healing: Re-querying DOM via MCP for %s", url)
            snapshot = mcp_client.inspect_page(url)
            
            # Cache the snapshot
            self.dom_cache[url] = (snapshot, time.time())
            self.metrics.cache_misses += 1
            
            logger.info("Healing: DOM re-query SUCCESS for %s (%d chars)", url, len(snapshot))
            return snapshot
        except Exception as e:
            logger.error("Healing: DOM re-query FAILED for %s: %s", url, str(e))
            return None
    
    def _get_alternate_locators(self, element_name: str, context: Dict[str, Any]) -> List[str]:
        """Get alternate locators for an element."""
        # Check locator cache
        if element_name in self.locator_cache:
            return self.locator_cache[element_name]
        
        # Try to extract from context
        alternates = []
        if "locators" in context:
            for loc in context["locators"]:
                if loc.get("element_name") == element_name:
                    if "alternate_locators" in loc:
                        alternates = loc["alternate_locators"]
                        # Cache for future use
                        self.locator_cache[element_name] = alternates
                        break
        
        if alternates:
            logger.info("Healing: Found %d alternate locators for %s", len(alternates), element_name)
        else:
            logger.info("Healing: No alternate locators found for %s", element_name)
        
        return alternates
    
    def _recover_session(self, page: Any, context: Dict[str, Any]) -> None:
        """Recover from session loss."""
        logger.info("Healing: Attempting session recovery")
        
        try:
            # Navigate to login page
            login_url = context.get("login_url", context.get("application_url", ""))
            if login_url:
                page.goto(login_url)
                
                # Restore session state if available
                if "username" in context and "password" in context:
                    page.locator("input[name='username']").fill(context["username"])
                    page.locator("input[name='password']").fill(context["password"])
                    page.get_by_role("button", name="Login").click()
                
                logger.info("Healing: Session recovery SUCCESS")
            else:
                logger.warning("Healing: Session recovery FAILED - no login URL")
        except Exception as e:
            logger.error("Healing: Session recovery FAILED: %s", str(e))
    
    def _recover_browser(self, page: Any, context: Dict[str, Any]) -> None:
        """Recover from browser issues."""
        logger.info("Healing: Attempting browser recovery")
        
        try:
            # Reload the page
            page.reload()
            
            # Wait for page to be ready
            page.wait_for_load_state("networkidle", timeout=10000)
            
            logger.info("Healing: Browser recovery SUCCESS")
        except Exception as e:
            logger.error("Healing: Browser recovery FAILED: %s", str(e))
    
    def get_metrics(self) -> HealingMetrics:
        """Get current healing metrics."""
        return self.metrics
    
    def get_healing_history(self) -> List[HealingAttempt]:
        """Get healing history."""
        return self.healing_history
    
    def reset_metrics(self) -> None:
        """Reset healing metrics."""
        self.metrics = HealingMetrics()
        self.healing_history = []
        logger.info("Healing metrics reset")
    
    def _save_healing_report(
        self,
        element_name: str,
        attempts: List[HealingAttempt],
        final_locator: str,
        successful: bool
    ) -> None:
        """Save healing report to artifacts.
        
        Args:
            element_name: Name of the element
            attempts: List of healing attempts
            final_locator: Final locator used
            successful: Whether healing was successful
        """
        if not self.artifacts_manager:
            return
        
        try:
            from phoenix.execution.artifacts import HealingReport, HealingAttempt as ArtifactHealingAttempt
            
            # Convert internal healing attempts to artifact format
            artifact_attempts = []
            total_duration = 0.0
            
            for attempt in attempts:
                artifact_attempt = ArtifactHealingAttempt(
                    original_locator=final_locator,
                    failure_reason=attempt.error_message or "",
                    alternative_locator=final_locator,
                    success=attempt.success,
                    strategy=attempt.strategy.value,
                    duration_ms=attempt.duration_ms,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(attempt.timestamp))
                )
                artifact_attempts.append(artifact_attempt)
                total_duration += attempt.duration_ms
            
            healing_report = HealingReport(
                element_name=element_name,
                attempts=artifact_attempts,
                final_locator=final_locator,
                total_attempts=len(attempts),
                successful=successful,
                total_duration_ms=total_duration
            )
            
            self.artifacts_manager.save_healing_report(healing_report)
            logger.info(f"[HEALING] Report saved for {element_name}: {len(attempts)} attempts, success={successful}")
            
        except Exception as e:
            logger.warning(f"Failed to save healing report: {e}")
    
    def _persist_healing_success(
        self,
        element_name: str,
        final_locator: str,
        context: Dict[str, Any]
    ) -> None:
        """Persist successful healing to locator repository.
        
        When healing succeeds, update the locator repository with the
        successful locator so future runs can use it directly.
        
        Args:
            element_name: Name of the element
            final_locator: The locator that succeeded
            context: Execution context with project/page info
        """
        if not self.locator_repository:
            return
        
        try:
            # Extract project and page info from context
            project_name = context.get("project_name", "default")
            page_name = context.get("page_name", "default")
            page_url = context.get("url", "")
            
            # Determine locator type (simple heuristic)
            locator_type = "unknown"
            if "get_by_role" in final_locator:
                locator_type = "get_by_role"
            elif "get_by_text" in final_locator:
                locator_type = "get_by_text"
            elif "get_by_label" in final_locator:
                locator_type = "get_by_label"
            elif "#" in final_locator or "[" in final_locator:
                locator_type = "css"
            
            # Save to repository with high confidence (since it worked)
            self.locator_repository.save_locator(
                project_name=project_name,
                page_name=page_name,
                element_name=element_name,
                locator=final_locator,
                locator_type=locator_type,
                confidence=0.9,  # High confidence since it worked via healing
                source="healing",
                page_url=page_url,
                priority=1,
                metadata={"healed": True, "healing_timestamp": time.time()}
            )
            
            # Record as successful
            self.locator_repository.record_success(project_name, page_name, element_name)
            # Validate the healed locator after successful healing
            self.locator_repository.record_validation(project_name, page_name, element_name, validated=True)
            
            logger.info(
                f"[HEALING] Persisted successful locator to repository: {element_name} -> {final_locator}"
            )
            
        except Exception as e:
            logger.warning(f"Failed to persist healing to locator repository: {e}")