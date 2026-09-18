"""Automation Generation Module - Universal Autonomous Test Automation Generation.

This module implements Priority 24: Universal Autonomous Test Automation Generation
for the Phoenix Enterprise AI Platform.

Components:
- models: Data models for automation generation
- automation_planner: Converts test scenarios to automation plans
- action_generator: Generates executable Playwright actions
- assertion_generator: Generates evidence-based assertions
- pom_manager: Manages Page Object generation and reuse
- locator_strategy: Evidence-driven locator selection with fallback
- quality_gate: Validates automation before execution
- test_data_intelligence: Determines test data requirements
- sensitive_data_protection: Protects sensitive values
- automation_generator: Main coordinator for all components
- failure_classifier: Classifies automation failures
- automation_regeneration: Handles application changes

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

from phoenix.automation_generation.models import (
    AutomationStatus,
    FailureType,
    ActionType,
    AssertionType,
    TestDataType,
    AutomationPlan,
    Action,
    Assertion,
    TestDataRequirement,
    GeneratedAutomation,
    FailureClassification,
    AutomationMetrics,
)

from phoenix.automation_generation.automation_planner import AutomationPlanner
from phoenix.automation_generation.action_generator import ActionGenerator
from phoenix.automation_generation.assertion_generator import AssertionGenerator
from phoenix.automation_generation.pom_manager import POMManager
from phoenix.automation_generation.locator_strategy import (
    LocatorStrategy,
    LocatorFallback,
    LocatorChain,
    LocatorStrategyManager,
)
from phoenix.automation_generation.quality_gate import (
    QualityIssue,
    QualityGateResult,
    AutomationQualityGate,
)
from phoenix.automation_generation.test_data_intelligence import TestDataIntelligence
from phoenix.automation_generation.sensitive_data_protection import SensitiveDataProtection
from phoenix.automation_generation.automation_generator import AutomationGenerationCoordinator
from phoenix.automation_generation.failure_classifier import FailureClassifier
from phoenix.automation_generation.automation_regeneration import AutomationRegeneration

__all__ = [
    # Models
    "AutomationStatus",
    "FailureType",
    "ActionType",
    "AssertionType",
    "TestDataType",
    "AutomationPlan",
    "Action",
    "Assertion",
    "TestDataRequirement",
    "GeneratedAutomation",
    "FailureClassification",
    "AutomationMetrics",
    # Components
    "AutomationPlanner",
    "ActionGenerator",
    "AssertionGenerator",
    "POMManager",
    "LocatorStrategy",
    "LocatorFallback",
    "LocatorChain",
    "LocatorStrategyManager",
    "QualityIssue",
    "QualityGateResult",
    "AutomationQualityGate",
    "TestDataIntelligence",
    "SensitiveDataProtection",
    "AutomationGenerationCoordinator",
    "FailureClassifier",
    "AutomationRegeneration",
]

__version__ = "1.0.0"
