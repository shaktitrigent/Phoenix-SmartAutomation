"""Real Metrics Collection - Priority 31.

This module implements real-time metrics collection for the risk intelligence system,
tracking governance effectiveness, risk trends, and system performance.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMING = "timing"


class MetricCategory(Enum):
    """Categories of metrics."""
    RISK_ASSESSMENT = "risk_assessment"
    QUARANTINE = "quarantine"
    FLAKY_TESTS = "flaky_tests"
    COVERAGE = "coverage"
    SECURITY = "security"
    HUMAN_REVIEW = "human_review"
    RELEASE_READINESS = "release_readiness"
    SYSTEM_PERFORMANCE = "system_performance"
    GOVERNANCE_EFFECTIVENESS = "governance_effectiveness"


@dataclass
class Metric:
    """A single metric data point."""
    metric_id: str
    name: str
    metric_type: MetricType
    category: MetricCategory
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "metric_type": self.metric_type.value,
            "category": self.category.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class MetricSnapshot:
    """A snapshot of metrics at a point in time."""
    snapshot_id: str
    timestamp: datetime
    metrics: List[Metric]
    summary: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics],
            "summary": self.summary,
        }


class RealMetricsCollector:
    """Real-time metrics collector for risk intelligence.
    
    This collector:
    - Tracks risk assessment metrics
    - Monitors quarantine effectiveness
    - Measures flaky test detection
    - Tracks coverage improvement
    - Monitors security compliance
    - Measures human review efficiency
    - Tracks release readiness trends
    - Monitors system performance
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timings: Dict[str, List[float]] = defaultdict(list)
        
        # Performance tracking
        self.start_times: Dict[str, float] = {}
        
        logger.info("[METRICS COLLECTOR] Real-time metrics collector initialized")
    
    def increment_counter(
        self,
        name: str,
        category: MetricCategory,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> Metric:
        """Increment a counter metric.
        
        Args:
            name: Metric name
            category: Metric category
            value: Value to increment by
            labels: Optional labels
            
        Returns:
            Metric
        """
        metric_key = f"{category.value}:{name}"
        self.counters[metric_key] += value
        
        metric = Metric(
            metric_id=str(uuid4()),
            name=name,
            metric_type=MetricType.COUNTER,
            category=category,
            value=self.counters[metric_key],
            labels=labels or {},
        )
        
        self.metrics[metric_key].append(metric)
        return metric
    
    def set_gauge(
        self,
        name: str,
        category: MetricCategory,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> Metric:
        """Set a gauge metric.
        
        Args:
            name: Metric name
            category: Metric category
            value: Value to set
            labels: Optional labels
            
        Returns:
            Metric
        """
        metric_key = f"{category.value}:{name}"
        self.gauges[metric_key] = value
        
        metric = Metric(
            metric_id=str(uuid4()),
            name=name,
            metric_type=MetricType.GAUGE,
            category=category,
            value=value,
            labels=labels or {},
        )
        
        self.metrics[metric_key].append(metric)
        return metric
    
    def record_histogram(
        self,
        name: str,
        category: MetricCategory,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> Metric:
        """Record a histogram metric.
        
        Args:
            name: Metric name
            category: Metric category
            value: Value to record
            labels: Optional labels
            
        Returns:
            Metric
        """
        metric_key = f"{category.value}:{name}"
        self.histograms[metric_key].append(value)
        
        metric = Metric(
            metric_id=str(uuid4()),
            name=name,
            metric_type=MetricType.HISTOGRAM,
            category=category,
            value=value,
            labels=labels or {},
        )
        
        self.metrics[metric_key].append(metric)
        return metric
    
    def record_timing(
        self,
        name: str,
        category: MetricCategory,
        duration: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> Metric:
        """Record a timing metric.
        
        Args:
            name: Metric name
            category: Metric category
            duration: Duration in seconds
            labels: Optional labels
            
        Returns:
            Metric
        """
        metric_key = f"{category.value}:{name}"
        self.timings[metric_key].append(duration)
        
        metric = Metric(
            metric_id=str(uuid4()),
            name=name,
            metric_type=MetricType.TIMING,
            category=category,
            value=duration,
            labels=labels or {},
        )
        
        self.metrics[metric_key].append(metric)
        return metric
    
    def start_timing(self, operation: str) -> str:
        """Start timing an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Timing ID
        """
        timing_id = str(uuid4())
        self.start_times[timing_id] = time.time()
        return timing_id
    
    def end_timing(
        self,
        timing_id: str,
        name: str,
        category: MetricCategory,
        labels: Optional[Dict[str, str]] = None,
    ) -> Optional[Metric]:
        """End timing an operation and record metric.
        
        Args:
            timing_id: Timing ID from start_timing
            name: Metric name
            category: Metric category
            labels: Optional labels
            
        Returns:
            Metric if timing ID found, None otherwise
        """
        if timing_id not in self.start_times:
            return None
        
        duration = time.time() - self.start_times[timing_id]
        del self.start_times[timing_id]
        
        return self.record_timing(name, category, duration, labels)
    
    def take_snapshot(self) -> MetricSnapshot:
        """Take a snapshot of current metrics.
        
        Returns:
            Metric snapshot
        """
        all_metrics = []
        for metric_list in self.metrics.values():
            all_metrics.extend(metric_list)
        
        # Generate summary
        summary = self._generate_summary()
        
        snapshot = MetricSnapshot(
            snapshot_id=str(uuid4()),
            timestamp=datetime.now(),
            metrics=all_metrics,
            summary=summary,
        )
        
        return snapshot
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate metrics summary.
        
        Returns:
            Summary dictionary
        """
        summary = {
            "total_metrics": sum(len(m) for m in self.metrics.values()),
            "counters": len(self.counters),
            "gauges": len(self.gauges),
            "histograms": len(self.histograms),
            "timings": len(self.timings),
        }
        
        # Add category breakdown
        category_counts = defaultdict(int)
        for metric_list in self.metrics.values():
            for metric in metric_list:
                category_counts[metric.category.value] += 1
        
        summary["by_category"] = dict(category_counts)
        
        return summary
    
    def get_metrics_by_category(self, category: MetricCategory) -> List[Metric]:
        """Get metrics by category.
        
        Args:
            category: Metric category
            
        Returns:
            List of metrics
        """
        category_metrics = []
        for metric_list in self.metrics.values():
            for metric in metric_list:
                if metric.category == category:
                    category_metrics.append(metric)
        
        return category_metrics
    
    def get_histogram_stats(self, name: str, category: MetricCategory) -> Dict[str, float]:
        """Get histogram statistics.
        
        Args:
            name: Metric name
            category: Metric category
            
        Returns:
            Statistics dictionary
        """
        metric_key = f"{category.value}:{name}"
        values = self.histograms.get(metric_key, [])
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / n,
            "median": sorted_values[n // 2],
            "p50": sorted_values[int(n * 0.5)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)],
        }
    
    def get_timing_stats(self, name: str, category: MetricCategory) -> Dict[str, float]:
        """Get timing statistics.
        
        Args:
            name: Metric name
            category: Metric category
            
        Returns:
            Statistics dictionary
        """
        metric_key = f"{category.value}:{name}"
        values = self.timings.get(metric_key, [])
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / n,
            "median": sorted_values[n // 2],
            "p50": sorted_values[int(n * 0.5)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)],
            "total": sum(sorted_values),
        }
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics.clear()
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.timings.clear()
        self.start_times.clear()
        
        logger.info("[METRICS COLLECTOR] All metrics reset")
    
    def get_status(self) -> Dict[str, Any]:
        """Get collector status.
        
        Returns:
            Status dictionary
        """
        return {
            "total_metrics": sum(len(m) for m in self.metrics.values()),
            "active_timings": len(self.start_times),
            "categories": len(set(m.category for m_list in self.metrics.values() for m in m_list)),
        }
