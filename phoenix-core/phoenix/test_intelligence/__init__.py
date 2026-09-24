"""Test Intelligence - Universal AI Test Scenario Generation (Priority 23).

This module provides AI-powered test scenario generation, validation,
and quality assessment for ANY web application without product-specific
knowledge.

Priority 23 capabilities:
- Universal Test Scenario Intelligence
- AI Test Scenario Reasoning
- Test Coverage Intelligence
- Duplicate Test Detection
- Test Prioritization
- AI Test Quality Validation
- Test Generation Confidence
- Runtime Learning Integration
- Healing Integration
"""

from phoenix.test_intelligence.models import (
    TestScenarioType,
    TestPriority,
    TestRisk,
    QualityIssueType,
    TestScenario,
    TestCoverage,
    QualityIssue,
    TestGenerationRequest,
    TestGenerationResponse,
    TestExecutionFeedback,
    TestHealingContext,
)

from phoenix.test_intelligence.scenario_generator import TestScenarioGenerator
from phoenix.test_intelligence.scenario_reasoning import TestScenarioReasoning
from phoenix.test_intelligence.coverage_intelligence import CoverageIntelligence
from phoenix.test_intelligence.duplicate_detector import DuplicateDetector
from phoenix.test_intelligence.test_prioritizer import TestPrioritizer
from phoenix.test_intelligence.quality_validator import AITestValidator
from phoenix.test_intelligence.confidence_calculator import ConfidenceCalculator
from phoenix.test_intelligence.runtime_learning import TestRuntimeLearning
from phoenix.test_intelligence.healing_integration import TestHealingIntegration

__all__ = [
    # Models
    "TestScenarioType",
    "TestPriority",
    "TestRisk",
    "QualityIssueType",
    "TestScenario",
    "TestCoverage",
    "QualityIssue",
    "TestGenerationRequest",
    "TestGenerationResponse",
    "TestExecutionFeedback",
    "TestHealingContext",
    
    # Core components
    "TestScenarioGenerator",
    "TestScenarioReasoning",
    "CoverageIntelligence",
    "DuplicateDetector",
    "TestPrioritizer",
    "AITestValidator",
    "ConfidenceCalculator",
    "TestRuntimeLearning",
    "TestHealingIntegration",
]
