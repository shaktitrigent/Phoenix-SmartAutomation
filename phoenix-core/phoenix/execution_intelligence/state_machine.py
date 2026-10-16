"""Runtime State Machine - Universal execution state model.

This module implements a universal execution state machine that tracks
state transitions during execution.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import ExecutionState, ExecutionPhase

logger = logging.getLogger(__name__)


class ExecutionStateMachine:
    """Universal execution state machine.
    
    Tracks state transitions:
    - Normal execution path
    - Failure recovery path
    - Healing path
    - Regeneration path
    """
    
    def __init__(self):
        self.current_state = ExecutionState.INITIALIZING
        self.current_phase = ExecutionPhase.PRE_EXECUTION
        self.state_history: List[Dict[str, Any]] = []
        
        # Valid transitions
        self.valid_transitions = {
            ExecutionState.INITIALIZING: [
                ExecutionState.BROWSER_STARTED,
                ExecutionState.ABORTED,
            ],
            ExecutionState.BROWSER_STARTED: [
                ExecutionState.PAGE_LOADING,
                ExecutionState.ABORTED,
            ],
            ExecutionState.PAGE_LOADING: [
                ExecutionState.PAGE_ANALYZED,
                ExecutionState.FAILURE,
                ExecutionState.ABORTED,
            ],
            ExecutionState.PAGE_ANALYZED: [
                ExecutionState.ACTION_EXECUTING,
                ExecutionState.FAILURE,
                ExecutionState.ABORTED,
            ],
            ExecutionState.ACTION_EXECUTING: [
                ExecutionState.ACTION_VERIFIED,
                ExecutionState.FAILURE,
                ExecutionState.ABORTED,
            ],
            ExecutionState.ACTION_VERIFIED: [
                ExecutionState.NEXT_ACTION,
                ExecutionState.TEST_COMPLETED,
                ExecutionState.FAILURE,
            ],
            ExecutionState.NEXT_ACTION: [
                ExecutionState.ACTION_EXECUTING,
                ExecutionState.TEST_COMPLETED,
                ExecutionState.FAILURE,
            ],
            ExecutionState.FAILURE: [
                ExecutionState.DIAGNOSING,
                ExecutionState.ABORTED,
            ],
            ExecutionState.DIAGNOSING: [
                ExecutionState.HEALING,
                ExecutionState.REGENERATING,
                ExecutionState.ABORTED,
            ],
            ExecutionState.HEALING: [
                ExecutionState.RETRYING,
                ExecutionState.RECOVERED,
                ExecutionState.ABORTED,
            ],
            ExecutionState.RETRYING: [
                ExecutionState.VERIFYING,
                ExecutionState.FAILURE,
                ExecutionState.ABORTED,
            ],
            ExecutionState.VERIFYING: [
                ExecutionState.RECOVERED,
                ExecutionState.FAILURE,
                ExecutionState.ABORTED,
            ],
            ExecutionState.RECOVERED: [
                ExecutionState.ACTION_EXECUTING,
                ExecutionState.TEST_COMPLETED,
            ],
            ExecutionState.REGENERATING: [
                ExecutionState.ACTION_EXECUTING,
                ExecutionState.ABORTED,
            ],
            ExecutionState.TEST_COMPLETED: [
                ExecutionState.INITIALIZING,  # For next test
            ],
            ExecutionState.ABORTED: [
                ExecutionState.INITIALIZING,  # For next test
            ],
        }
        
        logger.info("ExecutionStateMachine initialized")
    
    def transition_to(
        self,
        new_state: ExecutionState,
        phase: Optional[ExecutionPhase] = None,
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition to a new state.
        
        Args:
            new_state: Target state
            phase: Optional phase transition
            reason: Reason for transition
            evidence: Supporting evidence
            
        Returns:
            True if transition is valid, False otherwise
        """
        old_state = self.current_state
        
        # Validate transition
        if new_state not in self.valid_transitions.get(old_state, []):
            logger.warning(
                f"[STATE MACHINE] Invalid transition: {old_state} -> {new_state}"
            )
            return False
        
        # Record transition
        self.state_history.append({
            "from_state": old_state.value,
            "to_state": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "evidence": evidence or {},
        })
        
        # Update state
        self.current_state = new_state
        if phase:
            self.current_phase = phase
        
        logger.info(
            f"[STATE MACHINE] Transition: {old_state.value} -> {new_state.value} "
            f"(reason: {reason})"
        )
        
        return True
    
    def get_current_state(self) -> ExecutionState:
        """Get current execution state."""
        return self.current_state
    
    def get_current_phase(self) -> ExecutionPhase:
        """Get current execution phase."""
        return self.current_phase
    
    def get_state_history(self) -> List[Dict[str, Any]]:
        """Get complete state transition history."""
        return self.state_history
    
    def is_in_failure_path(self) -> bool:
        """Check if currently in failure recovery path."""
        failure_states = [
            ExecutionState.FAILURE,
            ExecutionState.DIAGNOSING,
            ExecutionState.HEALING,
            ExecutionState.RETRYING,
            ExecutionState.VERIFYING,
            ExecutionState.REGENERATING,
        ]
        return self.current_state in failure_states
    
    def can_retry(self) -> bool:
        """Check if retry is possible from current state."""
        return self.current_state in [
            ExecutionState.HEALING,
            ExecutionState.REGENERATING,
        ]
