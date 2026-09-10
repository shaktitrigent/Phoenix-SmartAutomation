"""Test Intelligence Models - Universal AI Test Scenario Data Structures.

This module defines all data models for AI test scenario generation,
validation, and quality assessment. These models are completely generic
and work for ANY web application.

Priority 23: Universal AI Test Intelligence
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Test Scenario Types - Generic, Application-Agnostic
# ---------------------------------------------------------------------------

class TestScenarioType(str, Enum):
    """Generic test scenario types that work for ANY web application."""
    
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    VALIDATION = "validation"
    SECURITY = "security"
    ERROR_HANDLING = "error_handling"
    NAVIGATION = "navigation"
    CRUD = "crud"
    SEARCH = "search"
    UPLOAD = "upload"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Test Priority Levels - Generic Prioritization
# ---------------------------------------------------------------------------

class TestPriority(str, Enum):
    """Generic test priority levels."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Test Risk Levels - Generic Risk Assessment
# ---------------------------------------------------------------------------

class TestRisk(str, Enum):
    """Generic test risk levels."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Test Quality Validation Issues
# ---------------------------------------------------------------------------

class QualityIssueType(str, Enum):
    """Types of quality issues that can be detected in test scenarios."""
    
    MISSING_STEPS = "missing_steps"
    MISSING_EXPECTED_RESULT = "missing_expected_result"
    MISSING_PRECONDITIONS = "missing_preconditions"
    INVALID_LOCATOR = "invalid_locator"
    UNSUPPORTED_ACTION = "unsupported_action"
    DUPLICATE_SCENARIO = "duplicate_scenario"
    CONTRADICTORY_STEPS = "contradictory_steps"
    IMPOSSIBLE_NAVIGATION = "impossible_navigation"
    MISSING_TEST_DATA = "missing_test_data"
    MISSING_VALIDATION = "missing_validation"
    PLACEHOLDER_IMPLEMENTATION = "placeholder_implementation"
    EMPTY_TEST_BODY = "empty_test_body"
    UNSUPPORTED_ASSUMPTIONS = "unsupported_assumptions"
    LOW_CONFIDENCE = "low_confidence"


# ---------------------------------------------------------------------------
# Test Scenario Model
# ---------------------------------------------------------------------------

class TestScenario(BaseModel):
    """Represents a generated test scenario with full intelligence."""
    
    # Identification
    scenario_id: str = Field(..., description="Unique scenario identifier")
    title: str = Field(..., description="Scenario title")
    
    # Classification
    scenario_type: TestScenarioType = Field(..., description="Type of test scenario")
    priority: TestPriority = Field(default=TestPriority.MEDIUM, description="Test priority")
    risk: TestRisk = Field(default=TestRisk.MEDIUM, description="Test risk level")
    
    # Description
    purpose: str = Field(default="", description="Purpose of this test scenario")
    
    # Classification
    scenario_type: TestScenarioType = Field(..., description="Type of test scenario")
    priority: TestPriority = Field(default=TestPriority.MEDIUM, description="Test priority")
    risk: TestRisk = Field(default=TestRisk.MEDIUM, description="Test risk level")
    
    # Description
    purpose: str = Field(..., description="Purpose of this test scenario")
    business_intent: str = Field(default="", description="Business intent being tested")
    
    # Context
    preconditions: List[str] = Field(default_factory=list, description="Preconditions for test")
    flow: str = Field(default="", description="Business flow being tested")
    
    # Test content
    steps: List[str] = Field(default_factory=list, description="Test steps")
    test_data: Dict[str, Any] = Field(default_factory=dict, description="Test data to use")
    expected_result: str = Field(default="", description="Expected result")
    
    # Validation
    validation_rules: List[str] = Field(default_factory=list, description="Validation rules to verify")
    
    # Quality assessment
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Quality score (0-100)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Generation confidence")
    
    # Evidence
    source_evidence: Dict[str, Any] = Field(default_factory=dict, description="Evidence for scenario generation")
    confidence_breakdown: Dict[str, float] = Field(default_factory=dict, description="Confidence breakdown by source")
    
    # Execution metadata
    execution_cost: int = Field(default=1, description="Estimated execution cost (1-10)")
    business_impact: str = Field(default="", description="Business impact if this fails")
    
    # Integration
    related_components: List[str] = Field(default_factory=list, description="Related component IDs")
    related_flows: List[str] = Field(default_factory=list, description="Related flow IDs")
    
    # Status
    is_duplicate: bool = Field(default=False, description="Whether this is a duplicate scenario")
    duplicate_of: Optional[str] = Field(default=None, description="ID of duplicate scenario")
    
    # Validation results
    quality_issues: List[Dict[str, Any]] = Field(default_factory=list, description="Quality issues detected")
    is_validated: bool = Field(default=False, description="Whether scenario has been validated")
    
    # Metadata
    generated_by: str = Field(default="ai_test_intelligence", description="What generated this scenario")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Test Coverage Model
# ---------------------------------------------------------------------------

class TestCoverage(BaseModel):
    """Represents test coverage for a business flow or component."""
    
    # Target
    target_id: str = Field(..., description="ID of the target (flow, component, etc.)")
    target_type: str = Field(..., description="Type of target (flow, component, page)")
    target_name: str = Field(default="", description="Name of the target")
    
    # Coverage by scenario type
    positive_coverage: str = Field(default="not_covered", description="Positive scenario coverage")
    negative_coverage: str = Field(default="not_covered", description="Negative scenario coverage")
    boundary_coverage: str = Field(default="not_covered", description="Boundary scenario coverage")
    validation_coverage: str = Field(default="not_covered", description="Validation scenario coverage")
    security_coverage: str = Field(default="not_covered", description="Security scenario coverage")
    error_handling_coverage: str = Field(default="not_covered", description="Error handling coverage")
    
    # Overall coverage
    overall_coverage: str = Field(default="not_covered", description="Overall coverage status")
    coverage_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Coverage percentage")
    
    # Missing scenarios
    missing_scenarios: List[str] = Field(default_factory=list, description="Missing scenario types")
    recommended_scenarios: List[str] = Field(default_factory=list, description="Recommended scenarios to add")
    
    # Related scenarios
    covered_scenario_ids: List[str] = Field(default_factory=list, description="IDs of scenarios covering this")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Quality Issue Model
# ---------------------------------------------------------------------------

class QualityIssue(BaseModel):
    """Represents a quality issue detected in a test scenario."""
    
    issue_type: QualityIssueType = Field(..., description="Type of quality issue")
    severity: str = Field(default="medium", description="Issue severity (low, medium, high, critical)")
    description: str = Field(..., description="Description of the issue")
    
    # Location
    affected_field: str = Field(default="", description="Field affected by the issue")
    step_index: Optional[int] = Field(default=None, description="Step index if applicable")
    
    # Recommendation
    recommendation: str = Field(default="", description="Recommendation to fix the issue")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for the issue")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Test Scenario Generation Request
# ---------------------------------------------------------------------------

class TestGenerationRequest(BaseModel):
    """Request for test scenario generation."""
    
    # Context
    business_flow_id: Optional[str] = Field(default=None, description="Business flow to generate tests for")
    component_id: Optional[str] = Field(default=None, description="Component to generate tests for")
    page_type: Optional[str] = Field(default=None, description="Page type to generate tests for")
    business_intent: Optional[str] = Field(default=None, description="Business intent to generate tests for")
    
    # Generation options
    scenario_types: List[TestScenarioType] = Field(default_factory=list, description="Types of scenarios to generate")
    max_scenarios: int = Field(default=50, description="Maximum number of scenarios to generate")
    min_quality_score: float = Field(default=70.0, description="Minimum quality score threshold")
    
    # Intelligence sources
    use_semantic_understanding: bool = Field(default=True, description="Use semantic understanding")
    use_component_intelligence: bool = Field(default=True, description="Use component intelligence")
    use_flow_intelligence: bool = Field(default=True, description="Use flow intelligence")
    use_validation_intelligence: bool = Field(default=True, description="Use validation intelligence")
    
    # Validation options
    enable_duplicate_detection: bool = Field(default=True, description="Enable duplicate detection")
    enable_quality_validation: bool = Field(default=True, description="Enable quality validation")
    enable_prioritization: bool = Field(default=True, description="Enable test prioritization")
    
    # Metadata
    request_id: str = Field(default_factory=lambda: f"req_{datetime.now(timezone.utc).timestamp()}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Test Scenario Generation Response
# ---------------------------------------------------------------------------

class TestGenerationResponse(BaseModel):
    """Response from test scenario generation."""
    
    # Request info
    request_id: str = Field(..., description="Request ID")
    
    # Generated scenarios
    scenarios: List[TestScenario] = Field(default_factory=list, description="Generated scenarios")
    
    # Statistics
    total_generated: int = Field(default=0, description="Total scenarios generated")
    total_validated: int = Field(default=0, description="Total scenarios validated")
    total_rejected: int = Field(default=0, description="Total scenarios rejected")
    duplicates_removed: int = Field(default=0, description="Number of duplicates removed")
    
    # Coverage
    coverage: List[TestCoverage] = Field(default_factory=list, description="Coverage information")
    
    # Quality statistics
    average_quality_score: float = Field(default=0.0, description="Average quality score")
    average_confidence: float = Field(default=0.0, description="Average confidence")
    
    # Metadata
    generation_time_ms: float = Field(default=0.0, description="Generation time in milliseconds")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Runtime Learning Feedback
# ---------------------------------------------------------------------------

class TestExecutionFeedback(BaseModel):
    """Feedback from test execution for runtime learning."""
    
    # Scenario info
    scenario_id: str = Field(..., description="Scenario ID")
    execution_id: str = Field(..., description="Execution ID")
    
    # Execution results
    success: bool = Field(default=False, description="Whether execution was successful")
    execution_time_ms: float = Field(default=0.0, description="Execution time")
    
    # Failure information
    failure_type: Optional[str] = Field(default=None, description="Type of failure if any")
    failure_reason: str = Field(default="", description="Reason for failure")
    
    # Learning observations
    observed_behavior: Dict[str, Any] = Field(default_factory=dict, description="Observed behavior")
    correct_assumptions: List[str] = Field(default_factory=list, description="Assumptions that were correct")
    incorrect_assumptions: List[str] = Field(default_factory=list, description="Assumptions that were incorrect")
    
    # Quality feedback
    quality_adequate: bool = Field(default=True, description="Whether test quality was adequate")
    quality_feedback: str = Field(default="", description="Quality feedback")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Healing Integration Context
# ---------------------------------------------------------------------------

class TestHealingContext(BaseModel):
    """Context for healing integration with test intelligence."""
    
    # Scenario info
    scenario_id: str = Field(..., description="Scenario ID")
    failing_step_index: int = Field(..., description="Index of failing step")
    
    # Failure analysis
    failure_type: str = Field(..., description="Type of failure")
    failure_intent: str = Field(default="", description="Intent of the failing step")
    
    # Recovery options
    alternative_components: List[str] = Field(default_factory=list, description="Alternative component IDs")
    alternative_flows: List[str] = Field(default_factory=list, description="Alternative flow IDs")
    recovery_strategies: List[str] = Field(default_factory=list, description="Recovery strategies")
    
    # Confidence
    recovery_confidence: float = Field(default=0.0, description="Confidence in recovery")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
