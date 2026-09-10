"""Automation Generation Models - Universal Autonomous Test Automation Data Structures.

This module defines all data models for automation planning, generation,
validation, and execution. These models are completely generic and work
for ANY web application.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Automation Status Types
# ---------------------------------------------------------------------------

class AutomationStatus(str, Enum):
    """Status of generated automation."""
    
    PLANNED = "planned"
    GENERATED = "generated"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXECUTED = "executed"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    HEALED = "healed"
    REGENERATED = "regenerated"


# ---------------------------------------------------------------------------
# Failure Classification Types
# ---------------------------------------------------------------------------

class FailureType(str, Enum):
    """Types of failures in generated automation."""
    
    AUTOMATION_FAILURE = "automation_failure"
    LOCATOR_FAILURE = "locator_failure"
    APPLICATION_FAILURE = "application_failure"
    NAVIGATION_FAILURE = "navigation_failure"
    ASSERTION_FAILURE = "assertion_failure"
    DATA_FAILURE = "data_failure"
    ENVIRONMENT_FAILURE = "environment_failure"
    GENERATION_FAILURE = "generation_failure"


# ---------------------------------------------------------------------------
# Quality Issue Types
# ---------------------------------------------------------------------------

class QualityIssueType(str, Enum):
    """Types of quality issues in generated automation."""
    
    PLACEHOLDER_IMPLEMENTATION = "placeholder_implementation"
    EMPTY_TEST_BODY = "empty_test_body"
    PLACEHOLDER_LOCATOR = "placeholder_locator"
    FAKE_ASSERTION = "fake_assertion"
    MISSING_ASSERTION = "missing_assertion"
    MISSING_VALIDATION = "missing_validation"
    INVALID_LOCATOR = "invalid_locator"
    UNSUPPORTED_ACTION = "unsupported_action"
    MISSING_TEST_DATA = "missing_test_data"
    CONTRADICTORY_STEPS = "contradictory_steps"
    IMPOSSIBLE_NAVIGATION = "impossible_navigation"
    DUPLICATE_AUTOMATION = "duplicate_automation"
    HARDCODED_CREDENTIALS = "hardcoded_credentials"
    UNSUPPORTED_ASSUMPTIONS = "unsupported_assumptions"
    APPLICATION_SPECIFIC = "application_specific"


# ---------------------------------------------------------------------------
# Action Types - Generic Playwright Actions
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """Generic action types for automation generation."""
    
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    HOVER = "hover"
    PRESS = "press"
    SCROLL = "scroll"
    SEARCH = "search"
    SUBMIT = "submit"
    WAIT = "wait"
    ASSERT = "assert"
    VERIFY = "verify"
    OPEN = "open"
    CLOSE = "close"
    EXPAND = "expand"
    COLLAPSE = "collapse"
    SWITCH_TAB = "switch_tab"
    SWITCH_FRAME = "switch_frame"
    TYPE = "type"
    CLEAR = "clear"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"


# ---------------------------------------------------------------------------
# Assertion Types - Generic Assertions
# ---------------------------------------------------------------------------

class AssertionType(str, Enum):
    """Generic assertion types for automation generation."""
    
    PAGE_TITLE = "page_title"
    URL = "url"
    VISIBLE_TEXT = "visible_text"
    ELEMENT_VISIBILITY = "element_visibility"
    ELEMENT_STATE = "element_state"
    ELEMENT_VALUE = "element_value"
    ELEMENT_COUNT = "element_count"
    TABLE_CONTENTS = "table_contents"
    SUCCESS_MESSAGE = "success_message"
    ERROR_MESSAGE = "error_message"
    VALIDATION_MESSAGE = "validation_message"
    NAVIGATION_RESULT = "navigation_result"
    CREATED_RECORD = "created_record"
    UPDATED_RECORD = "updated_record"
    DELETED_RECORD = "deleted_record"
    SEARCH_RESULT = "search_result"
    UPLOAD_RESULT = "upload_result"
    DOWNLOAD_RESULT = "download_result"


# ---------------------------------------------------------------------------
# Test Data Types - Generic Data Types
# ---------------------------------------------------------------------------

class TestDataType(str, Enum):
    """Generic test data types."""
    
    USERNAME = "username"
    PASSWORD = "password"
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    ADDRESS = "address"
    DATE = "date"
    NUMBER = "number"
    CURRENCY = "currency"
    TEXT = "text"
    FILE = "file"
    DROPDOWN_VALUE = "dropdown_value"
    SEARCH_QUERY = "search_query"
    URL = "url"
    ID = "id"
    BOOLEAN = "boolean"
    JSON = "json"


# ---------------------------------------------------------------------------
# Automation Plan Model
# ---------------------------------------------------------------------------

class AutomationPlan(BaseModel):
    """Represents a complete automation plan for a test scenario."""
    
    # Identification
    scenario_id: str = Field(..., description="Source test scenario ID")
    automation_id: str = Field(..., description="Unique automation ID")
    
    # Business context
    business_intent: str = Field(..., description="Business intent being automated")
    preconditions: List[str] = Field(default_factory=list, description="Preconditions")
    
    # Required resources
    required_pages: List[str] = Field(default_factory=list, description="Required page objects")
    required_components: List[str] = Field(default_factory=list, description="Required component IDs")
    
    # Automation steps
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="Planned actions")
    locators: Dict[str, str] = Field(default_factory=dict, description="Locator mapping")
    test_data: Dict[str, Any] = Field(default_factory=dict, description="Test data requirements")
    
    # Validation
    assertions: List[Dict[str, Any]] = Field(default_factory=list, description="Planned assertions")
    expected_outcomes: List[str] = Field(default_factory=list, description="Expected outcomes")
    
    # Navigation
    navigation_steps: List[Dict[str, Any]] = Field(default_factory=list, description="Navigation steps")
    
    # Recovery
    recovery_strategy: str = Field(default="", description="Recovery strategy")
    
    # Quality assessment
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Plan confidence")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting evidence")
    
    # Status
    status: AutomationStatus = Field(default=AutomationStatus.PLANNED, description="Automation status")
    
    # Metadata
    generated_by: str = Field(default="automation_planner", description="Generator")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Action Model
# ---------------------------------------------------------------------------

class Action(BaseModel):
    """Represents a single automation action."""
    
    action_id: str = Field(..., description="Unique action ID")
    action_type: ActionType = Field(..., description="Type of action")
    
    # Target
    target_component_id: str = Field(default="", description="Target component ID")
    target_locator: str = Field(default="", description="Target locator")
    
    # Parameters
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    # Context
    page_context: str = Field(default="", description="Page context")
    business_context: str = Field(default="", description="Business context")
    
    # Quality
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Action confidence")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    
    # Fallback
    fallback_locators: List[str] = Field(default_factory=list, description="Fallback locators")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Assertion Model
# ---------------------------------------------------------------------------

class Assertion(BaseModel):
    """Represents a single automation assertion."""
    
    assertion_id: str = Field(..., description="Unique assertion ID")
    assertion_type: AssertionType = Field(..., description="Type of assertion")
    
    # Target
    target_component_id: str = Field(default="", description="Target component ID")
    target_locator: str = Field(default="", description="Target locator")
    
    # Expected value
    expected_value: Any = Field(default=None, description="Expected value")
    comparison_type: str = Field(default="equals", description="Comparison type")
    
    # Context
    page_context: str = Field(default="", description="Page context")
    
    # Quality
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Assertion confidence")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Test Data Requirement Model
# ---------------------------------------------------------------------------

class TestDataRequirement(BaseModel):
    """Represents a test data requirement."""
    
    data_id: str = Field(..., description="Unique data ID")
    data_type: TestDataType = Field(..., description="Type of data")
    
    # Requirements
    field_name: str = Field(default="", description="Field name")
    is_required: bool = Field(default=False, description="Whether required")
    
    # Constraints
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Data constraints")
    validation_rules: List[str] = Field(default_factory=list, description="Validation rules")
    
    # Source
    source: str = Field(default="", description="Data source (user, generated, env)")
    is_sensitive: bool = Field(default=False, description="Whether sensitive data")
    
    # Value
    provided_value: Any = Field(default=None, description="Provided value")
    is_missing: bool = Field(default=True, description="Whether value is missing")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Generated Automation Model
# ---------------------------------------------------------------------------

class GeneratedAutomation(BaseModel):
    """Represents a complete generated automation script."""
    
    # Identification
    automation_id: str = Field(..., description="Unique automation ID")
    scenario_id: str = Field(..., description="Source scenario ID")
    
    # Script
    script_code: str = Field(..., description="Generated Playwright script")
    script_path: str = Field(default="", description="Script file path")
    
    # Components
    pom_objects: List[str] = Field(default_factory=list, description="Page objects used")
    reused_poms: List[str] = Field(default_factory=list, description="Reused page objects")
    
    # Quality
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Quality score")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Generation confidence")
    validation_status: str = Field(default="pending", description="Validation status")
    
    # Issues
    quality_issues: List[Dict[str, Any]] = Field(default_factory=list, description="Quality issues")
    
    # Status
    status: AutomationStatus = Field(default=AutomationStatus.GENERATED, description="Status")
    
    # Execution
    execution_count: int = Field(default=0, description="Execution count")
    pass_count: int = Field(default=0, description="Pass count")
    fail_count: int = Field(default=0, description="Fail count")
    heal_count: int = Field(default=0, description="Heal count")
    
    # Metadata
    generated_by: str = Field(default="automation_generator", description="Generator")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Failure Classification Model
# ---------------------------------------------------------------------------

class FailureClassification(BaseModel):
    """Represents a classified failure in generated automation."""
    
    # Identification
    failure_id: str = Field(..., description="Unique failure ID")
    automation_id: str = Field(..., description="Failed automation ID")
    
    # Classification
    failure_type: FailureType = Field(..., description="Type of failure")
    severity: str = Field(default="medium", description="Failure severity")
    
    # Details
    error_message: str = Field(default="", description="Error message")
    stack_trace: str = Field(default="", description="Stack trace")
    
    # Root cause
    root_cause: str = Field(default="", description="Root cause analysis")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting evidence")
    
    # Impact
    impact: str = Field(default="", description="Failure impact")
    
    # Responsibility
    phoenix_responsibility: bool = Field(default=False, description="Phoenix responsibility")
    application_responsibility: bool = Field(default=False, description="Application responsibility")
    
    # Resolution
    recommended_action: str = Field(default="", description="Recommended action")
    healing_attempted: bool = Field(default=False, description="Whether healing was attempted")
    healing_successful: bool = Field(default=False, description="Whether healing succeeded")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Automation Metrics Model
# ---------------------------------------------------------------------------

class AutomationMetrics(BaseModel):
    """Aggregate metrics for automation generation."""
    
    # Planning
    total_plans: int = Field(default=0, description="Total automation plans")
    successful_plans: int = Field(default=0, description="Successful plans")
    failed_plans: int = Field(default=0, description="Failed plans")
    
    # Generation
    total_generated: int = Field(default=0, description="Total generated automations")
    validated_automations: int = Field(default=0, description="Validated automations")
    rejected_automations: int = Field(default=0, description="Rejected automations")
    duplicate_automations: int = Field(default=0, description="Duplicate automations")
    
    # Execution
    executed_automations: int = Field(default=0, description="Executed automations")
    passed_automations: int = Field(default=0, description="Passed automations")
    failed_automations: int = Field(default=0, description="Failed automations")
    blocked_automations: int = Field(default=0, description="Blocked automations")
    
    # Locator intelligence
    locator_reuse_count: int = Field(default=0, description="Locator reuse count")
    locator_fallback_count: int = Field(default=0, description="Locator fallback count")
    
    # Healing
    healing_attempts: int = Field(default=0, description="Healing attempts")
    healing_successes: int = Field(default=0, description="Healing successes")
    
    # Cache
    dom_cache_hits: int = Field(default=0, description="DOM cache hits")
    dom_cache_misses: int = Field(default=0, description="DOM cache misses")
    
    # Intelligence
    semantic_decisions: int = Field(default=0, description="Semantic decisions")
    component_decisions: int = Field(default=0, description="Component decisions")
    flow_decisions: int = Field(default=0, description="Flow decisions")
    scenario_decisions: int = Field(default=0, description="Scenario decisions")
    ai_decisions: int = Field(default=0, description="AI decisions")
    
    # Learning
    runtime_learning_updates: int = Field(default=0, description="Runtime learning updates")
    
    # Performance
    total_execution_time_ms: float = Field(default=0.0, description="Total execution time")
    average_execution_time_ms: float = Field(default=0.0, description="Average execution time")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
