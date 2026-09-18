"""Priority 25 Execution Intelligence Models.

Universal autonomous execution intelligence data structures.
Completely application-agnostic.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution State Machine
# ---------------------------------------------------------------------------

class ExecutionState(str, Enum):
    """States in the execution lifecycle."""
    
    INITIALIZING = "initializing"
    BROWSER_STARTED = "browser_started"
    PAGE_LOADING = "page_loading"
    PAGE_ANALYZED = "page_analyzed"
    ACTION_EXECUTING = "action_executing"
    ACTION_VERIFIED = "action_verified"
    NEXT_ACTION = "next_action"
    FAILURE = "failure"
    DIAGNOSING = "diagnosing"
    HEALING = "healing"
    RETRYING = "retrying"
    VERIFYING = "verifying"
    RECOVERED = "recovered"
    REGENERATING = "regenerating"
    TEST_COMPLETED = "test_completed"
    ABORTED = "aborted"


class ExecutionPhase(str, Enum):
    """High-level execution phases."""
    
    PRE_EXECUTION = "pre_execution"
    BROWSER_LAUNCH = "browser_launch"
    PAGE_NAVIGATION = "page_navigation"
    SEMANTIC_ANALYSIS = "semantic_analysis"
    ACTION_EXECUTION = "action_execution"
    ASSERTION_VERIFICATION = "assertion_verification"
    FAILURE_HANDLING = "failure_handling"
    HEALING = "healing"
    POST_EXECUTION = "post_execution"
    LEARNING = "learning"
    REPORTING = "reporting"


# ---------------------------------------------------------------------------
# Recovery Levels
# ---------------------------------------------------------------------------

class RecoveryLevel(str, Enum):
    """Levels of recovery for handling failures."""
    
    LOCATOR_RECOVERY = "locator_recovery"  # Try known successful alternatives
    DOM_RECOVERY = "dom_recovery"  # Re-observe current DOM
    SEMANTIC_RECOVERY = "semantic_recovery"  # Re-identify using Priority 22
    FLOW_RECOVERY = "flow_recovery"  # Use Priority 21 flow knowledge
    ACTION_RECOVERY = "action_recovery"  # Regenerate failed action
    TEST_RECOVERY = "test_recovery"  # Regenerate affected portion
    FULL_REGENERATION = "full_regeneration"  # Last resort


# ---------------------------------------------------------------------------
# Execution Intelligence Models
# ---------------------------------------------------------------------------

class ActionExecutionEvidence(BaseModel):
    """Evidence for a single action execution."""
    
    action_id: str = Field(..., description="Action identifier")
    action_type: str = Field(..., description="Type of action")
    
    # Intent
    semantic_intent: str = Field(default="", description="Semantic intent of action")
    component_purpose: str = Field(default="", description="Purpose of target component")
    
    # Component
    component_id: str = Field(default="", description="Target component ID")
    component_type: str = Field(default="", description="Component type")
    
    # Locator
    locator: str = Field(default="", description="Locator used")
    locator_strategy: str = Field(default="", description="Locator strategy")
    locator_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Locator confidence")
    
    # Input
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data")
    
    # Expected
    expected_outcome: str = Field(default="", description="Expected outcome")
    
    # Actual
    actual_outcome: str = Field(default="", description="Actual outcome")
    result: str = Field(default="", description="Result: success/failure")
    
    # Timing
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = Field(default=None)
    duration_ms: float = Field(default=0.0)
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    
    # Context
    page_url: str = Field(default="")
    page_type: str = Field(default="")
    dom_snapshot_ref: Optional[str] = Field(default=None)
    screenshot_ref: Optional[str] = Field(default=None)


class PreExecutionValidation(BaseModel):
    """Validation results before execution."""
    
    validation_id: str = Field(..., description="Validation identifier")
    automation_id: str = Field(..., description="Automation being validated")
    
    # Test Validation
    test_structure_valid: bool = Field(default=True)
    required_actions_valid: bool = Field(default=True)
    required_assertions_valid: bool = Field(default=True)
    required_test_data_valid: bool = Field(default=True)
    
    # Locator Validation
    locator_exists: bool = Field(default=True)
    locator_confidence_sufficient: bool = Field(default=True)
    locator_unique: bool = Field(default=True)
    locator_stable: bool = Field(default=True)
    alternative_locators_available: bool = Field(default=True)
    
    # Test Data Validation
    required_env_vars_set: bool = Field(default=True)
    required_credentials_available: bool = Field(default=True)
    required_input_data_available: bool = Field(default=True)
    sensitive_data_protected: bool = Field(default=True)
    
    # Environment Validation
    browser_config_valid: bool = Field(default=True)
    url_accessible: bool = Field(default=True)
    environment_config_valid: bool = Field(default=True)
    
    # Overall
    overall_valid: bool = Field(default=True)
    blocking_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SmartRetryDecision(BaseModel):
    """Decision for retrying failed execution."""
    
    decision_id: str = Field(..., description="Decision identifier")
    should_retry: bool = Field(..., description="Whether to retry")
    
    # Reasoning
    reason: str = Field(..., description="Reason for decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    
    # Context
    failure_type: str = Field(default="")
    failure_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    
    # Strategy
    retry_strategy: str = Field(default="immediate")
    retry_delay_ms: int = Field(default=1000)
    backoff_multiplier: float = Field(default=2.0)
    
    # Evidence
    evidence: List[str] = Field(default_factory=list)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeRegression(BaseModel):
    """Detected regression between executions."""
    
    regression_id: str = Field(..., description="Regression identifier")
    
    # Comparison
    previous_execution_id: str = Field(..., description="Previous execution")
    current_execution_id: str = Field(..., description="Current execution")
    
    # Regression Type
    regression_type: str = Field(..., description="Type of regression")
    
    # Details
    locator_degradation: bool = Field(default=False)
    page_structure_changed: bool = Field(default=False)
    flow_changed: bool = Field(default=False)
    component_changed: bool = Field(default=False)
    unexpected_navigation: bool = Field(default=False)
    increased_execution_time: bool = Field(default=False)
    increased_healing: bool = Field(default=False)
    increased_failures: bool = Field(default=False)
    
    # Metrics
    previous_success_rate: float = Field(default=0.0)
    current_success_rate: float = Field(default=0.0)
    degradation_percentage: float = Field(default=0.0)
    
    # Specifics
    affected_locator: str = Field(default="")
    affected_component: str = Field(default="")
    affected_flow: str = Field(default="")
    
    # Recommendation
    recommended_action: str = Field(default="")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Evidence
    evidence: List[str] = Field(default_factory=list)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionIntelligenceScore(BaseModel):
    """Evidence-based execution intelligence score."""
    
    score_id: str = Field(..., description="Score identifier")
    execution_id: str = Field(..., description="Execution being scored")
    
    # Component Scores (0-100)
    locator_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    dom_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    semantic_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    flow_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    action_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    assertion_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    runtime_stability: float = Field(default=0.0, ge=0.0, le=100.0)
    healing_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Overall Score
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Evidence
    score_evidence: Dict[str, Any] = Field(default_factory=dict)
    calculation_method: str = Field(default="weighted_average")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EnterpriseExecutionReport(BaseModel):
    """Enterprise execution report with comprehensive metrics."""
    
    report_id: str = Field(..., description="Report identifier")
    execution_id: str = Field(..., description="Execution ID")
    project_name: str = Field(..., description="Project name")
    test_name: str = Field(..., description="Test name")
    
    # Executive Summary
    status: str = Field(..., description="Overall status")
    total_duration_ms: float = Field(default=0.0)
    recovery_status: str = Field(default="")
    
    # Test Statistics
    total_tests: int = Field(default=0)
    passed_tests: int = Field(default=0)
    failed_tests: int = Field(default=0)
    recovered_tests: int = Field(default=0)
    skipped_tests: int = Field(default=0)
    
    # Step Statistics
    total_actions: int = Field(default=0)
    successful_actions: int = Field(default=0)
    failed_actions: int = Field(default=0)
    healed_actions: int = Field(default=0)
    
    # Locator Statistics
    total_locators: int = Field(default=0)
    successful_locators: int = Field(default=0)
    failed_locators: int = Field(default=0)
    average_locator_confidence: float = Field(default=0.0)
    
    # Healing Statistics
    healing_attempts: int = Field(default=0)
    healing_recoveries: int = Field(default=0)
    healing_failures: int = Field(default=0)
    healing_success_rate: float = Field(default=0.0)
    
    # Runtime Statistics
    execution_time_ms: float = Field(default=0.0)
    time_saved_ms: float = Field(default=0.0)
    dom_reuse_count: int = Field(default=0)
    locator_reuse_count: int = Field(default=0)
    mcp_calls_saved: int = Field(default=0)
    
    # Intelligence Statistics
    semantic_confidence: float = Field(default=0.0)
    flow_confidence: float = Field(default=0.0)
    execution_confidence: float = Field(default=0.0)
    healing_confidence: float = Field(default=0.0)
    
    # Regression Detection
    regressions_detected: List[RuntimeRegression] = Field(default_factory=list)
    
    # Runtime Learning
    locator_learning_updates: int = Field(default=0)
    component_learning_updates: int = Field(default=0)
    flow_learning_updates: int = Field(default=0)
    healing_learning_updates: int = Field(default=0)
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)
    
    # Evidence
    execution_evidence: Dict[str, Any] = Field(default_factory=dict)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Healing Integration Models
# ---------------------------------------------------------------------------

class HealingAttempt(BaseModel):
    """Record of a healing attempt."""
    
    attempt_id: str = Field(..., description="Attempt identifier")
    recovery_level: RecoveryLevel = Field(..., description="Recovery level used")
    
    # Original
    original_locator: str = Field(default="")
    original_confidence: float = Field(default=0.0)
    
    # Alternative
    alternative_locator: str = Field(default="")
    alternative_confidence: float = Field(default=0.0)
    
    # Reasoning
    reason: str = Field(..., description="Reason for healing")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Result
    attempt_number: int = Field(default=1)
    result: str = Field(..., description="Result: success/failure")
    duration_ms: float = Field(default=0.0)
    
    # Evidence
    evidence: List[str] = Field(default_factory=list)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HealingSession(BaseModel):
    """Complete healing session for a failure."""
    
    session_id: str = Field(..., description="Session identifier")
    failure_id: str = Field(..., description="Failure being healed")
    
    attempts: List[HealingAttempt] = Field(default_factory=list)
    
    # Summary
    total_attempts: int = Field(default=0)
    successful_attempt: Optional[int] = Field(default=None)
    final_result: str = Field(default="")
    
    # Statistics
    total_duration_ms: float = Field(default=0.0)
    recovery_level_achieved: Optional[RecoveryLevel] = Field(default=None)
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
