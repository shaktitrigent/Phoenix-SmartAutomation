"""Universal Execution Orchestrator - Central execution intelligence layer.

This module implements the Universal Execution Orchestrator that coordinates
all execution intelligence components for autonomous test execution.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from phoenix.execution_intelligence.models import (
    ExecutionState,
    ExecutionPhase,
    ActionExecutionEvidence,
    PreExecutionValidation,
    SmartRetryDecision,
    EnterpriseExecutionReport,
    HealingSession,
)

logger = logging.getLogger(__name__)


class UniversalExecutionOrchestrator:
    """Universal execution orchestrator for autonomous test execution.
    
    This orchestrator coordinates:
    - Pre-execution validation
    - Browser execution
    - Runtime observation
    - Failure detection
    - Failure classification
    - Healing
    - Re-execution
    - Verification
    - Learning
    - Execution result generation
    
    Works for ANY generated test without application-specific branches.
    """
    
    def __init__(
        self,
        intelligent_runtime=None,
        pre_execution_validator=None,
        action_intelligence=None,
        failure_classifier=None,
        recovery_engine=None,
        state_machine=None,
        retry_policy=None,
        regression_detector=None,
        scorer=None,
        reporter=None,
    ):
        """Initialize the universal execution orchestrator."""
        self.intelligent_runtime = intelligent_runtime
        self.pre_execution_validator = pre_execution_validator
        self.action_intelligence = action_intelligence
        self.failure_classifier = failure_classifier
        self.recovery_engine = recovery_engine
        self.state_machine = state_machine
        self.retry_policy = retry_policy
        self.regression_detector = regression_detector
        self.scorer = scorer
        self.reporter = reporter
        
        # Execution state
        self.execution_id: Optional[str] = None
        self.current_state: ExecutionState = ExecutionState.INITIALIZING
        self.current_phase: ExecutionPhase = ExecutionPhase.PRE_EXECUTION
        
        # Execution evidence
        self.action_evidence: List[ActionExecutionEvidence] = []
        self.healing_sessions: List[HealingSession] = []
        self.execution_metrics: Dict[str, Any] = {}
        
        logger.info("UniversalExecutionOrchestrator initialized")
    
    def execute_automation(
        self,
        automation_script: str,
        automation_id: str,
        test_name: str,
        project_name: str = "default",
        headed: bool = False,
        slow_mo: int = 0,
    ) -> EnterpriseExecutionReport:
        """Execute automation with full intelligence orchestration.
        
        Args:
            automation_script: Generated automation script
            automation_id: ID of the automation
            test_name: Name of the test
            project_name: Project name
            headed: Whether to use headed browser mode
            slow_mo: Slow motion delay in milliseconds
            
        Returns:
            EnterpriseExecutionReport with comprehensive results
        """
        self.execution_id = f"EXEC-{uuid.uuid4().hex[:8].upper()}"
        
        logger.info(
            f"[ORCHESTRATOR] Starting execution {self.execution_id} "
            f"for automation {automation_id}"
        )
        
        # Phase 1: Pre-Execution Validation
        self.current_phase = ExecutionPhase.PRE_EXECUTION
        pre_validation = self._validate_pre_execution(
            automation_script, automation_id
        )
        
        if not pre_validation.overall_valid:
            logger.warning(f"[ORCHESTRATOR] Pre-execution validation failed")
            return self._generate_report(
                automation_id, test_name, project_name,
                status="PRE_EXECUTION_FAILED",
                pre_validation=pre_validation,
            )
        
        # Phase 2: Browser Launch
        self.current_phase = ExecutionPhase.BROWSER_LAUNCH
        self.current_state = ExecutionState.BROWSER_STARTED
        
        # Phase 3: Page Navigation & Analysis
        self.current_phase = ExecutionPhase.PAGE_NAVIGATION
        self.current_state = ExecutionState.PAGE_LOADING
        
        # Phase 4: Semantic Analysis
        self.current_phase = ExecutionPhase.SEMANTIC_ANALYSIS
        self.current_state = ExecutionState.PAGE_ANALYZED
        
        # Phase 5: Action Execution Loop
        self.current_phase = ExecutionPhase.ACTION_EXECUTION
        
        # Execute actions with intelligence
        execution_result = self._execute_actions_with_intelligence(
            automation_script, headed, slow_mo
        )
        
        # Phase 6: Post-Execution & Learning
        self.current_phase = ExecutionPhase.POST_EXECUTION
        self.current_state = ExecutionState.TEST_COMPLETED
        
        # Phase 7: Reporting
        self.current_phase = ExecutionPhase.REPORTING
        
        report = self._generate_report(
            automation_id, test_name, project_name,
            status=execution_result.get("status", "UNKNOWN"),
            pre_validation=pre_validation,
            execution_result=execution_result,
        )
        
        logger.info(
            f"[ORCHESTRATOR] Execution {self.execution_id} completed "
            f"with status {report.status}"
        )
        
        return report
    
    def _validate_pre_execution(
        self,
        automation_script: str,
        automation_id: str,
    ) -> PreExecutionValidation:
        """Validate automation before execution."""
        if self.pre_execution_validator:
            return self.pre_execution_validator.validate(
                automation_script, automation_id
            )
        
        # Default validation
        return PreExecutionValidation(
            validation_id=f"VAL-{uuid.uuid4().hex[:8].upper()}",
            automation_id=automation_id,
            overall_valid=True,
            confidence=0.8,
        )
    
    def _execute_actions_with_intelligence(
        self,
        automation_script: str,
        headed: bool,
        slow_mo: int,
    ) -> Dict[str, Any]:
        """Execute actions with full intelligence."""
        # This would integrate with IntelligentRuntime
        # For now, return a placeholder result
        return {
            "status": "NOT_EXECUTED",
            "reason": "Requires environment setup",
            "actions_executed": 0,
            "actions_failed": 0,
            "actions_healed": 0,
        }
    
    def _generate_report(
        self,
        automation_id: str,
        test_name: str,
        project_name: str,
        status: str,
        pre_validation: Optional[PreExecutionValidation] = None,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> EnterpriseExecutionReport:
        """Generate enterprise execution report."""
        if self.reporter:
            return self.reporter.generate_report(
                self.execution_id or "UNKNOWN",
                automation_id,
                test_name,
                project_name,
                status,
                pre_validation,
                execution_result,
                self.action_evidence,
                self.healing_sessions,
            )
        
        # Default report
        return EnterpriseExecutionReport(
            report_id=f"REPORT-{uuid.uuid4().hex[:8].upper()}",
            execution_id=self.execution_id or "UNKNOWN",
            project_name=project_name,
            test_name=test_name,
            status=status,
            total_tests=1,
            passed_tests=1 if status == "PASSED" else 0,
            failed_tests=1 if status == "FAILED" else 0,
            recovered_tests=1 if status == "RECOVERED" else 0,
        )
    
    def handle_failure(
        self,
        error: Exception,
        context: Dict[str, Any],
    ) -> HealingSession:
        """Handle failure with multi-level recovery."""
        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        
        logger.info(f"[ORCHESTRATOR] Handling failure {failure_id}")
        
        # Classify failure
        if self.failure_classifier:
            classification = self.failure_classifier.classify_failure(
                str(error), context=context
            )
        else:
            classification = None
        
        # Check retry policy
        if self.retry_policy:
            retry_decision = self.retry_policy.should_retry(
                classification, context
            )
        else:
            retry_decision = None
        
        # Attempt recovery
        if self.recovery_engine and retry_decision and retry_decision.should_retry:
            healing_session = self.recovery_engine.attempt_recovery(
                failure_id, classification, context
            )
            self.healing_sessions.append(healing_session)
            return healing_session
        
        # Create empty healing session
        return HealingSession(
            session_id=f"HEAL-{uuid.uuid4().hex[:8].upper()}",
            failure_id=failure_id,
            final_result="NO_RECOVERY",
        )
    
    def update_state(
        self,
        new_state: ExecutionState,
        phase: Optional[ExecutionPhase] = None,
    ):
        """Update execution state."""
        old_state = self.current_state
        self.current_state = new_state
        
        if phase:
            old_phase = self.current_phase
            self.current_phase = phase
        
        logger.info(
            f"[ORCHESTRATOR] State transition: {old_state} -> {new_state}"
        )
