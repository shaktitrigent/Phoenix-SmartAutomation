"""Unit Tests for Priority 25 - Universal Autonomous Execution Intelligence.

This test suite verifies all Priority 25 components work correctly without
application-specific knowledge.

Priority 25: Universal Autonomous Execution Intelligence
"""

import pytest
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import (
    ExecutionState,
    ExecutionPhase,
    RecoveryLevel,
    ActionExecutionEvidence,
    PreExecutionValidation,
    SmartRetryDecision,
    RuntimeRegression,
    ExecutionIntelligenceScore,
    EnterpriseExecutionReport,
    HealingAttempt,
    HealingSession,
)

from phoenix.execution_intelligence.orchestrator import UniversalExecutionOrchestrator
from phoenix.execution_intelligence.pre_execution import PreExecutionValidator
from phoenix.execution_intelligence.action_intelligence import ActionIntelligence
from phoenix.execution_intelligence.failure_intelligence import (
    EnhancedFailureClassifier,
    EnhancedFailureType,
)
from phoenix.execution_intelligence.recovery import MultiLevelRecovery
from phoenix.execution_intelligence.state_machine import ExecutionStateMachine
from phoenix.execution_intelligence.retry_policy import SmartRetryPolicy
from phoenix.execution_intelligence.regression_detection import RuntimeRegressionDetector
from phoenix.execution_intelligence.scoring import ExecutionIntelligenceScorer
from phoenix.execution_intelligence.reporting import EnterpriseExecutionReporter


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

def test_execution_state_enum():
    """Test ExecutionState enum values."""
    assert ExecutionState.INITIALIZING == "initializing"
    assert ExecutionState.BROWSER_STARTED == "browser_started"
    assert ExecutionState.ACTION_EXECUTING == "action_executing"
    assert ExecutionState.FAILURE == "failure"
    assert ExecutionState.HEALING == "healing"


def test_execution_phase_enum():
    """Test ExecutionPhase enum values."""
    assert ExecutionPhase.PRE_EXECUTION == "pre_execution"
    assert ExecutionPhase.ACTION_EXECUTION == "action_execution"
    assert ExecutionPhase.HEALING == "healing"
    assert ExecutionPhase.REPORTING == "reporting"


def test_recovery_level_enum():
    """Test RecoveryLevel enum values."""
    assert RecoveryLevel.LOCATOR_RECOVERY == "locator_recovery"
    assert RecoveryLevel.DOM_RECOVERY == "dom_recovery"
    assert RecoveryLevel.SEMANTIC_RECOVERY == "semantic_recovery"
    assert RecoveryLevel.FULL_REGENERATION == "full_regeneration"


def test_action_execution_evidence_creation():
    """Test ActionExecutionEvidence model creation."""
    evidence = ActionExecutionEvidence(
        action_id="ACT-001",
        action_type="click",
        semantic_intent="Submit form",
        component_purpose="Submit button",
        locator='get_by_role("button", name="Submit")',
        locator_strategy="role",
        locator_confidence=0.95,
        expected_outcome="Form submitted",
    )
    
    assert evidence.action_id == "ACT-001"
    assert evidence.action_type == "click"
    assert evidence.semantic_intent == "Submit form"
    assert evidence.locator_confidence == 0.95


def test_pre_execution_validation_creation():
    """Test PreExecutionValidation model creation."""
    validation = PreExecutionValidation(
        validation_id="VAL-001",
        automation_id="AUTO-001",
        overall_valid=True,
        confidence=0.85,
    )
    
    assert validation.validation_id == "VAL-001"
    assert validation.automation_id == "AUTO-001"
    assert validation.overall_valid == True
    assert validation.confidence == 0.85


def test_smart_retry_decision_creation():
    """Test SmartRetryDecision model creation."""
    decision = SmartRetryDecision(
        decision_id="RETRY-001",
        should_retry=True,
        reason="Transient failure",
        confidence=0.87,
    )
    
    assert decision.decision_id == "RETRY-001"
    assert decision.should_retry == True
    assert decision.reason == "Transient failure"
    assert decision.confidence == 0.87


def test_runtime_regression_creation():
    """Test RuntimeRegression model creation."""
    regression = RuntimeRegression(
        regression_id="REG-001",
        previous_execution_id="EXEC-001",
        current_execution_id="EXEC-002",
        regression_type="DETECTED",
        locator_degradation=True,
    )
    
    assert regression.regression_id == "REG-001"
    assert regression.previous_execution_id == "EXEC-001"
    assert regression.current_execution_id == "EXEC-002"
    assert regression.locator_degradation == True


def test_execution_intelligence_score_creation():
    """Test ExecutionIntelligenceScore model creation."""
    score = ExecutionIntelligenceScore(
        score_id="SCORE-001",
        execution_id="EXEC-001",
        locator_confidence=85.0,
        dom_confidence=90.0,
        overall_score=87.5,
    )
    
    assert score.score_id == "SCORE-001"
    assert score.execution_id == "EXEC-001"
    assert score.locator_confidence == 85.0
    assert score.overall_score == 87.5


def test_enterprise_execution_report_creation():
    """Test EnterpriseExecutionReport model creation."""
    report = EnterpriseExecutionReport(
        report_id="REPORT-001",
        execution_id="EXEC-001",
        project_name="test_project",
        test_name="test_login",
        status="PASSED",
    )
    
    assert report.report_id == "REPORT-001"
    assert report.execution_id == "EXEC-001"
    assert report.project_name == "test_project"
    assert report.status == "PASSED"


# ---------------------------------------------------------------------------
# Orchestrator Tests
# ---------------------------------------------------------------------------

def test_orchestrator_initialization():
    """Test UniversalExecutionOrchestrator initialization."""
    orchestrator = UniversalExecutionOrchestrator()
    
    assert orchestrator is not None
    assert orchestrator.current_state == ExecutionState.INITIALIZING
    assert orchestrator.current_phase == ExecutionPhase.PRE_EXECUTION


def test_orchestrator_state_update():
    """Test state update in orchestrator."""
    orchestrator = UniversalExecutionOrchestrator()
    
    orchestrator.update_state(ExecutionState.BROWSER_STARTED)
    
    assert orchestrator.current_state == ExecutionState.BROWSER_STARTED


# ---------------------------------------------------------------------------
# Pre-Execution Validator Tests
# ---------------------------------------------------------------------------

def test_pre_execution_validator_initialization():
    """Test PreExecutionValidator initialization."""
    validator = PreExecutionValidator()
    
    assert validator is not None


def test_pre_execution_validator_valid_script():
    """Test validation of valid script."""
    validator = PreExecutionValidator()
    
    script = '''
def test_login(page):
    page.goto("https://example.com")
    page.fill("username", "test")
    page.click("button")
    expect(page).to_have_title("Dashboard")
'''
    
    validation = validator.validate(script, "AUTO-001")
    
    assert validation.validation_id is not None
    assert validation.automation_id == "AUTO-001"


def test_pre_execution_validator_invalid_script():
    """Test validation of invalid script."""
    validator = PreExecutionValidator()
    
    script = "invalid python code"
    
    validation = validator.validate(script, "AUTO-001")
    
    assert validation.overall_valid == False
    assert len(validation.blocking_issues) > 0


# ---------------------------------------------------------------------------
# Action Intelligence Tests
# ---------------------------------------------------------------------------

def test_action_intelligence_initialization():
    """Test ActionIntelligence initialization."""
    intelligence = ActionIntelligence()
    
    assert intelligence is not None
    assert len(intelligence.action_history) == 0


def test_action_intelligence_create_evidence():
    """Test creating action evidence."""
    intelligence = ActionIntelligence()
    
    evidence = intelligence.create_action_evidence(
        action_id="ACT-001",
        action_type="click",
        semantic_intent="Submit form",
        component_purpose="Submit button",
        locator='get_by_role("button")',
        locator_confidence=0.95,
    )
    
    assert evidence.action_id == "ACT-001"
    assert evidence.semantic_intent == "Submit form"
    assert len(intelligence.action_history) == 1


def test_action_intelligence_record_result():
    """Test recording action result."""
    intelligence = ActionIntelligence()
    
    intelligence.create_action_evidence(
        action_id="ACT-001",
        action_type="click",
        semantic_intent="Submit form",
    )
    
    intelligence.record_action_result(
        action_id="ACT-001",
        actual_outcome="Form submitted",
        result="success",
        duration_ms=500,
    )
    
    evidence = intelligence.get_action_evidence("ACT-001")
    assert evidence.actual_outcome == "Form submitted"
    assert evidence.result == "success"
    assert evidence.duration_ms == 500


def test_action_intelligence_get_summary():
    """Test getting action summary."""
    intelligence = ActionIntelligence()
    
    intelligence.create_action_evidence(
        action_id="ACT-001",
        action_type="click",
        semantic_intent="Submit form",
    )
    intelligence.record_action_result(
        action_id="ACT-001",
        actual_outcome="Form submitted",
        result="success",
        duration_ms=500,
    )
    
    summary = intelligence.get_action_summary()
    
    assert summary["total_actions"] == 1
    assert summary["successful_actions"] == 1
    assert summary["failed_actions"] == 0


# ---------------------------------------------------------------------------
# Failure Intelligence Tests
# ---------------------------------------------------------------------------

def test_enhanced_failure_classifier_initialization():
    """Test EnhancedFailureClassifier initialization."""
    classifier = EnhancedFailureClassifier()
    
    assert classifier is not None


def test_enhanced_failure_classifier_locator_failure():
    """Test classifying locator failure."""
    classifier = EnhancedFailureClassifier()
    
    classification = classifier.classify_failure(
        "Element not found: timeout",
        context={"component": "submit_button"},
    )
    
    assert classification["failure_type"] == "locator_failure"
    assert classification["phoenix_responsibility"] == True


def test_enhanced_failure_classifier_navigation_failure():
    """Test classifying navigation failure."""
    classifier = EnhancedFailureClassifier()
    
    classification = classifier.classify_failure(
        "Navigation timeout exceeded",
        context={"url": "https://example.com"},
    )
    
    assert classification["failure_type"] == "navigation_failure"


def test_enhanced_failure_classifier_application_failure():
    """Test classifying application failure."""
    classifier = EnhancedFailureClassifier()
    
    classification = classifier.classify_failure(
        "HTTP 500 Internal Server Error",
        context={"http_status": 500},
    )
    
    assert classification["failure_type"] == "application_failure"
    assert classification["application_responsibility"] == True


# ---------------------------------------------------------------------------
# Recovery Tests
# ---------------------------------------------------------------------------

def test_multi_level_recovery_initialization():
    """Test MultiLevelRecovery initialization."""
    recovery = MultiLevelRecovery()
    
    assert recovery is not None


def test_multi_level_recovery_attempt_recovery():
    """Test recovery attempt."""
    recovery = MultiLevelRecovery()
    
    classification = {
        "failure_type": "locator_failure",
        "recoverability": "HIGH",
        "phoenix_responsibility": True,
    }
    
    session = recovery.attempt_recovery(
        "FAIL-001",
        classification,
        {"locator": "submit_button"},
    )
    
    assert session.session_id is not None
    assert session.failure_id == "FAIL-001"
    assert session.total_attempts > 0


# ---------------------------------------------------------------------------
# State Machine Tests
# ---------------------------------------------------------------------------

def test_state_machine_initialization():
    """Test ExecutionStateMachine initialization."""
    machine = ExecutionStateMachine()
    
    assert machine is not None
    assert machine.current_state == ExecutionState.INITIALIZING


def test_state_machine_valid_transition():
    """Test valid state transition."""
    machine = ExecutionStateMachine()
    
    success = machine.transition_to(
        ExecutionState.BROWSER_STARTED,
        reason="Browser launched successfully"
    )
    
    assert success == True
    assert machine.current_state == ExecutionState.BROWSER_STARTED


def test_state_machine_invalid_transition():
    """Test invalid state transition."""
    machine = ExecutionStateMachine()
    
    # Try invalid transition
    success = machine.transition_to(
        ExecutionState.TEST_COMPLETED,
        reason="Invalid transition"
    )
    
    assert success == False
    assert machine.current_state == ExecutionState.INITIALIZING


def test_state_machine_failure_path():
    """Test failure path detection."""
    machine = ExecutionStateMachine()
    
    # Follow valid transition path to failure
    machine.transition_to(ExecutionState.BROWSER_STARTED, reason="Browser started")
    machine.transition_to(ExecutionState.PAGE_LOADING, reason="Page loading")
    machine.transition_to(ExecutionState.FAILURE, reason="Test failed")
    
    assert machine.is_in_failure_path() == True


# ---------------------------------------------------------------------------
# Retry Policy Tests
# ---------------------------------------------------------------------------

def test_smart_retry_policy_initialization():
    """Test SmartRetryPolicy initialization."""
    policy = SmartRetryPolicy()
    
    assert policy is not None
    assert policy.max_retries == 3


def test_smart_retry_policy_retryable_failure():
    """Test retry decision for retryable failure."""
    policy = SmartRetryPolicy()
    
    classification = {
        "failure_type": "locator_failure",
        "recoverability": "HIGH",
        "phoenix_responsibility": True,
    }
    
    decision = policy.should_retry(classification, {"failure_count": 0})
    
    assert decision.should_retry == True
    assert decision.reason != ""


def test_smart_retry_policy_non_retryable_failure():
    """Test retry decision for non-retryable failure."""
    policy = SmartRetryPolicy()
    
    classification = {
        "failure_type": "test_data_failure",
        "recoverability": "LOW",
        "phoenix_responsibility": False,
    }
    
    decision = policy.should_retry(classification, {"failure_count": 0})
    
    assert decision.should_retry == False


def test_smart_retry_policy_max_retries_exceeded():
    """Test retry decision when max retries exceeded."""
    policy = SmartRetryPolicy(max_retries=3)
    
    classification = {
        "failure_type": "locator_failure",
        "recoverability": "HIGH",
        "phoenix_responsibility": True,
    }
    
    decision = policy.should_retry(classification, {"failure_count": 5})
    
    assert decision.should_retry == False
    assert "max retries" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Regression Detection Tests
# ---------------------------------------------------------------------------

def test_regression_detector_initialization():
    """Test RuntimeRegressionDetector initialization."""
    detector = RuntimeRegressionDetector()
    
    assert detector is not None


def test_regression_detector_no_previous():
    """Test regression detection with no previous execution."""
    detector = RuntimeRegressionDetector()
    
    current = {"execution_id": "EXEC-002"}
    
    regression = detector.detect_regression(current, None)
    
    assert regression is None


def test_regression_detector_no_regression():
    """Test regression detection with no regression."""
    detector = RuntimeRegressionDetector()
    
    previous = {
        "execution_id": "EXEC-001",
        "locators": {"btn1": {"success_rate": 0.95}},
        "dom_hash": "abc123",
        "execution_time_ms": 1000,
        "healing_count": 0,
    }
    
    current = {
        "execution_id": "EXEC-002",
        "locators": {"btn1": {"success_rate": 0.94}},
        "dom_hash": "abc123",
        "execution_time_ms": 1050,
        "healing_count": 0,
    }
    
    regression = detector.detect_regression(current, previous)
    
    assert regression is None


def test_regression_detector_locator_regression():
    """Test regression detection for locator degradation."""
    detector = RuntimeRegressionDetector()
    
    previous = {
        "execution_id": "EXEC-001",
        "locators": {"btn1": {"success_rate": 0.95}},
        "dom_hash": "abc123",
        "execution_time_ms": 1000,
        "healing_count": 0,
    }
    
    current = {
        "execution_id": "EXEC-002",
        "locators": {"btn1": {"success_rate": 0.60}},  # Degraded
        "dom_hash": "abc123",
        "execution_time_ms": 1000,
        "healing_count": 0,
    }
    
    regression = detector.detect_regression(current, previous)
    
    assert regression is not None
    assert regression.locator_degradation == True


# ---------------------------------------------------------------------------
# Scoring Tests
# ---------------------------------------------------------------------------

def test_scorer_initialization():
    """Test ExecutionIntelligenceScorer initialization."""
    scorer = ExecutionIntelligenceScorer()
    
    assert scorer is not None


def test_scorer_calculate_score():
    """Test score calculation."""
    scorer = ExecutionIntelligenceScorer()
    
    evidence = {
        "locators": {"btn1": {"confidence": 0.9}},
        "dom_cache_hits": 8,
        "dom_cache_misses": 2,
        "semantic_pages": {"page1": {"confidence": 0.85}},
        "flows": {"flow1": {"confidence": 0.8}},
        "actions": {"act1": {"result": "success"}},
        "assertions": {"assert1": {"result": "success"}},
        "execution_times": [1000, 1050, 1020],
        "healing_attempts": 0,
        "healing_successes": 0,
    }
    
    score = scorer.calculate_score("EXEC-001", evidence)
    
    assert score.execution_id == "EXEC-001"
    assert score.overall_score > 0
    assert score.overall_score <= 100


# ---------------------------------------------------------------------------
# Reporting Tests
# ---------------------------------------------------------------------------

def test_reporter_initialization():
    """Test EnterpriseExecutionReporter initialization."""
    reporter = EnterpriseExecutionReporter()
    
    assert reporter is not None


def test_reporter_generate_report():
    """Test report generation."""
    reporter = EnterpriseExecutionReporter()
    
    report = reporter.generate_report(
        execution_id="EXEC-001",
        automation_id="AUTO-001",
        test_name="test_login",
        project_name="test_project",
        status="PASSED",
    )
    
    assert report.report_id is not None
    assert report.execution_id == "EXEC-001"
    assert report.status == "PASSED"
    assert report.total_tests == 1
    assert report.passed_tests == 1


# ---------------------------------------------------------------------------
# Application-Agnostic Tests
# ---------------------------------------------------------------------------

def test_no_orangehrm_in_models():
    """Verify no orangehrm references in models."""
    import phoenix.execution_intelligence.models as models_module
    
    source = open(models_module.__file__, 'r').read().lower()
    
    assert "orangehrm" not in source
    assert "jira" not in source
    assert "salesforce" not in source


def test_no_orangehrm_in_orchestrator():
    """Verify no orangehrm references in orchestrator."""
    import phoenix.execution_intelligence.orchestrator as orchestrator_module
    
    source = open(orchestrator_module.__file__, 'r').read().lower()
    
    assert "orangehrm" not in source
    assert "jira" not in source
    assert "salesforce" not in source


def test_no_orangehrm_in_pre_execution():
    """Verify no orangehrm references in pre_execution."""
    import phoenix.execution_intelligence.pre_execution as pre_exec_module
    
    source = open(pre_exec_module.__file__, 'r').read().lower()
    
    assert "orangehrm" not in source
    assert "jira" not in source
    assert "salesforce" not in source


def test_no_orangehrm_in_failure_intelligence():
    """Verify no orangehrm references in failure intelligence."""
    import phoenix.execution_intelligence.failure_intelligence as failure_module
    
    source = open(failure_module.__file__, 'r').read().lower()
    
    assert "orangehrm" not in source
    assert "jira" not in source
    assert "salesforce" not in source


def test_no_hardcoded_urls():
    """Verify no hardcoded application URLs."""
    import phoenix.execution_intelligence as exec_intel_module
    
    source = open(exec_intel_module.__file__, 'r').read().lower()
    
    assert "orangehrm.com" not in source
    assert "atlassian.net" not in source
    assert "salesforce.com" not in source
