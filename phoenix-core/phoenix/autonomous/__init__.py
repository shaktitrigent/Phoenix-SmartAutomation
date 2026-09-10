"""Autonomous Agent Module - Priority 28.

This module implements the Universal Autonomous End-to-End Agent that orchestrates
all Phoenix intelligence components (Priorities 20-27) to perform end-to-end
autonomous testing starting from only a URL.

Priority 28: Universal Autonomous End-to-End Agent + Real Headed Runtime Validation
"""

from __future__ import annotations

from phoenix.autonomous.models import (
    AutonomousPhase,
    DecisionType,
    RiskLevel,
    ChangeSeverity,
    AutonomousDecision,
    ExplorationSession,
    TestStrategy,
    ApplicationChange,
    AutonomousExecution,
    EvidenceTrace,
)

from phoenix.autonomous.autonomous_agent import AutonomousAgent
from phoenix.autonomous.decision_engine import DecisionEngine

__all__ = [
    # Models
    "AutonomousPhase",
    "DecisionType",
    "RiskLevel",
    "ChangeSeverity",
    "AutonomousDecision",
    "ExplorationSession",
    "TestStrategy",
    "ApplicationChange",
    "AutonomousExecution",
    "EvidenceTrace",
    
    # Main components
    "AutonomousAgent",
    "DecisionEngine",
]

__version__ = "1.0.0"
