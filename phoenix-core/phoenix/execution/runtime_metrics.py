"""Real Runtime Metrics - Comprehensive performance tracking.

This module implements runtime metrics collection that:
- Tracks execution time for all phases
- Measures DOM capture and cache performance
- Records locator validation timing
- Tracks healing duration and success
- Provides verifiable performance evidence
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Metrics Models
# ---------------------------------------------------------------------------

class PhaseMetrics(BaseModel):
    """Metrics for a single execution phase."""
    phase_name: str = ""
    duration_ms: float = 0.0
    start_time: str = ""
    end_time: str = ""
    success: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeMetrics(BaseModel):
    """Complete runtime metrics for a test execution."""
    run_id: str = ""
    test_name: str = ""
    total_execution_time_ms: float = 0.0
    start_time: str = ""
    end_time: str = ""
    
    # Phase timings
    dom_capture_time_ms: float = 0.0
    dom_cache_time_ms: float = 0.0
    locator_generation_time_ms: float = 0.0
    locator_validation_time_ms: float = 0.0
    healing_time_ms: float = 0.0
    mcp_time_ms: float = 0.0
    
    # DOM metrics
    dom_size_bytes: int = 0
    dom_node_count: int = 0
    dom_hash: str = ""
    
    # Locator metrics
    locator_count: int = 0
    locator_cache_hits: int = 0
    locator_cache_misses: int = 0
    
    # Cache metrics
    dom_cache_hits: int = 0
    dom_cache_misses: int = 0
    cache_hit_ratio: float = 0.0
    
    # Healing metrics
    healing_attempts: int = 0
    healing_successes: int = 0
    healing_failures: int = 0
    
    # Phase details
    phases: List[PhaseMetrics] = Field(default_factory=list)
    
    # Overall status
    status: str = "passed"  # passed, failed, error
    error_message: str = ""
    
    # Time savings
    total_time_saved_ms: float = 0.0
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Runtime Metrics Collector
# ---------------------------------------------------------------------------

class RuntimeMetricsCollector:
    """Collects and aggregates runtime metrics.
    
    Features:
    - Phase-based timing
    - Automatic metric aggregation
    - Artifact integration
    - Real-time tracking
    """
    
    def __init__(self, artifacts_manager=None):
        self.artifacts_manager = artifacts_manager
        self.metrics: Optional[RuntimeMetrics] = None
        self._phase_stack: List[str] = []
        self._phase_start_times: Dict[str, float] = {}
    
    def start_collection(
        self,
        run_id: str,
        test_name: str = ""
    ) -> None:
        """Start metrics collection for a test run.
        
        Args:
            run_id: Run identifier
            test_name: Test name
        """
        self.metrics = RuntimeMetrics(
            run_id=run_id,
            test_name=test_name,
            start_time=datetime.now(timezone.utc).isoformat()
        )
    
    def end_collection(self, status: str = "passed", error_message: str = "") -> None:
        """End metrics collection and finalize.
        
        Args:
            status: Final status (passed, failed, error)
            error_message: Error message if failed
        """
        if not self.metrics:
            return
        
        self.metrics.end_time = datetime.now(timezone.utc).isoformat()
        self.metrics.status = status
        self.metrics.error_message = error_message
        
        # Calculate total execution time
        if self.metrics.start_time:
            start = datetime.fromisoformat(self.metrics.start_time)
            end = datetime.fromisoformat(self.metrics.end_time)
            self.metrics.total_execution_time_ms = (end - start).total_seconds() * 1000
        
        # Calculate cache hit ratio
        total_cache_ops = self.metrics.dom_cache_hits + self.metrics.dom_cache_misses
        if total_cache_ops > 0:
            self.metrics.cache_hit_ratio = self.metrics.dom_cache_hits / total_cache_ops
        
        # Save metrics if artifacts manager available
        if self.artifacts_manager:
            self._save_metrics()
    
    def start_phase(self, phase_name: str) -> None:
        """Start timing a phase.
        
        Args:
            phase_name: Name of the phase
        """
        if not self.metrics:
            return
        
        self._phase_stack.append(phase_name)
        self._phase_start_times[phase_name] = time.time()
    
    def end_phase(
        self,
        phase_name: str,
        success: bool = True,
        error_message: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """End timing a phase.
        
        Args:
            phase_name: Name of the phase
            success: Whether phase succeeded
            error_message: Error message if failed
            metadata: Additional phase metadata
        """
        if not self.metrics:
            return
        
        start_time = self._phase_start_times.get(phase_name)
        if start_time is None:
            return
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Create phase metrics
        phase = PhaseMetrics(
            phase_name=phase_name,
            duration_ms=duration_ms,
            start_time=datetime.fromtimestamp(start_time, timezone.utc).isoformat(),
            end_time=datetime.now(timezone.utc).isoformat(),
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )
        
        self.metrics.phases.append(phase)
        
        # Update specific phase metrics
        self._update_phase_metric(phase_name, duration_ms)
        
        # Clean up
        if phase_name in self._phase_stack:
            self._phase_stack.remove(phase_name)
        if phase_name in self._phase_start_times:
            del self._phase_start_times[phase_name]
    
    def record_dom_capture(
        self,
        size_bytes: int,
        node_count: int,
        dom_hash: str,
        duration_ms: float
    ) -> None:
        """Record DOM capture metrics.
        
        Args:
            size_bytes: DOM size in bytes
            node_count: Number of DOM nodes
            dom_hash: DOM hash
            duration_ms: Capture duration
        """
        if not self.metrics:
            return
        
        self.metrics.dom_size_bytes = size_bytes
        self.metrics.dom_node_count = node_count
        self.metrics.dom_hash = dom_hash
        self.metrics.dom_capture_time_ms = duration_ms
    
    def record_mcp_call(self, duration_ms: float, success: bool = True) -> None:
        """Record MCP call metrics.
        
        Args:
            duration_ms: MCP call duration
            success: Whether MCP call succeeded
        """
        if not self.metrics:
            return
        
        self.metrics.mcp_time_ms += duration_ms
    
    def record_cache_operation(self, hit: bool, duration_ms: float) -> None:
        """Record cache operation.
        
        Args:
            hit: Whether cache hit
            duration_ms: Cache operation duration
        """
        if not self.metrics:
            return
        
        if hit:
            self.metrics.dom_cache_hits += 1
        else:
            self.metrics.dom_cache_misses += 1
        
        self.metrics.dom_cache_time_ms += duration_ms
    
    def record_locator_operation(
        self,
        count: int,
        cache_hit: bool,
        duration_ms: float
    ) -> None:
        """Record locator operation.
        
        Args:
            count: Number of locators
            cache_hit: Whether locator cache hit
            duration_ms: Operation duration
        """
        if not self.metrics:
            return
        
        self.metrics.locator_count += count
        
        if cache_hit:
            self.metrics.locator_cache_hits += 1
        else:
            self.metrics.locator_cache_misses += 1
    
    def record_healing_attempt(
        self,
        success: bool,
        duration_ms: float
    ) -> None:
        """Record healing attempt.
        
        Args:
            success: Whether healing succeeded
            duration_ms: Healing duration
        """
        if not self.metrics:
            return
        
        self.metrics.healing_attempts += 1
        self.metrics.healing_time_ms += duration_ms
        
        if success:
            self.metrics.healing_successes += 1
        else:
            self.metrics.healing_failures += 1
    
    def record_time_saved(self, time_saved_ms: float) -> None:
        """Record time saved from cache/locator reuse.
        
        Args:
            time_saved_ms: Time saved in milliseconds
        """
        if not self.metrics:
            return
        
        self.metrics.total_time_saved_ms += time_saved_ms
    
    def _update_phase_metric(self, phase_name: str, duration_ms: float) -> None:
        """Update specific phase metric.
        
        Args:
            phase_name: Phase name
            duration_ms: Phase duration
        """
        phase_lower = phase_name.lower()
        
        if "dom" in phase_lower and "capture" in phase_lower:
            self.metrics.dom_capture_time_ms = duration_ms
        elif "dom" in phase_lower and "cache" in phase_lower:
            self.metrics.dom_cache_time_ms = duration_ms
        elif "locator" in phase_lower and "generation" in phase_lower:
            self.metrics.locator_generation_time_ms = duration_ms
        elif "locator" in phase_lower and "validation" in phase_lower:
            self.metrics.locator_validation_time_ms = duration_ms
        elif "healing" in phase_lower:
            self.metrics.healing_time_ms = duration_ms
        elif "mcp" in phase_lower:
            self.metrics.mcp_time_ms = duration_ms
    
    def _save_metrics(self) -> None:
        """Save metrics to artifacts."""
        if not self.artifacts_manager or not self.metrics:
            return
        
        try:
            run_dir = self.artifacts_manager.get_run_directory()
            if run_dir:
                metrics_path = run_dir / "metrics.json"
                metrics_path.write_text(self.metrics.model_dump_json(indent=2), encoding='utf-8')
        except Exception as e:
            pass  # Don't fail if artifact saving fails
    
    def get_metrics(self) -> Optional[RuntimeMetrics]:
        """Get current metrics.
        
        Returns:
            Current metrics or None
        """
        return self.metrics