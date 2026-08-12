"""Change Intelligence Module - Priority 29.

This module implements universal autonomous change intelligence and adaptive
test maintenance for the Phoenix Enterprise AI Platform.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

from phoenix.change_intelligence.models import (
    ChangeType,
    ChangeSeverity,
    MaintenanceAction,
    RiskLevel,
    SemanticChange,
    Baseline,
    ImpactAnalysis,
    MaintenanceDecision,
    ChangeIntelligenceSession,
)

from phoenix.change_intelligence.baseline_manager import BaselineManager
from phoenix.change_intelligence.change_detector import ChangeDetector
from phoenix.change_intelligence.impact_analyzer import ImpactAnalyzer
from phoenix.change_intelligence.change_intelligence import ChangeIntelligence

__all__ = [
    # Models
    "ChangeType",
    "ChangeSeverity",
    "MaintenanceAction",
    "RiskLevel",
    "SemanticChange",
    "Baseline",
    "ImpactAnalysis",
    "MaintenanceDecision",
    "ChangeIntelligenceSession",
    
    # Components
    "BaselineManager",
    "ChangeDetector",
    "ImpactAnalyzer",
    "ChangeIntelligence",
]

__version__ = "1.0.0"
