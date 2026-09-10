"""Production Metrics - Comprehensive runtime metrics collection.

Collects and aggregates metrics from all Phoenix subsystems:
- Healing metrics
- Browser pool metrics
- Circuit breaker metrics
- Session recovery metrics
- DOM cache metrics
- Execution time metrics
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProductionMetrics:
    """Aggregate production metrics from all subsystems."""
    
    # Healing metrics
    healing_total_attempts: int = 0
    healing_successful: int = 0
    healing_failed: int = 0
    healing_cache_hits: int = 0
    healing_cache_misses: int = 0
    healing_total_time_ms: float = 0.0
    
    # Browser pool metrics
    browser_total_created: int = 0
    browser_total_closed: int = 0
    browser_active: int = 0
    browser_reuse_count: int = 0
    context_total_created: int = 0
    context_active: int = 0
    context_reuse_count: int = 0
    page_total_created: int = 0
    page_active: int = 0
    page_reuse_count: int = 0
    
    # Circuit breaker metrics
    circuit_state: str = "closed"
    circuit_failures: int = 0
    circuit_successes: int = 0
    circuit_total_events: int = 0
    
    # Session recovery metrics
    session_recovery_attempts: int = 0
    session_successful: int = 0
    session_failed: int = 0
    session_saved: int = 0
    session_restored: int = 0
    session_recovery_time_ms: float = 0.0
    
    # DOM cache metrics
    dom_cache_hits: int = 0
    dom_cache_misses: int = 0
    dom_cache_entries: int = 0
    dom_cache_evictions: int = 0
    dom_cache_hit_ratio: float = 0.0
    
    # Execution metrics
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    total_execution_time_ms: float = 0.0
    average_test_time_ms: float = 0.0
    
    # MCP metrics
    mcp_call_count: int = 0
    mcp_success_count: int = 0
    mcp_failure_count: int = 0
    mcp_total_time_ms: float = 0.0
    mcp_average_time_ms: float = 0.0
    
    # LLM metrics
    llm_call_count: int = 0
    llm_total_time_ms: float = 0.0
    llm_average_time_ms: float = 0.0
    
    # Timestamp
    collected_at: float = field(default_factory=time.time)


class MetricsCollector:
    """Collects and aggregates metrics from all Phoenix subsystems."""
    
    def __init__(self):
        self.metrics = ProductionMetrics()
        self.start_time = time.time()
        
        logger.info("Metrics Collector initialized")
    
    def update_healing_metrics(
        self,
        total_attempts: int,
        successful: int,
        failed: int,
        cache_hits: int,
        cache_misses: int,
        total_time_ms: float,
    ) -> None:
        """Update healing metrics."""
        self.metrics.healing_total_attempts = total_attempts
        self.metrics.healing_successful = successful
        self.metrics.healing_failed = failed
        self.metrics.healing_cache_hits = cache_hits
        self.metrics.healing_cache_misses = cache_misses
        self.metrics.healing_total_time_ms = total_time_ms
        
        logger.debug(
            "Healing metrics updated: attempts=%d, successful=%d, failed=%d, "
            "cache_hits=%d, cache_misses=%d, time=%.0fms",
            total_attempts, successful, failed, cache_hits, cache_misses, total_time_ms
        )
    
    def update_browser_pool_metrics(
        self,
        total_created: int,
        total_closed: int,
        active: int,
        reuse_count: int,
        context_created: int,
        context_active: int,
        context_reuse: int,
        page_created: int,
        page_active: int,
        page_reuse: int,
    ) -> None:
        """Update browser pool metrics."""
        self.metrics.browser_total_created = total_created
        self.metrics.browser_total_closed = total_closed
        self.metrics.browser_active = active
        self.metrics.browser_reuse_count = reuse_count
        self.metrics.context_total_created = context_created
        self.metrics.context_active = context_active
        self.metrics.context_reuse_count = context_reuse
        self.metrics.page_total_created = page_created
        self.metrics.page_active = page_active
        self.metrics.page_reuse_count = page_reuse
        
        logger.debug(
            "Browser pool metrics updated: browsers=%d/%d, contexts=%d/%d, pages=%d/%d, "
            "browser_reuse=%d, context_reuse=%d, page_reuse=%d",
            active, total_created, context_active, context_created, page_active, page_created,
            reuse_count, context_reuse, page_reuse
        )
    
    def update_circuit_breaker_metrics(
        self,
        state: str,
        failures: int,
        successes: int,
        total_events: int,
    ) -> None:
        """Update circuit breaker metrics."""
        self.metrics.circuit_state = state
        self.metrics.circuit_failures = failures
        self.metrics.circuit_successes = successes
        self.metrics.circuit_total_events = total_events
        
        logger.debug(
            "Circuit breaker metrics updated: state=%s, failures=%d, successes=%d, events=%d",
            state, failures, successes, total_events
        )
    
    def update_session_recovery_metrics(
        self,
        attempts: int,
        successful: int,
        failed: int,
        saved: int,
        restored: int,
        recovery_time_ms: float,
    ) -> None:
        """Update session recovery metrics."""
        self.metrics.session_recovery_attempts = attempts
        self.metrics.session_successful = successful
        self.metrics.session_failed = failed
        self.metrics.session_saved = saved
        self.metrics.session_restored = restored
        self.metrics.session_recovery_time_ms = recovery_time_ms
        
        logger.debug(
            "Session recovery metrics updated: attempts=%d, successful=%d, failed=%d, "
            "saved=%d, restored=%d, time=%.0fms",
            attempts, successful, failed, saved, restored, recovery_time_ms
        )
    
    def update_dom_cache_metrics(
        self,
        hits: int,
        misses: int,
        entries: int,
        evictions: int,
        hit_ratio: float,
    ) -> None:
        """Update DOM cache metrics."""
        self.metrics.dom_cache_hits = hits
        self.metrics.dom_cache_misses = misses
        self.metrics.dom_cache_entries = entries
        self.metrics.dom_cache_evictions = evictions
        self.metrics.dom_cache_hit_ratio = hit_ratio
        
        logger.debug(
            "DOM cache metrics updated: hits=%d, misses=%d, entries=%d, evictions=%d, hit_ratio=%.2f",
            hits, misses, entries, evictions, hit_ratio
        )
    
    def update_execution_metrics(
        self,
        total_tests: int,
        passed: int,
        failed: int,
        skipped: int,
        execution_time_ms: float,
    ) -> None:
        """Update execution metrics."""
        self.metrics.total_tests = total_tests
        self.metrics.passed_tests = passed
        self.metrics.failed_tests = failed
        self.metrics.skipped_tests = skipped
        self.metrics.total_execution_time_ms = execution_time_ms
        
        if total_tests > 0:
            self.metrics.average_test_time_ms = execution_time_ms / total_tests
        
        logger.debug(
            "Execution metrics updated: total=%d, passed=%d, failed=%d, skipped=%d, time=%.0fms, avg=%.0fms",
            total_tests, passed, failed, skipped, execution_time_ms, self.metrics.average_test_time_ms
        )
    
    def update_mcp_metrics(
        self,
        call_count: int,
        success_count: int,
        failure_count: int,
        total_time_ms: float,
    ) -> None:
        """Update MCP metrics."""
        self.metrics.mcp_call_count = call_count
        self.metrics.mcp_success_count = success_count
        self.metrics.mcp_failure_count = failure_count
        self.metrics.mcp_total_time_ms = total_time_ms
        
        if call_count > 0:
            self.metrics.mcp_average_time_ms = total_time_ms / call_count
        
        logger.debug(
            "MCP metrics updated: calls=%d, success=%d, failure=%d, time=%.0fms, avg=%.0fms",
            call_count, success_count, failure_count, total_time_ms, self.metrics.mcp_average_time_ms
        )
    
    def update_llm_metrics(
        self,
        call_count: int,
        total_time_ms: float,
    ) -> None:
        """Update LLM metrics."""
        self.metrics.llm_call_count = call_count
        self.metrics.llm_total_time_ms = total_time_ms
        
        if call_count > 0:
            self.metrics.llm_average_time_ms = total_time_ms / call_count
        
        logger.debug(
            "LLM metrics updated: calls=%d, time=%.0fms, avg=%.0fms",
            call_count, total_time_ms, self.metrics.llm_average_time_ms
        )
    
    def get_metrics(self) -> ProductionMetrics:
        """Get current aggregate metrics."""
        self.metrics.collected_at = time.time()
        return self.metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of key metrics."""
        metrics = self.get_metrics()
        
        return {
            "healing_success_rate": (
                metrics.healing_successful / metrics.healing_total_attempts * 100
                if metrics.healing_total_attempts > 0 else 0
            ),
            "browser_reuse_rate": (
                metrics.browser_reuse_count / metrics.browser_total_created * 100
                if metrics.browser_total_created > 0 else 0
            ),
            "test_pass_rate": (
                metrics.passed_tests / metrics.total_tests * 100
                if metrics.total_tests > 0 else 0
            ),
            "dom_cache_hit_ratio": metrics.dom_cache_hit_ratio,
            "mcp_success_rate": (
                metrics.mcp_success_count / metrics.mcp_call_count * 100
                if metrics.mcp_call_count > 0 else 0
            ),
            "circuit_state": metrics.circuit_state,
            "total_execution_time_s": metrics.total_execution_time_ms / 1000,
            "average_test_time_s": metrics.average_test_time_ms / 1000,
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics = ProductionMetrics()
        self.start_time = time.time()
        logger.info("Metrics reset")