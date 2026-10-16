"""Risk Intelligence Models - Priority 31.

This module defines the data models for the universal risk intelligence system that
provides evidence-driven governance for autonomous testing.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class BusinessCriticality(Enum):
    """Business criticality levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestPriority(Enum):
    """Test priority levels."""
    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low


class ExecutionPolicy(Enum):
    """Autonomous execution policies."""
    AUTONOMOUS_EXECUTE = "autonomous_execute"
    AUTONOMOUS_RETRY = "autonomous_retry"
    AUTONOMOUS_HEAL = "autonomous_heal"
    AUTONOMOUS_REGENERATE = "autonomous_regenerate"
    MONITOR_ONLY = "monitor_only"
    QUARANTINE = "quarantine"
    HUMAN_REVIEW = "human_review"
    BLOCK_EXECUTION = "block_execution"


class ReadinessStatus(Enum):
    """Release/execution readiness status."""
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    RISK_ACCEPTED = "risk_accepted"
    BLOCKED = "blocked"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class FlakyClassification(Enum):
    """Flaky test classification."""
    STABLE = "stable"
    POSSIBLY_FLAKY = "possibly_flaky"
    FLAKY = "flaky"
    HIGHLY_FLAKY = "highly_flaky"


class CoverageGapLevel(Enum):
    """Coverage gap levels."""
    CRITICAL_COVERAGE_GAP = "critical_coverage_gap"
    HIGH_COVERAGE_GAP = "high_coverage_gap"
    MEDIUM_COVERAGE_GAP = "medium_coverage_gap"
    LOW_COVERAGE_GAP = "low_coverage_gap"


@dataclass
class RiskDimension:
    """A single dimension of risk assessment."""
    dimension_name: str
    score: float  # 0.0 to 1.0
    weight: float  # 0.0 to 1.0
    evidence: List[str]
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dimension_name": self.dimension_name,
            "score": self.score,
            "weight": self.weight,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class RiskAssessment:
    """Complete risk assessment for a test or component."""
    assessment_id: str
    target_id: str  # test_id, component_id, or flow_id
    target_type: str  # "test", "component", "flow"
    overall_risk_score: float  # 0.0 to 100.0
    risk_level: str  # "critical", "high", "medium", "low"
    dimensions: List[RiskDimension]
    business_criticality: BusinessCriticality
    test_priority: TestPriority
    execution_policy: ExecutionPolicy
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "overall_risk_score": self.overall_risk_score,
            "risk_level": self.risk_level,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "business_criticality": self.business_criticality.value,
            "test_priority": self.test_priority.value,
            "execution_policy": self.execution_policy.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class QuarantineRecord:
    """Record of a quarantined test."""
    quarantine_id: str
    test_id: str
    reason: str
    evidence: List[str]
    failure_history: List[Dict[str, Any]]
    last_successful_execution: Optional[datetime]
    confidence: float
    affected_flow: Optional[str]
    recommended_action: str
    quarantine_date: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "quarantine_id": self.quarantine_id,
            "test_id": self.test_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "failure_history": self.failure_history,
            "last_successful_execution": self.last_successful_execution.isoformat() if self.last_successful_execution else None,
            "confidence": self.confidence,
            "affected_flow": self.affected_flow,
            "recommended_action": self.recommended_action,
            "quarantine_date": self.quarantine_date.isoformat(),
        }


@dataclass
class FlakyTestAssessment:
    """Assessment of test flakiness."""
    assessment_id: str
    test_id: str
    classification: FlakyClassification
    pass_fail_oscillation: float
    timing_variation: float
    locator_instability: float
    navigation_instability: float
    intermittent_assertions: float
    retry_dependency: float
    healing_dependency: float
    environment_dependency: float
    overall_flakiness_score: float
    evidence: List[str]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "test_id": self.test_id,
            "classification": self.classification.value,
            "pass_fail_oscillation": self.pass_fail_oscillation,
            "timing_variation": self.timing_variation,
            "locator_instability": self.locator_instability,
            "navigation_instability": self.navigation_instability,
            "intermittent_assertions": self.intermittent_assertions,
            "retry_dependency": self.retry_dependency,
            "healing_dependency": self.healing_dependency,
            "environment_dependency": self.environment_dependency,
            "overall_flakiness_score": self.overall_flakiness_score,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CoverageGap:
    """Coverage gap assessment."""
    gap_id: str
    gap_type: str  # "page", "component", "flow", "action", "validation", etc.
    target_id: str
    target_name: str
    gap_level: CoverageGapLevel
    business_importance: BusinessCriticality
    missing_tests: List[str]
    recommended_actions: List[str]
    risk_impact: float
    evidence: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "gap_level": self.gap_level.value,
            "business_importance": self.business_importance.value,
            "missing_tests": self.missing_tests,
            "recommended_actions": self.recommended_actions,
            "risk_impact": self.risk_impact,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReadinessAssessment:
    """Release/execution readiness assessment."""
    assessment_id: str
    scope: str  # "application", "flow", "test_suite"
    scope_id: str
    status: ReadinessStatus
    critical_tests_status: str
    high_risk_changes: int
    regression_failures: int
    unresolved_maintenance: int
    flaky_tests: int
    coverage_gaps: int
    security_concerns: int
    execution_confidence: float
    overall_readiness_score: float
    blockers: List[str]
    warnings: List[str]
    recommendations: List[str]
    evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "scope": self.scope,
            "scope_id": self.scope_id,
            "status": self.status.value,
            "critical_tests_status": self.critical_tests_status,
            "high_risk_changes": self.high_risk_changes,
            "regression_failures": self.regression_failures,
            "unresolved_maintenance": self.unresolved_maintenance,
            "flaky_tests": self.flaky_tests,
            "coverage_gaps": self.coverage_gaps,
            "security_concerns": self.security_concerns,
            "execution_confidence": self.execution_confidence,
            "overall_readiness_score": self.overall_readiness_score,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HumanReviewTrigger:
    """Trigger for human review."""
    trigger_id: str
    test_id: Optional[str]
    component_id: Optional[str]
    flow_id: Optional[str]
    reason: str
    evidence: List[str]
    confidence: float
    affected_tests: List[str]
    affected_flows: List[str]
    recommended_human_action: str
    urgency: str  # "critical", "high", "medium", "low"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trigger_id": self.trigger_id,
            "test_id": self.test_id,
            "component_id": self.component_id,
            "flow_id": self.flow_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "affected_tests": self.affected_tests,
            "affected_flows": self.affected_flows,
            "recommended_human_action": self.recommended_human_action,
            "urgency": self.urgency,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RiskDashboardData:
    """Structured data for enterprise risk dashboard."""
    dashboard_id: str
    timestamp: datetime
    overall_application_risk: float
    critical_tests: List[Dict[str, Any]]
    high_risk_tests: List[Dict[str, Any]]
    high_risk_changes: List[Dict[str, Any]]
    coverage_gaps: List[Dict[str, Any]]
    flaky_tests: List[Dict[str, Any]]
    quarantined_tests: List[Dict[str, Any]]
    maintenance_failures: List[Dict[str, Any]]
    regression_failures: List[Dict[str, Any]]
    human_reviews: List[Dict[str, Any]]
    release_readiness: Dict[str, Any]
    autonomous_decisions: List[Dict[str, Any]]
    risk_distribution: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dashboard_id": self.dashboard_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_application_risk": self.overall_application_risk,
            "critical_tests": self.critical_tests,
            "high_risk_tests": self.high_risk_tests,
            "high_risk_changes": self.high_risk_changes,
            "coverage_gaps": self.coverage_gaps,
            "flaky_tests": self.flaky_tests,
            "quarantined_tests": self.quarantined_tests,
            "maintenance_failures": self.maintenance_failures,
            "regression_failures": self.regression_failures,
            "human_reviews": self.human_reviews,
            "release_readiness": self.release_readiness,
            "autonomous_decisions": self.autonomous_decisions,
            "risk_distribution": self.risk_distribution,
        }
