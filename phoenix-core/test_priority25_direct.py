"""Direct test of Priority 25 execution intelligence without full Phoenix imports."""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import execution intelligence modules directly
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

print("Priority 25 Execution Intelligence - Direct Module Test")
print("=" * 60)

# Test 1: Models
print("\n1. Testing Models...")
try:
    assert ExecutionState.INITIALIZING == "initializing"
    assert ExecutionPhase.PRE_EXECUTION == "pre_execution"
    assert RecoveryLevel.LOCATOR_RECOVERY == "locator_recovery"
    print("[PASS] All model enums imported successfully")
except Exception as e:
    print(f"[FAIL] Model test failed: {e}")

# Test 2: Orchestrator
print("\n2. Testing Universal Execution Orchestrator...")
try:
    orchestrator = UniversalExecutionOrchestrator()
    print("[PASS] UniversalExecutionOrchestrator initialized")
except Exception as e:
    print(f"[FAIL] UniversalExecutionOrchestrator failed: {e}")

# Test 3: Pre-Execution Validator
print("\n3. Testing Pre-Execution Validator...")
try:
    validator = PreExecutionValidator()
    print("[PASS] PreExecutionValidator initialized")
except Exception as e:
    print(f"[FAIL] PreExecutionValidator failed: {e}")

# Test 4: Action Intelligence
print("\n4. Testing Action Intelligence...")
try:
    action_intel = ActionIntelligence()
    print("[PASS] ActionIntelligence initialized")
except Exception as e:
    print(f"[FAIL] ActionIntelligence failed: {e}")

# Test 5: Enhanced Failure Classifier
print("\n5. Testing Enhanced Failure Classifier...")
try:
    failure_classifier = EnhancedFailureClassifier()
    print("[PASS] EnhancedFailureClassifier initialized")
except Exception as e:
    print(f"[FAIL] EnhancedFailureClassifier failed: {e}")

# Test 6: Multi-Level Recovery
print("\n6. Testing Multi-Level Recovery...")
try:
    recovery = MultiLevelRecovery()
    print("[PASS] MultiLevelRecovery initialized")
except Exception as e:
    print(f"[FAIL] MultiLevelRecovery failed: {e}")

# Test 7: State Machine
print("\n7. Testing Execution State Machine...")
try:
    state_machine = ExecutionStateMachine()
    print("[PASS] ExecutionStateMachine initialized")
except Exception as e:
    print(f"[FAIL] ExecutionStateMachine failed: {e}")

# Test 8: Smart Retry Policy
print("\n8. Testing Smart Retry Policy...")
try:
    retry_policy = SmartRetryPolicy()
    print("[PASS] SmartRetryPolicy initialized")
except Exception as e:
    print(f"[FAIL] SmartRetryPolicy failed: {e}")

# Test 9: Regression Detector
print("\n9. Testing Runtime Regression Detector...")
try:
    regression_detector = RuntimeRegressionDetector()
    print("[PASS] RuntimeRegressionDetector initialized")
except Exception as e:
    print(f"[FAIL] RuntimeRegressionDetector failed: {e}")

# Test 10: Scorer
print("\n10. Testing Execution Intelligence Scorer...")
try:
    scorer = ExecutionIntelligenceScorer()
    print("[PASS] ExecutionIntelligenceScorer initialized")
except Exception as e:
    print(f"[FAIL] ExecutionIntelligenceScorer failed: {e}")

# Test 11: Reporter
print("\n11. Testing Enterprise Execution Reporter...")
try:
    reporter = EnterpriseExecutionReporter()
    print("[PASS] EnterpriseExecutionReporter initialized")
except Exception as e:
    print(f"[FAIL] EnterpriseExecutionReporter failed: {e}")

# Test 12: Action Intelligence Functionality
print("\n12. Testing Action Intelligence Functionality...")
try:
    action_intel = ActionIntelligence()
    evidence = action_intel.create_action_evidence(
        action_id="ACT-001",
        action_type="click",
        semantic_intent="Submit form",
        component_purpose="Submit button",
        locator='get_by_role("button")',
        locator_confidence=0.95,
    )
    action_intel.record_action_result(
        action_id="ACT-001",
        actual_outcome="Form submitted",
        result="success",
        duration_ms=500,
    )
    summary = action_intel.get_action_summary()
    assert summary["total_actions"] == 1
    assert summary["successful_actions"] == 1
    print("[PASS] Action Intelligence functionality works")
except Exception as e:
    print(f"[FAIL] Action Intelligence functionality failed: {e}")

# Test 13: Failure Classification Functionality
print("\n13. Testing Failure Classification Functionality...")
try:
    classifier = EnhancedFailureClassifier()
    classification = classifier.classify_failure(
        "Element not found: timeout",
        context={"component": "submit_button"},
    )
    assert classification["failure_type"] == "locator_failure"
    assert classification["phoenix_responsibility"] == True
    print("[PASS] Failure Classification functionality works")
except Exception as e:
    print(f"[FAIL] Failure Classification functionality failed: {e}")

# Test 14: State Machine Functionality
print("\n14. Testing State Machine Functionality...")
try:
    machine = ExecutionStateMachine()
    success = machine.transition_to(
        ExecutionState.BROWSER_STARTED,
        reason="Browser launched"
    )
    assert success == True
    assert machine.current_state == ExecutionState.BROWSER_STARTED
    print("[PASS] State Machine functionality works")
except Exception as e:
    print(f"[FAIL] State Machine functionality failed: {e}")

# Test 15: Retry Policy Functionality
print("\n15. Testing Retry Policy Functionality...")
try:
    policy = SmartRetryPolicy()
    classification = {
        "failure_type": "locator_failure",
        "recoverability": "HIGH",
        "phoenix_responsibility": True,
    }
    decision = policy.should_retry(classification, {"failure_count": 0})
    assert decision.should_retry == True
    print("[PASS] Retry Policy functionality works")
except Exception as e:
    print(f"[FAIL] Retry Policy functionality failed: {e}")

# Test 16: Regression Detection Functionality
print("\n16. Testing Regression Detection Functionality...")
try:
    detector = RuntimeRegressionDetector()
    current = {"execution_id": "EXEC-002"}
    regression = detector.detect_regression(current, None)
    assert regression is None  # No previous execution
    print("[PASS] Regression Detection functionality works")
except Exception as e:
    print(f"[FAIL] Regression Detection functionality failed: {e}")

# Test 17: Scoring Functionality
print("\n17. Testing Scoring Functionality...")
try:
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
    print("[PASS] Scoring functionality works")
except Exception as e:
    print(f"[FAIL] Scoring functionality failed: {e}")

# Test 18: Reporting Functionality
print("\n18. Testing Reporting Functionality...")
try:
    reporter = EnterpriseExecutionReporter()
    report = reporter.generate_report(
        execution_id="EXEC-001",
        automation_id="AUTO-001",
        test_name="test_login",
        project_name="test_project",
        status="PASSED",
    )
    assert report.execution_id == "EXEC-001"
    assert report.status == "PASSED"
    print("[PASS] Reporting functionality works")
except Exception as e:
    print(f"[FAIL] Reporting functionality failed: {e}")

print("\n" + "=" * 60)
print("Priority 25 Direct Module Test Complete")
print("=" * 60)
