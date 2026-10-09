"""Runtime Learning - Test Intelligence Runtime Learning (Priority 23).

This module integrates test intelligence with the runtime learning system,
enabling Phoenix to learn from test execution and improve future test generation.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from phoenix.test_intelligence.models import (
    TestScenario,
    TestExecutionFeedback,
)

logger = logging.getLogger(__name__)


class TestRuntimeLearning:
    """Runtime learning for test intelligence.
    
    This learning system:
    - Records test execution feedback
    - Learns which scenarios are useful
    - Learns which scenarios fail
    - Tracks incorrect assumptions
    - Identifies unstable components
    - Improves future test generation
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self, base_dir: str = "phoenix_runtime", enable_persistence: bool = True):
        """Initialize the runtime learning system.
        
        Args:
            base_dir: Base directory for storing learning data
        """
        self.base_dir = Path(base_dir)
        self.learning_dir = self.base_dir / "test_intelligence_learning"
        self.enable_persistence = enable_persistence
        
        if enable_persistence:
            self.learning_dir.mkdir(parents=True, exist_ok=True)
        
        # Learning data
        self.scenario_history: Dict[str, List[TestExecutionFeedback]] = {}
        self.component_stability: Dict[str, Dict[str, Any]] = {}
        self.flow_reliability: Dict[str, Dict[str, Any]] = {}
        self.assumption_accuracy: Dict[str, Dict[str, Any]] = {}
        
        # Load existing learning data
        self._load_learning_data()
        
        logger.info(f"[TEST RUNTIME LEARNING] Initialized with directory: {self.learning_dir}")
    
    def _load_learning_data(self):
        """Load existing learning data from disk."""
        try:
            # Load scenario history
            scenario_history_file = self.learning_dir / "scenario_history.json"
            if scenario_history_file.exists():
                with open(scenario_history_file, 'r') as f:
                    data = json.load(f)
                    for scenario_id, feedbacks in data.items():
                        self.scenario_history[scenario_id] = [
                            TestExecutionFeedback(**fb) for fb in feedbacks
                        ]
            
            # Load component stability
            component_stability_file = self.learning_dir / "component_stability.json"
            if component_stability_file.exists():
                with open(component_stability_file, 'r') as f:
                    self.component_stability = json.load(f)
            
            # Load flow reliability
            flow_reliability_file = self.learning_dir / "flow_reliability.json"
            if flow_reliability_file.exists():
                with open(flow_reliability_file, 'r') as f:
                    self.flow_reliability = json.load(f)
            
            # Load assumption accuracy
            assumption_accuracy_file = self.learning_dir / "assumption_accuracy.json"
            if assumption_accuracy_file.exists():
                with open(assumption_accuracy_file, 'r') as f:
                    self.assumption_accuracy = json.load(f)
            
            logger.info("[TEST RUNTIME LEARNING] Loaded existing learning data")
        except Exception as e:
            logger.warning(f"[TEST RUNTIME LEARNING] Error loading learning data: {e}")
    
    def _save_learning_data(self):
        """Save learning data to disk."""
        try:
            # Save scenario history
            scenario_history_file = self.learning_dir / "scenario_history.json"
            with open(scenario_history_file, 'w') as f:
                data = {
                    scenario_id: [fb.dict() for fb in feedbacks]
                    for scenario_id, feedbacks in self.scenario_history.items()
                }
                json.dump(data, f, indent=2)
            
            # Save component stability
            component_stability_file = self.learning_dir / "component_stability.json"
            with open(component_stability_file, 'w') as f:
                json.dump(self.component_stability, f, indent=2)
            
            # Save flow reliability
            flow_reliability_file = self.learning_dir / "flow_reliability.json"
            with open(flow_reliability_file, 'w') as f:
                json.dump(self.flow_reliability, f, indent=2)
            
            # Save assumption accuracy
            assumption_accuracy_file = self.learning_dir / "assumption_accuracy.json"
            with open(assumption_accuracy_file, 'w') as f:
                json.dump(self.assumption_accuracy, f, indent=2)
            
            logger.debug("[TEST RUNTIME LEARNING] Saved learning data")
        except Exception as e:
            logger.warning(f"[TEST RUNTIME LEARNING] Error saving learning data: {e}")
    
    def record_execution_feedback(
        self,
        feedback: TestExecutionFeedback,
    ):
        """Record execution feedback for a scenario.
        
        Args:
            feedback: Execution feedback to record
        """
        scenario_id = feedback.scenario_id
        
        # Add to scenario history
        if scenario_id not in self.scenario_history:
            self.scenario_history[scenario_id] = []
        
        self.scenario_history[scenario_id].append(feedback)
        
        # Update component stability
        self._update_component_stability(feedback)
        
        # Update flow reliability
        self._update_flow_reliability(feedback)
        
        # Update assumption accuracy
        self._update_assumption_accuracy(feedback)
        
        # Save learning data
        self._save_learning_data()
        
        logger.info(f"[TEST RUNTIME LEARNING] Recorded feedback for scenario {scenario_id}")
    
    def _update_component_stability(self, feedback: TestExecutionFeedback):
        """Update component stability based on feedback."""
        # This would be populated with component IDs from the scenario
        # For now, we'll update based on failure type
        if feedback.failure_type:
            # Extract component IDs from observed behavior if available
            components_affected = feedback.observed_behavior.get("components_affected", [])
            
            for component_id in components_affected:
                if component_id not in self.component_stability:
                    self.component_stability[component_id] = {
                        "success_count": 0,
                        "failure_count": 0,
                        "last_seen": None,
                    }
                
                if feedback.success:
                    self.component_stability[component_id]["success_count"] += 1
                else:
                    self.component_stability[component_id]["failure_count"] += 1
                
                self.component_stability[component_id]["last_seen"] = feedback.timestamp
    
    def _update_flow_reliability(self, feedback: TestExecutionFeedback):
        """Update flow reliability based on feedback."""
        # Extract flow IDs from observed behavior if available
        flows_affected = feedback.observed_behavior.get("flows_affected", [])
        
        for flow_id in flows_affected:
            if flow_id not in self.flow_reliability:
                self.flow_reliability[flow_id] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "last_seen": None,
                }
            
            if feedback.success:
                self.flow_reliability[flow_id]["success_count"] += 1
            else:
                self.flow_reliability[flow_id]["failure_count"] += 1
            
            self.flow_reliability[flow_id]["last_seen"] = feedback.timestamp
    
    def _update_assumption_accuracy(self, feedback: TestExecutionFeedback):
        """Update assumption accuracy based on feedback."""
        for correct_assumption in feedback.correct_assumptions:
            if correct_assumption not in self.assumption_accuracy:
                self.assumption_accuracy[correct_assumption] = {
                    "correct_count": 0,
                    "incorrect_count": 0,
                }
            
            self.assumption_accuracy[correct_assumption]["correct_count"] += 1
        
        for incorrect_assumption in feedback.incorrect_assumptions:
            if incorrect_assumption not in self.assumption_accuracy:
                self.assumption_accuracy[incorrect_assumption] = {
                    "correct_count": 0,
                    "incorrect_count": 0,
                }
            
            self.assumption_accuracy[incorrect_assumption]["incorrect_count"] += 1
    
    def get_scenario_success_rate(self, scenario_id: str) -> float:
        """Get success rate for a scenario.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            Success rate (0-1)
        """
        if scenario_id not in self.scenario_history:
            return 0.0
        
        feedbacks = self.scenario_history[scenario_id]
        if not feedbacks:
            return 0.0
        
        success_count = sum(1 for fb in feedbacks if fb.success)
        return success_count / len(feedbacks)
    
    def get_component_failure_count(self, component_id: str) -> int:
        """Get failure count for a component.
        
        Args:
            component_id: Component ID
            
        Returns:
            Failure count
        """
        if component_id not in self.component_stability:
            return 0
        
        return self.component_stability[component_id].get("failure_count", 0)
    
    def get_flow_failure_count(self, flow_id: str) -> int:
        """Get failure count for a flow.
        
        Args:
            flow_id: Flow ID
            
        Returns:
            Failure count
        """
        if flow_id not in self.flow_reliability:
            return 0
        
        return self.flow_reliability[flow_id].get("failure_count", 0)
    
    def get_unstable_components(self, threshold: int = 3) -> List[str]:
        """Get list of unstable components (high failure count).
        
        Args:
            threshold: Failure count threshold
            
        Returns:
            List of unstable component IDs
        """
        unstable = []
        
        for component_id, stability in self.component_stability.items():
            failure_count = stability.get("failure_count", 0)
            if failure_count >= threshold:
                unstable.append(component_id)
        
        return unstable
    
    def get_unreliable_flows(self, threshold: int = 3) -> List[str]:
        """Get list of unreliable flows (high failure count).
        
        Args:
            threshold: Failure count threshold
            
        Returns:
            List of unreliable flow IDs
        """
        unreliable = []
        
        for flow_id, reliability in self.flow_reliability.items():
            failure_count = reliability.get("failure_count", 0)
            if failure_count >= threshold:
                unreliable.append(flow_id)
        
        return unreliable
    
    def get_assumption_accuracy(self, assumption: str) -> float:
        """Get accuracy for an assumption.
        
        Args:
            assumption: Assumption text
            
        Returns:
            Accuracy (0-1)
        """
        if assumption not in self.assumption_accuracy:
            return 0.0
        
        data = self.assumption_accuracy[assumption]
        correct = data.get("correct_count", 0)
        incorrect = data.get("incorrect_count", 0)
        total = correct + incorrect
        
        return correct / total if total > 0 else 0.0
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get a summary of learning data.
        
        Returns:
            Learning summary
        """
        total_scenarios = len(self.scenario_history)
        total_feedbacks = sum(len(feedbacks) for feedbacks in self.scenario_history.values())
        
        scenario_success_rates = [
            self.get_scenario_success_rate(scenario_id)
            for scenario_id in self.scenario_history
        ]
        avg_success_rate = sum(scenario_success_rates) / len(scenario_success_rates) if scenario_success_rates else 0.0
        
        return {
            "total_scenarios_tracked": total_scenarios,
            "total_executions_recorded": total_feedbacks,
            "average_scenario_success_rate": avg_success_rate,
            "total_components_tracked": len(self.component_stability),
            "total_flows_tracked": len(self.flow_reliability),
            "total_assumptions_tracked": len(self.assumption_accuracy),
            "unstable_components": self.get_unstable_components(),
            "unreliable_flows": self.get_unreliable_flows(),
        }
    
    def get_failure_history(self) -> Dict[str, int]:
        """Get aggregated failure history for prioritization.
        
        Returns:
            Dictionary mapping component/flow IDs to failure counts
        """
        failure_history = {}
        
        # Add component failures
        for component_id, stability in self.component_stability.items():
            failure_history[component_id] = stability.get("failure_count", 0)
        
        # Add flow failures
        for flow_id, reliability in self.flow_reliability.items():
            failure_history[flow_id] = reliability.get("failure_count", 0)
        
        return failure_history
