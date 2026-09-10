"""Change Intelligence Models - Priority 29.

This module defines the data models for the change intelligence system that
detects application changes, classifies them semantically, and determines
maintenance actions.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ChangeType(Enum):
    """Types of semantic changes."""
    COMPONENT_ADDED = "component_added"
    COMPONENT_REMOVED = "component_removed"
    COMPONENT_MODIFIED = "component_modified"
    LOCATOR_CHANGED = "locator_changed"
    LOCATOR_INVALIDATED = "locator_invalidated"
    PAGE_TYPE_CHANGED = "page_type_changed"
    PAGE_STRUCTURE_CHANGED = "page_structure_changed"
    FLOW_ADDED = "flow_added"
    FLOW_REMOVED = "flow_removed"
    FLOW_MODIFIED = "flow_modified"
    VALIDATION_ADDED = "validation_added"
    VALIDATION_REMOVED = "validation_removed"
    VALIDATION_MODIFIED = "validation_modified"
    NAVIGATION_CHANGED = "navigation_changed"
    ATTRIBUTE_CHANGED = "attribute_changed"
    TEXT_CHANGED = "text_changed"
    DOM_CHANGED = "dom_changed"


class ChangeSeverity(Enum):
    """Severity of changes."""
    SAFE = "safe"
    MINOR = "minor"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


class MaintenanceAction(Enum):
    """Maintenance actions for changes."""
    NO_ACTION = "no_action"
    REVALIDATE = "revalidate"
    REPAIR_LOCATOR = "repair_locator"
    REGENERATE_ACTION = "regenerate_action"
    REGENERATE_ASSERTION = "regenerate_assertion"
    UPDATE_PAGE_OBJECT = "update_page_object"
    REGENERATE_TEST_STEP = "regenerate_test_step"
    REGENERATE_TEST = "regenerate_test"
    REGENERATE_FLOW = "regenerate_flow"
    DEPRECATE_TEST = "deprecate_test"
    CREATE_NEW_TEST = "create_new_test"
    REQUEST_HUMAN_REVIEW = "request_human_review"


class RiskLevel(Enum):
    """Risk levels for changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SemanticChange:
    """A semantically classified change."""
    change_id: str
    change_type: ChangeType
    previous_state: Dict[str, Any]
    current_state: Dict[str, Any]
    severity: ChangeSeverity
    confidence: float
    evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Baseline:
    """A baseline snapshot of application state."""
    baseline_id: str
    url: str
    version: int
    dom_snapshot: str
    dom_hash: str
    page_type: str
    components: List[Dict[str, Any]]
    locators: List[Dict[str, Any]]
    flows: List[Dict[str, Any]]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_id": self.baseline_id,
            "url": self.url,
            "version": self.version,
            "dom_snapshot": self.dom_snapshot,
            "dom_hash": self.dom_hash,
            "page_type": self.page_type,
            "components": self.components,
            "locators": self.locators,
            "flows": self.flows,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ImpactAnalysis:
    """Analysis of change impact on tests."""
    analysis_id: str
    change_id: str
    affected_components: List[str]
    affected_flows: List[str]
    affected_scenarios: List[str]
    affected_automations: List[str]
    affected_page_objects: List[str]
    affected_locators: List[str]
    risk_score: float
    recommended_action: MaintenanceAction
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "change_id": self.change_id,
            "affected_components": self.affected_components,
            "affected_flows": self.affected_flows,
            "affected_scenarios": self.affected_scenarios,
            "affected_automations": self.affected_automations,
            "affected_page_objects": self.affected_page_objects,
            "affected_locators": self.affected_locators,
            "risk_score": self.risk_score,
            "recommended_action": self.recommended_action.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MaintenanceDecision:
    """A maintenance decision for a change."""
    decision_id: str
    change_id: str
    action: MaintenanceAction
    reason: str
    evidence: Dict[str, Any]
    confidence: float
    risk: RiskLevel
    requires_human_review: bool
    human_review_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "change_id": self.change_id,
            "action": self.action.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "risk": self.risk.value,
            "requires_human_review": self.requires_human_review,
            "human_review_reason": self.human_review_reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ChangeIntelligenceSession:
    """A complete change intelligence session."""
    session_id: str
    url: str
    previous_baseline: Optional[Baseline]
    current_baseline: Baseline
    detected_changes: List[SemanticChange]
    impact_analyses: List[ImpactAnalysis]
    maintenance_decisions: List[MaintenanceDecision]
    repairs_executed: List[Dict[str, Any]]
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "in_progress"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "url": self.url,
            "previous_baseline": self.previous_baseline.to_dict() if self.previous_baseline else None,
            "current_baseline": self.current_baseline.to_dict(),
            "detected_changes": [c.to_dict() for c in self.detected_changes],
            "impact_analyses": [a.to_dict() for a in self.impact_analyses],
            "maintenance_decisions": [d.to_dict() for d in self.maintenance_decisions],
            "repairs_executed": self.repairs_executed,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
        }
