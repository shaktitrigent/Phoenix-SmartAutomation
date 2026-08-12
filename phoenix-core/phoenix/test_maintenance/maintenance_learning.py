"""Maintenance Learning - Priority 30.

This module integrates runtime learning from Priorities 23 and 25 to improve
maintenance decisions over time.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from phoenix.test_maintenance.models import (
    RegenerationResult,
    ValidationResult,
    ContinuousValidationResult,
    MaintenanceOutcome,
)

logger = logging.getLogger(__name__)


class MaintenanceLearning:
    """Integrates runtime learning for maintenance improvement.
    
    This learning system:
    - Learns which locators survive changes
    - Learns which regeneration strategies succeed
    - Learns which changes cause failures
    - Learns which components are unstable
    - Learns which flows are unstable
    - Learns which maintenance decisions are accurate
    - Learns which tests frequently require regeneration
    - Updates confidence based on real execution evidence
    """
    
    def __init__(self):
        """Initialize maintenance learning."""
        # Learning data
        self.locator_survival_rate: Dict[str, float] = {}
        self.regeneration_strategy_success: Dict[str, float] = {}
        self.change_failure_rate: Dict[str, float] = {}
        self.component_stability: Dict[str, float] = {}
        self.flow_stability: Dict[str, float] = {}
        self.maintenance_decision_accuracy: Dict[str, float] = {}
        self.test_regeneration_frequency: Dict[str, int] = {}
        
        # Learning history
        self.learning_history: List[Dict[str, Any]] = []
        
        logger.info("[MAINTENANCE LEARNING] Initialized")
    
    def learn_from_regeneration(
        self,
        regeneration_result: RegenerationResult,
    ):
        """Learn from regeneration result.
        
        Args:
            regeneration_result: Regeneration result
        """
        # Track regeneration strategy success
        strategy = regeneration_result.decision_type.value
        if strategy not in self.regeneration_strategy_success:
            self.regeneration_strategy_success[strategy] = {"success": 0, "total": 0}
        
        self.regeneration_strategy_success[strategy]["total"] += 1
        if regeneration_result.success:
            self.regeneration_strategy_success[strategy]["success"] += 1
        
        # Track test regeneration frequency
        test_id = regeneration_result.test_id
        self.test_regeneration_frequency[test_id] = self.test_regeneration_frequency.get(test_id, 0) + 1
        
        logger.debug(f"[MAINTENANCE LEARNING] Learned from regeneration: {strategy}")
    
    def learn_from_validation(
        self,
        validation_result: ValidationResult,
    ):
        """Learn from validation result.
        
        Args:
            validation_result: Validation result
        """
        # Track locator validation results
        for step_id, locator_data in validation_result.locator_validation.items():
            if isinstance(locator_data, dict) and locator_data.get("valid", False):
                # Locator survived validation
                self.locator_survival_rate[step_id] = self.locator_survival_rate.get(step_id, 0.0) + 0.1
        
        logger.debug(f"[MAINTENANCE LEARNING] Learned from validation: {validation_result.status.value}")
    
    def learn_from_execution(
        self,
        execution_result: ContinuousValidationResult,
    ):
        """Learn from continuous validation execution.
        
        Args:
            execution_result: Continuous validation result
        """
        # Track outcome for learning
        if execution_result.outcome == MaintenanceOutcome.SUCCESS:
            # Successful maintenance - reinforce the decision
            self._reinforce_decision(execution_result.test_id)
        elif execution_result.outcome == MaintenanceOutcome.FAILED:
            # Failed maintenance - learn from failure
            self._learn_from_failure(execution_result)
        
        # Track component stability based on healing results
        healing_results = execution_result.healing_results
        if healing_results.get("healing_required", False):
            # Components requiring healing are less stable
            self._mark_components_unstable(execution_result.test_id)
        
        logger.debug(f"[MAINTENANCE LEARNING] Learned from execution: {execution_result.outcome.value}")
    
    def _reinforce_decision(
        self,
        test_id: str,
    ):
        """Reinforce successful maintenance decision.
        
        Args:
            test_id: Test ID
        """
        if test_id not in self.maintenance_decision_accuracy:
            self.maintenance_decision_accuracy[test_id] = {"success": 0, "total": 0}
        
        self.maintenance_decision_accuracy[test_id]["total"] += 1
        self.maintenance_decision_accuracy[test_id]["success"] += 1
    
    def _learn_from_failure(
        self,
        execution_result: ContinuousValidationResult,
    ):
        """Learn from maintenance failure.
        
        Args:
            execution_result: Execution result
        """
        test_id = execution_result.test_id
        
        # Track failure
        if test_id not in self.maintenance_decision_accuracy:
            self.maintenance_decision_accuracy[test_id] = {"success": 0, "total": 0}
        
        self.maintenance_decision_accuracy[test_id]["total"] += 1
        
        # Track failure classification
        failure_classification = execution_result.failure_classification
        if failure_classification:
            if failure_classification not in self.change_failure_rate:
                self.change_failure_rate[failure_classification] = 0
            self.change_failure_rate[failure_classification] += 1
    
    def _mark_components_unstable(
        self,
        test_id: str,
    ):
        """Mark components as unstable based on healing.
        
        Args:
            test_id: Test ID
        """
        # In a real implementation, this would track specific components
        # For now, mark the test as having unstable components
        if test_id not in self.component_stability:
            self.component_stability[test_id] = 1.0
        
        # Reduce stability score
        self.component_stability[test_id] = max(0.0, self.component_stability[test_id] - 0.1)
    
    def get_regeneration_strategy_confidence(
        self,
        strategy: str,
    ) -> float:
        """Get confidence in a regeneration strategy.
        
        Args:
            strategy: Regeneration strategy
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if strategy not in self.regeneration_strategy_success:
            return 0.5  # Default confidence
        
        data = self.regeneration_strategy_success[strategy]
        if data["total"] == 0:
            return 0.5
        
        return data["success"] / data["total"]
    
    def get_test_stability(
        self,
        test_id: str,
    ) -> float:
        """Get stability score for a test.
        
        Args:
            test_id: Test ID
            
        Returns:
            Stability score (0.0 to 1.0)
        """
        # Consider regeneration frequency (lower is better)
        frequency = self.test_regeneration_frequency.get(test_id, 0)
        frequency_score = max(0.0, 1.0 - (frequency * 0.1))
        
        # Consider component stability
        component_score = self.component_stability.get(test_id, 1.0)
        
        # Consider decision accuracy
        if test_id in self.maintenance_decision_accuracy:
            data = self.maintenance_decision_accuracy[test_id]
            decision_score = data["success"] / data["total"] if data["total"] > 0 else 0.5
        else:
            decision_score = 0.5
        
        # Combined score
        return (frequency_score + component_score + decision_score) / 3.0
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """Get learning metrics.
        
        Returns:
            Learning metrics
        """
        # Calculate strategy success rates
        strategy_metrics = {}
        for strategy, data in self.regeneration_strategy_success.items():
            if data["total"] > 0:
                strategy_metrics[strategy] = {
                    "success_rate": data["success"] / data["total"],
                    "total_attempts": data["total"],
                }
        
        return {
            "strategies": strategy_metrics,
            "test_regeneration_frequency": self.test_regeneration_frequency,
            "component_stability": self.component_stability,
            "decision_accuracy": self.maintenance_decision_accuracy,
            "total_learning_events": len(self.learning_history),
        }
    
    def record_learning_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ):
        """Record a learning event.
        
        Args:
            event_type: Type of learning event
            data: Event data
        """
        self.learning_history.append({
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
