"""Action-Level Intelligence - Understand why actions are performed.

This module implements action-level intelligence that tracks semantic intent,
component context, and execution evidence for every action.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import ActionExecutionEvidence

logger = logging.getLogger(__name__)


class ActionIntelligence:
    """Action-level intelligence for understanding execution.
    
    Every action should have:
    - Semantic intent
    - Component context
    - Locator information
    - Expected outcome
    - Actual outcome
    - Evidence
    """
    
    def __init__(self):
        self.action_history: List[ActionExecutionEvidence] = []
        
        logger.info("ActionIntelligence initialized")
    
    def create_action_evidence(
        self,
        action_id: str,
        action_type: str,
        semantic_intent: str = "",
        component_purpose: str = "",
        component_id: str = "",
        component_type: str = "",
        locator: str = "",
        locator_strategy: str = "",
        locator_confidence: float = 0.0,
        input_data: Optional[Dict[str, Any]] = None,
        expected_outcome: str = "",
        page_url: str = "",
        page_type: str = "",
    ) -> ActionExecutionEvidence:
        """Create action evidence with full context.
        
        Args:
            action_id: Action identifier
            action_type: Type of action
            semantic_intent: Why this action is being performed
            component_purpose: Purpose of target component
            component_id: Target component ID
            component_type: Component type
            locator: Locator being used
            locator_strategy: Locator strategy
            locator_confidence: Confidence in locator
            input_data: Input data for action
            expected_outcome: Expected result
            page_url: Current page URL
            page_type: Semantic page type
            
        Returns:
            ActionExecutionEvidence with full context
        """
        evidence = ActionExecutionEvidence(
            action_id=action_id,
            action_type=action_type,
            semantic_intent=semantic_intent,
            component_purpose=component_purpose,
            component_id=component_id,
            component_type=component_type,
            locator=locator,
            locator_strategy=locator_strategy,
            locator_confidence=locator_confidence,
            input_data=input_data or {},
            expected_outcome=expected_outcome,
            page_url=page_url,
            page_type=page_type,
        )
        
        self.action_history.append(evidence)
        
        logger.debug(
            f"[ACTION INTELLIGENCE] Created evidence for {action_id}: "
            f"intent={semantic_intent}, component={component_purpose}"
        )
        
        return evidence
    
    def record_action_result(
        self,
        action_id: str,
        actual_outcome: str,
        result: str,
        duration_ms: float,
        console_errors: Optional[List[str]] = None,
        network_errors: Optional[List[str]] = None,
        dom_snapshot_ref: Optional[str] = None,
        screenshot_ref: Optional[str] = None,
    ):
        """Record the result of an action execution.
        
        Args:
            action_id: Action identifier
            actual_outcome: What actually happened
            result: success/failure
            duration_ms: Execution duration
            console_errors: Console errors encountered
            network_errors: Network errors encountered
            dom_snapshot_ref: Reference to DOM snapshot
            screenshot_ref: Reference to screenshot
        """
        # Find the action evidence
        action_evidence = next(
            (a for a in self.action_history if a.action_id == action_id),
            None
        )
        
        if action_evidence:
            action_evidence.actual_outcome = actual_outcome
            action_evidence.result = result
            action_evidence.duration_ms = duration_ms
            action_evidence.end_time = datetime.now(timezone.utc).isoformat()
            action_evidence.console_errors = console_errors or []
            action_evidence.network_errors = network_errors or []
            action_evidence.dom_snapshot_ref = dom_snapshot_ref
            action_evidence.screenshot_ref = screenshot_ref
            
            logger.info(
                f"[ACTION INTELLIGENCE] Recorded result for {action_id}: "
                f"{result} ({duration_ms:.0f}ms)"
            )
    
    def get_action_evidence(self, action_id: str) -> Optional[ActionExecutionEvidence]:
        """Get evidence for a specific action."""
        return next(
            (a for a in self.action_history if a.action_id == action_id),
            None
        )
    
    def get_failed_actions(self) -> List[ActionExecutionEvidence]:
        """Get all failed actions."""
        return [a for a in self.action_history if a.result == "failure"]
    
    def get_action_summary(self) -> Dict[str, Any]:
        """Get summary of all actions."""
        total = len(self.action_history)
        successful = len([a for a in self.action_history if a.result == "success"])
        failed = len([a for a in self.action_history if a.result == "failure"])
        
        total_duration = sum(a.duration_ms for a in self.action_history)
        avg_duration = total_duration / total if total > 0 else 0
        
        return {
            "total_actions": total,
            "successful_actions": successful,
            "failed_actions": failed,
            "success_rate": successful / total if total > 0 else 0,
            "total_duration_ms": total_duration,
            "average_duration_ms": avg_duration,
        }
