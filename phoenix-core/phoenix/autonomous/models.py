"""Autonomous Agent Models - Priority 28.

This module defines the data models for the autonomous agent that orchestrates
all Phoenix intelligence components (Priorities 20-27) to perform end-to-end
autonomous testing starting from only a URL.

Priority 28: Universal Autonomous End-to-End Agent + Real Headed Runtime Validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AutonomousPhase(Enum):
    """Autonomous agent execution phases."""
    INITIALIZATION = "initialization"
    EXPLORATION = "exploration"
    UNDERSTANDING = "understanding"
    DECISION = "decision"
    FLOW_DISCOVERY = "flow_discovery"
    TEST_GENERATION = "test_generation"
    AUTOMATION_GENERATION = "automation_generation"
    EXECUTION = "execution"
    ASSERTION = "assertion"
    HEALING = "healing"
    LEARNING = "learning"
    CHANGE_DETECTION = "change_detection"
    MAINTENANCE = "maintenance"
    REGENERATION = "regeneration"
    REPORTING = "reporting"
    COMPLETED = "completed"


class DecisionType(Enum):
    """Types of autonomous decisions."""
    EXPLORE_PAGE = "explore_page"
    EXPLORE_COMPONENT = "explore_component"
    CLICK_ELEMENT = "click_element"
    FILL_INPUT = "fill_input"
    SUBMIT_FORM = "submit_form"
    NAVIGATE = "navigate"
    GENERATE_TEST = "generate_test"
    EXECUTE_TEST = "execute_test"
    HEAL_FAILURE = "heal_failure"
    RETRY_ACTION = "retry_action"
    SKIP_COMPONENT = "skip_component"
    TERMINATE_EXPLORATION = "terminate_exploration"


class RiskLevel(Enum):
    """Risk levels for autonomous decisions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeSeverity(Enum):
    """Severity of application changes."""
    SAFE = "safe"
    MINOR = "minor"
    SIGNIFICANT = "significant"
    BREAKING = "breaking"


@dataclass
class AutonomousDecision:
    """A decision made by the autonomous agent."""
    decision_type: DecisionType
    reason: str
    evidence: Dict[str, Any]
    confidence: float
    risk: RiskLevel
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "risk": self.risk.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExplorationSession:
    """An exploration session for a URL."""
    session_id: str
    url: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    pages_explored: List[str] = field(default_factory=list)
    components_discovered: List[Dict[str, Any]] = field(default_factory=list)
    flows_discovered: List[Dict[str, Any]] = field(default_factory=list)
    decisions_made: List[AutonomousDecision] = field(default_factory=list)
    status: str = "in_progress"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "url": self.url,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "pages_explored": self.pages_explored,
            "components_discovered": self.components_discovered,
            "flows_discovered": self.flows_discovered,
            "decisions_made": [d.to_dict() for d in self.decisions_made],
            "status": self.status,
        }


@dataclass
class TestStrategy:
    """A test strategy for discovered capabilities."""
    strategy_id: str
    capability: str
    test_types: List[str] = field(default_factory=list)
    positive_scenarios: List[str] = field(default_factory=list)
    negative_scenarios: List[str] = field(default_factory=list)
    boundary_scenarios: List[str] = field(default_factory=list)
    validation_scenarios: List[str] = field(default_factory=list)
    security_scenarios: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "capability": self.capability,
            "test_types": self.test_types,
            "positive_scenarios": self.positive_scenarios,
            "negative_scenarios": self.negative_scenarios,
            "boundary_scenarios": self.boundary_scenarios,
            "validation_scenarios": self.validation_scenarios,
            "security_scenarios": self.security_scenarios,
            "confidence": self.confidence,
        }


@dataclass
class ApplicationChange:
    """A detected change in the application."""
    change_id: str
    change_type: str
    previous_state: Dict[str, Any]
    current_state: Dict[str, Any]
    severity: ChangeSeverity
    impact: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_id": self.change_id,
            "change_type": self.change_type,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "severity": self.severity.value,
            "impact": self.impact,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AutonomousExecution:
    """An autonomous execution from URL to report."""
    execution_id: str
    url: str
    exploration_session: ExplorationSession
    test_strategies: List[TestStrategy] = field(default_factory=list)
    generated_automations: List[Dict[str, Any]] = field(default_factory=list)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    healing_sessions: List[Dict[str, Any]] = field(default_factory=list)
    learning_updates: List[Dict[str, Any]] = field(default_factory=list)
    detected_changes: List[Dict[str, Any]] = field(default_factory=list)  # Priority 29
    change_intelligence_session: Optional[Dict[str, Any]] = None  # Priority 29
    maintenance_session: Optional[Dict[str, Any]] = None  # Priority 30
    risk_intelligence_session: Optional[Dict[str, Any]] = None  # Priority 31
    report: Optional[Dict[str, Any]] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "in_progress"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "url": self.url,
            "exploration_session": self.exploration_session.to_dict(),
            "test_strategies": [s.to_dict() for s in self.test_strategies],
            "generated_automations": self.generated_automations,
            "execution_results": self.execution_results,
            "healing_sessions": self.healing_sessions,
            "learning_updates": self.learning_updates,
            "detected_changes": [c.to_dict() for c in self.detected_changes],
            "report": self.report,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
        }


@dataclass
class EvidenceTrace:
    """A trace of evidence for an autonomous decision."""
    trace_id: str
    decision: AutonomousDecision
    dom_evidence: Optional[Dict[str, Any]] = None
    semantic_evidence: Optional[Dict[str, Any]] = None
    component_evidence: Optional[Dict[str, Any]] = None
    flow_evidence: Optional[Dict[str, Any]] = None
    execution_evidence: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "decision": self.decision.to_dict(),
            "dom_evidence": self.dom_evidence,
            "semantic_evidence": self.semantic_evidence,
            "component_evidence": self.component_evidence,
            "flow_evidence": self.flow_evidence,
            "execution_evidence": self.execution_evidence,
            "timestamp": self.timestamp.isoformat(),
        }
