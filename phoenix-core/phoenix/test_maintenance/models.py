"""Test Maintenance Models - Priority 30.

This module defines the data models for the universal test maintenance system that
closes the loop between change detection, impact analysis, selective regeneration,
validation, and baseline updates.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MaintenanceDecisionType(Enum):
    """Types of maintenance decisions."""
    NO_ACTION = "no_action"
    MONITOR = "monitor"
    UPDATE_LOCATOR = "update_locator"
    UPDATE_POM = "update_pom"
    UPDATE_TEST_STEP = "update_test_step"
    REGENERATE_ASSERTION = "regenerate_assertion"
    REGENERATE_TEST_SECTION = "regenerate_test_section"
    REGENERATE_TEST = "regenerate_test"
    FULL_REGENERATION = "full_regeneration"
    HUMAN_REVIEW = "human_review"


class ValidationStatus(Enum):
    """Status of maintenance validation."""
    PENDING = "pending"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class MaintenanceOutcome(Enum):
    """Outcome of maintenance operation."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    SKIPPED = "skipped"


@dataclass
class TestImpact:
    """Impact of a change on a specific test."""
    impact_id: str
    test_id: str
    change_id: str
    affected_steps: List[str]
    affected_locators: List[str]
    affected_assertions: List[str]
    severity: str
    confidence: float
    requires_regeneration: bool
    regeneration_scope: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "impact_id": self.impact_id,
            "test_id": self.test_id,
            "change_id": self.change_id,
            "affected_steps": self.affected_steps,
            "affected_locators": self.affected_locators,
            "affected_assertions": self.affected_assertions,
            "severity": self.severity,
            "confidence": self.confidence,
            "requires_regeneration": self.requires_regeneration,
            "regeneration_scope": self.regeneration_scope,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MaintenancePlan:
    """Plan for maintaining affected tests."""
    plan_id: str
    session_id: str
    impacted_tests: List[TestImpact]
    maintenance_decisions: List[Dict[str, Any]]
    execution_order: List[str]
    estimated_duration: int
    risk_assessment: Dict[str, Any]
    human_review_triggers: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "impacted_tests": [t.to_dict() for t in self.impacted_tests],
            "maintenance_decisions": self.maintenance_decisions,
            "execution_order": self.execution_order,
            "estimated_duration": self.estimated_duration,
            "risk_assessment": self.risk_assessment,
            "human_review_triggers": self.human_review_triggers,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RegenerationResult:
    """Result of selective regeneration."""
    regeneration_id: str
    test_id: str
    decision_type: MaintenanceDecisionType
    regenerated_steps: List[str]
    preserved_steps: List[str]
    new_locators: Dict[str, str]
    preserved_locators: Dict[str, str]
    new_assertions: List[str]
    preserved_assertions: List[str]
    success: bool
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regeneration_id": self.regeneration_id,
            "test_id": self.test_id,
            "decision_type": self.decision_type.value,
            "regenerated_steps": self.regenerated_steps,
            "preserved_steps": self.preserved_steps,
            "new_locators": self.new_locators,
            "preserved_locators": self.preserved_locators,
            "new_assertions": self.new_assertions,
            "preserved_assertions": self.preserved_assertions,
            "success": self.success,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of maintenance validation."""
    validation_id: str
    regeneration_id: str
    test_id: str
    status: ValidationStatus
    quality_score: float
    locator_validation: Dict[str, Any]
    assertion_validation: Dict[str, Any]
    pom_validation: Dict[str, Any]
    security_validation: Dict[str, Any]
    issues: List[Dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "regeneration_id": self.regeneration_id,
            "test_id": self.test_id,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "locator_validation": self.locator_validation,
            "assertion_validation": self.assertion_validation,
            "pom_validation": self.pom_validation,
            "security_validation": self.security_validation,
            "issues": self.issues,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ContinuousValidationResult:
    """Result of continuous validation with real browser execution."""
    execution_id: str
    test_id: str
    execution_result: Dict[str, Any]
    step_results: List[Dict[str, Any]]
    locator_results: Dict[str, Any]
    assertion_results: Dict[str, Any]
    healing_results: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    failure_classification: Optional[str]
    outcome: MaintenanceOutcome
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "test_id": self.test_id,
            "execution_result": self.execution_result,
            "step_results": self.step_results,
            "locator_results": self.locator_results,
            "assertion_results": self.assertion_results,
            "healing_results": self.healing_results,
            "performance_metrics": self.performance_metrics,
            "failure_classification": self.failure_classification,
            "outcome": self.outcome.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BaselineUpdate:
    """Baseline update result."""
    update_id: str
    previous_baseline_id: str
    new_baseline_id: str
    update_type: str
    tests_updated: List[str]
    tests_preserved: List[str]
    changes_recorded: List[str]
    validation_results: List[str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "update_id": self.update_id,
            "previous_baseline_id": self.previous_baseline_id,
            "new_baseline_id": self.new_baseline_id,
            "update_type": self.update_type,
            "tests_updated": self.tests_updated,
            "tests_preserved": self.tests_preserved,
            "changes_recorded": self.changes_recorded,
            "validation_results": self.validation_results,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MaintenanceSession:
    """Complete maintenance session."""
    session_id: str
    url: str
    change_intelligence_session_id: str
    maintenance_plan: MaintenancePlan
    regeneration_results: List[RegenerationResult]
    validation_results: List[ValidationResult]
    continuous_validation_results: List[ContinuousValidationResult]
    baseline_update: Optional[BaselineUpdate]
    overall_outcome: MaintenanceOutcome
    total_tests: int
    affected_tests: int
    preserved_tests: int
    regenerated_tests: int
    successful_maintenance: int
    failed_maintenance: int
    human_reviews: int
    metrics: Dict[str, Any]
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "url": self.url,
            "change_intelligence_session_id": self.change_intelligence_session_id,
            "maintenance_plan": self.maintenance_plan.to_dict(),
            "regeneration_results": [r.to_dict() for r in self.regeneration_results],
            "validation_results": [v.to_dict() for v in self.validation_results],
            "continuous_validation_results": [c.to_dict() for c in self.continuous_validation_results],
            "baseline_update": self.baseline_update.to_dict() if self.baseline_update else None,
            "overall_outcome": self.overall_outcome.value,
            "total_tests": self.total_tests,
            "affected_tests": self.affected_tests,
            "preserved_tests": self.preserved_tests,
            "regenerated_tests": self.regenerated_tests,
            "successful_maintenance": self.successful_maintenance,
            "failed_maintenance": self.failed_maintenance,
            "human_reviews": self.human_reviews,
            "metrics": self.metrics,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }
