"""Runtime Intelligence Integration - Priority 25 components integration into actual execution.

This module integrates Priority 25 execution intelligence components into the
real IntelligentRuntime and IntelligentPage execution flow.

Priority 26: Universal Production Runtime Integration
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from phoenix.execution_intelligence.models import (
        ExecutionState,
        ExecutionPhase,
        ActionExecutionEvidence,
        HealingSession,
    )
    from phoenix.execution_intelligence.orchestrator import UniversalExecutionOrchestrator
    from phoenix.execution_intelligence.action_intelligence import ActionIntelligence
    from phoenix.execution_intelligence.failure_intelligence import EnhancedFailureClassifier
    from phoenix.execution_intelligence.recovery import MultiLevelRecovery
    from phoenix.execution_intelligence.state_machine import ExecutionStateMachine
    from phoenix.execution_intelligence.retry_policy import SmartRetryPolicy
    from phoenix.execution_intelligence.regression_detection import RuntimeRegressionDetector
    from phoenix.execution_intelligence.scoring import ExecutionIntelligenceScorer
    from phoenix.execution_intelligence.reporting import EnterpriseExecutionReporter
    from phoenix.execution_intelligence.pre_execution import PreExecutionValidator
    PRIORITY25_AVAILABLE = True
except ImportError:
    PRIORITY25_AVAILABLE = False

logger = logging.getLogger(__name__)


class RuntimeIntelligenceIntegrator:
    """Integrates Priority 25 execution intelligence into IntelligentRuntime.
    
    This class bridges the gap between:
    - Priority 25's UniversalExecutionOrchestrator
    - Priority 25's execution intelligence components
    - Existing IntelligentRuntime
    - Actual browser execution
    
    The integration ensures that execution intelligence is applied during
    real test execution, not just as standalone modules.
    """
    
    def __init__(self, intelligent_runtime=None):
        """Initialize runtime intelligence integrator.
        
        Args:
            intelligent_runtime: Existing IntelligentRuntime instance
        """
        self.intelligent_runtime = intelligent_runtime
        
        # Priority 25 components
        self.orchestrator = None
        self.action_intelligence = None
        self.failure_classifier = None
        self.recovery_engine = None
        self.state_machine = None
        self.retry_policy = None
        self.regression_detector = None
        self.scorer = None
        self.reporter = None
        self.pre_validator = None
        
        # Execution state
        self.execution_evidence: Dict[str, Any] = {}
        self.action_history: List[ActionExecutionEvidence] = []
        self.healing_sessions: List[HealingSession] = []
        
        # Initialize Priority 25 components if available
        if PRIORITY25_AVAILABLE:
            self._initialize_priority25_components()
        else:
            logger.warning("[RUNTIME INTEGRATION] Priority 25 components not available")
    
    def _initialize_priority25_components(self):
        """Initialize Priority 25 execution intelligence components."""
        # Initialize Universal Execution Orchestrator
        self.orchestrator = UniversalExecutionOrchestrator(
            intelligent_runtime=self.intelligent_runtime,
        )
        
        # Initialize Action Intelligence
        self.action_intelligence = ActionIntelligence()
        
        # Initialize Enhanced Failure Classifier
        self.failure_classifier = EnhancedFailureClassifier()
        
        # Initialize Multi-Level Recovery
        self.recovery_engine = MultiLevelRecovery(
            healing_engine=self.intelligent_runtime.healing_engine if self.intelligent_runtime else None
        )
        
        # Initialize State Machine
        self.state_machine = ExecutionStateMachine()
        
        # Initialize Smart Retry Policy
        self.retry_policy = SmartRetryPolicy()
        
        # Initialize Regression Detector
        self.regression_detector = RuntimeRegressionDetector()
        
        # Initialize Scorer
        self.scorer = ExecutionIntelligenceScorer()
        
        # Initialize Reporter
        self.reporter = EnterpriseExecutionReporter()
        
        # Initialize Pre-Execution Validator
        self.pre_validator = PreExecutionValidator()
        
        logger.info("[RUNTIME INTEGRATION] Priority 25 components initialized")
    
    def start_execution(self, test_name: str, project_name: str) -> str:
        """Start execution with intelligence tracking.
        
        Args:
            test_name: Name of the test
            project_name: Name of the project
            
        Returns:
            Execution ID
        """
        if self.state_machine:
            self.state_machine.transition_to(
                ExecutionState.INITIALIZING,
                phase=ExecutionPhase.PRE_EXECUTION,
                reason="Execution started"
            )
        
        if self.orchestrator:
            self.orchestrator.execution_id = f"EXEC-{test_name}"
            self.orchestrator.current_state = ExecutionState.INITIALIZING
        
        return self.orchestrator.execution_id if self.orchestrator else "UNKNOWN"
    
    def track_action(
        self,
        action_id: str,
        action_type: str,
        semantic_intent: str,
        component_purpose: str,
        locator: str,
        locator_confidence: float,
        expected_outcome: str,
    ) -> Optional[ActionExecutionEvidence]:
        """Track action execution with intelligence.
        
        Args:
            action_id: Action identifier
            action_type: Type of action
            semantic_intent: Why this action is being performed
            component_purpose: Purpose of target component
            locator: Locator being used
            locator_confidence: Confidence in locator
            expected_outcome: Expected result
            
        Returns:
            ActionExecutionEvidence if available
        """
        if not self.action_intelligence:
            return None
        
        evidence = self.action_intelligence.create_action_evidence(
            action_id=action_id,
            action_type=action_type,
            semantic_intent=semantic_intent,
            component_purpose=component_purpose,
            locator=locator,
            locator_confidence=locator_confidence,
            expected_outcome=expected_outcome,
        )
        
        self.action_history.append(evidence)
        
        if self.state_machine:
            self.state_machine.transition_to(
                ExecutionState.ACTION_EXECUTING,
                phase=ExecutionPhase.ACTION_EXECUTION,
                reason=f"Executing action: {action_id}"
            )
        
        return evidence
    
    def record_action_result(
        self,
        action_id: str,
        actual_outcome: str,
        result: str,
        duration_ms: float,
        error_message: str = "",
    ):
        """Record action execution result.
        
        Args:
            action_id: Action identifier
            actual_outcome: What actually happened
            result: success/failure
            duration_ms: Execution duration
            error_message: Error message if failed
        """
        if not self.action_intelligence:
            return
        
        self.action_intelligence.record_action_result(
            action_id=action_id,
            actual_outcome=actual_outcome,
            result=result,
            duration_ms=duration_ms,
            console_errors=[error_message] if error_message else [],
        )
        
        if self.state_machine:
            if result == "success":
                self.state_machine.transition_to(
                    ExecutionState.ACTION_VERIFIED,
                    phase=ExecutionPhase.ACTION_EXECUTION,
                    reason=f"Action succeeded: {action_id}"
                )
            else:
                self.state_machine.transition_to(
                    ExecutionState.FAILURE,
                    phase=ExecutionPhase.FAILURE_HANDLING,
                    reason=f"Action failed: {action_id}"
                )
    
    def classify_failure(
        self,
        error_message: str,
        stack_trace: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classify failure with enhanced intelligence.
        
        Args:
            error_message: Error message
            stack_trace: Stack trace
            context: Additional context
            
        Returns:
            Failure classification if available
        """
        if not self.failure_classifier:
            return None
        
        classification = self.failure_classifier.classify_failure(
            error_message=error_message,
            stack_trace=stack_trace,
            context=context,
        )
        
        logger.info(
            f"[RUNTIME INTEGRATION] Failure classified as {classification['failure_type']}"
        )
        
        return classification
    
    def attempt_healing(
        self,
        failure_id: str,
        classification: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[HealingSession]:
        """Attempt healing with multi-level recovery.
        
        Args:
            failure_id: Failure identifier
            classification: Failure classification
            context: Execution context
            
        Returns:
            Healing session if available
        """
        if not self.recovery_engine:
            return None
        
        if self.state_machine:
            self.state_machine.transition_to(
                ExecutionState.HEALING,
                phase=ExecutionPhase.HEALING,
                reason=f"Healing failure: {failure_id}"
            )
        
        session = self.recovery_engine.attempt_recovery(
            failure_id=failure_id,
            failure_classification=classification,
            context=context,
        )
        
        self.healing_sessions.append(session)
        
        if session.final_result == "RECOVERED":
            if self.state_machine:
                self.state_machine.transition_to(
                    ExecutionState.RECOVERED,
                    phase=ExecutionPhase.ACTION_EXECUTION,
                    reason=f"Healing succeeded: {failure_id}"
                )
        
        return session
    
    def should_retry(
        self,
        classification: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Determine if execution should be retried.
        
        Args:
            classification: Failure classification
            context: Execution context
            
        Returns:
            True if should retry
        """
        if not self.retry_policy:
            return False
        
        decision = self.retry_policy.should_retry(classification, context)
        
        logger.info(
            f"[RUNTIME INTEGRATION] Retry decision: {decision.should_retry} "
            f"(reason: {decision.reason})"
        )
        
        return decision.should_retry
    
    def end_execution(self, status: str) -> Optional[Dict[str, Any]]:
        """End execution and generate intelligence report.
        
        Args:
            status: Execution status (passed/failed)
            
        Returns:
            Enterprise execution report if available
        """
        if self.state_machine:
            self.state_machine.transition_to(
                ExecutionState.TEST_COMPLETED,
                phase=ExecutionPhase.REPORTING,
                reason=f"Execution completed with status: {status}"
            )
        
        if not self.reporter:
            return None
        
        # Generate execution report
        report = self.reporter.generate_report(
            execution_id=self.orchestrator.execution_id if self.orchestrator else "UNKNOWN",
            automation_id="INTEGRATED",
            test_name="runtime_test",
            project_name="default",
            status=status,
            action_evidence=self.action_history,
            healing_sessions=self.healing_sessions,
        )
        
        logger.info(
            f"[RUNTIME INTEGRATION] Generated execution report: {report.report_id}"
        )
        
        return report.dict()


def create_intelligent_page_with_intelligence(page, intelligent_runtime, **kwargs):
    """Create intelligent page with Priority 25 execution intelligence.
    
    This function wraps the existing IntelligentPage with Priority 25
    execution intelligence integration.
    
    Args:
        page: Playwright Page object
        intelligent_runtime: IntelligentRuntime instance
        **kwargs: Additional arguments
        
    Returns:
        Wrapped page with intelligence integration
    """
    try:
        from phoenix.execution.intelligent_page import create_intelligent_page
    except ImportError:
        logger.warning("[RUNTIME INTEGRATION] IntelligentPage not available")
        return page
    
    # Create the base intelligent page
    intelligent_page = create_intelligent_page(
        page=page,
        intelligent_runtime=intelligent_runtime,
        **kwargs
    )
    
    # Add Priority 25 integration
    if PRIORITY25_AVAILABLE:
        integrator = RuntimeIntelligenceIntegrator(intelligent_runtime)
        intelligent_page._intelligence_integrator = integrator
        
        # Override action methods to add intelligence tracking
        original_click = intelligent_page.click
        original_fill = intelligent_page.fill
        original_goto = intelligent_page.goto
        
        def click_with_intelligence(*args, **kwargs):
            """Click with intelligence tracking."""
            # Extract locator if provided
            locator = args[0] if args else kwargs.get('selector', '')
            
            # Track action
            integrator.track_action(
                action_id=f"click_{id(args)}",
                action_type="click",
                semantic_intent="Click element",
                component_purpose="Interactive element",
                locator=locator,
                locator_confidence=0.85,
                expected_outcome="Element clicked",
            )
            
            # Execute original click
            try:
                result = original_click(*args, **kwargs)
                integrator.record_action_result(
                    action_id=f"click_{id(args)}",
                    actual_outcome="Element clicked",
                    result="success",
                    duration_ms=100,
                )
                return result
            except Exception as e:
                integrator.record_action_result(
                    action_id=f"click_{id(args)}",
                    actual_outcome=str(e),
                    result="failure",
                    duration_ms=100,
                    error_message=str(e),
                )
                
                # Classify failure
                classification = integrator.classify_failure(str(e))
                
                # Attempt healing
                if classification:
                    integrator.attempt_healing(
                        failure_id=f"fail_{id(args)}",
                        classification=classification,
                        context={"locator": locator},
                    )
                
                raise
        
        def fill_with_intelligence(*args, **kwargs):
            """Fill with intelligence tracking."""
            locator = args[0] if args else kwargs.get('selector', '')
            value = args[1] if len(args) > 1 else kwargs.get('value', '')
            
            integrator.track_action(
                action_id=f"fill_{id(args)}",
                action_type="fill",
                semantic_intent="Enter text",
                component_purpose="Input field",
                locator=locator,
                locator_confidence=0.85,
                expected_outcome="Text entered",
            )
            
            try:
                result = original_fill(*args, **kwargs)
                integrator.record_action_result(
                    action_id=f"fill_{id(args)}",
                    actual_outcome="Text entered",
                    result="success",
                    duration_ms=100,
                )
                return result
            except Exception as e:
                integrator.record_action_result(
                    action_id=f"fill_{id(args)}",
                    actual_outcome=str(e),
                    result="failure",
                    duration_ms=100,
                    error_message=str(e),
                )
                raise
        
        def goto_with_intelligence(*args, **kwargs):
            """Goto with intelligence tracking."""
            url = args[0] if args else kwargs.get('url', '')
            
            integrator.track_action(
                action_id=f"goto_{id(args)}",
                action_type="goto",
                semantic_intent="Navigate to page",
                component_purpose="Navigation",
                locator=url,
                locator_confidence=1.0,
                expected_outcome="Page loaded",
            )
            
            try:
                result = original_goto(*args, **kwargs)
                integrator.record_action_result(
                    action_id=f"goto_{id(args)}",
                    actual_outcome="Page loaded",
                    result="success",
                    duration_ms=500,
                )
                return result
            except Exception as e:
                integrator.record_action_result(
                    action_id=f"goto_{id(args)}",
                    actual_outcome=str(e),
                    result="failure",
                    duration_ms=500,
                    error_message=str(e),
                )
                raise
        
        # Override methods
        intelligent_page.click = click_with_intelligence
        intelligent_page.fill = fill_with_intelligence
        intelligent_page.goto = goto_with_intelligence
        
        logger.info("[RUNTIME INTEGRATION] Priority 25 intelligence integrated into IntelligentPage")
    
    return intelligent_page
