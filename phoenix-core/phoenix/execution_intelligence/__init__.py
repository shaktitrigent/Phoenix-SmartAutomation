"""Priority 25 - Universal Autonomous Execution Intelligence.

This module provides comprehensive execution intelligence for Phoenix,
including universal execution orchestration, failure detection, healing,
runtime learning, and headed runtime verification.

Priority 25: Universal Autonomous Execution Intelligence + Headed Runtime Verification
"""

from phoenix.execution_intelligence.models import (
    ExecutionState,
    ExecutionPhase,
    RecoveryLevel,
    ExecutionIntelligenceScore,
    ActionExecutionEvidence,
    PreExecutionValidation,
    SmartRetryDecision,
    RuntimeRegression,
    EnterpriseExecutionReport,
)

from phoenix.execution_intelligence.orchestrator import (
    UniversalExecutionOrchestrator,
)

from phoenix.execution_intelligence.pre_execution import (
    PreExecutionValidator,
)

from phoenix.execution_intelligence.action_intelligence import (
    ActionIntelligence,
)

from phoenix.execution_intelligence.failure_intelligence import (
    EnhancedFailureClassifier,
)

from phoenix.execution_intelligence.recovery import (
    MultiLevelRecovery,
)

from phoenix.execution_intelligence.state_machine import (
    ExecutionStateMachine,
)

from phoenix.execution_intelligence.retry_policy import (
    SmartRetryPolicy,
)

from phoenix.execution_intelligence.regression_detection import (
    RuntimeRegressionDetector,
)

from phoenix.execution_intelligence.scoring import (
    ExecutionIntelligenceScorer,
)

from phoenix.execution_intelligence.reporting import (
    EnterpriseExecutionReporter,
)

__all__ = [
    # Models
    "ExecutionState",
    "ExecutionPhase",
    "RecoveryLevel",
    "ExecutionIntelligenceScore",
    "ActionExecutionEvidence",
    "PreExecutionValidation",
    "SmartRetryDecision",
    "RuntimeRegression",
    "EnterpriseExecutionReport",
    
    # Core Components
    "UniversalExecutionOrchestrator",
    "PreExecutionValidator",
    "ActionIntelligence",
    "EnhancedFailureClassifier",
    "MultiLevelRecovery",
    "ExecutionStateMachine",
    "SmartRetryPolicy",
    "RuntimeRegressionDetector",
    "ExecutionIntelligenceScorer",
    "EnterpriseExecutionReporter",
]
