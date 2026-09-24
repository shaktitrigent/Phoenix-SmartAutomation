"""Test Prioritizer - Generic Test Prioritization (Priority 23).

This module prioritizes test scenarios based on generic risk and impact
factors, not product-specific rules.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
    TestPriority,
    TestRisk,
)

logger = logging.getLogger(__name__)


class TestPrioritizer:
    """Generic test prioritizer for ANY web application.
    
    This prioritizer considers:
    - Authentication scenarios (critical)
    - Core business flows (high)
    - Data modification (high)
    - Data deletion (critical)
    - Security-sensitive actions (critical)
    - High-risk validations (high)
    - Previously unstable components (based on runtime learning)
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the test prioritizer."""
        self.priority_weights = self._initialize_priority_weights()
        logger.info("[TEST PRIORITIZER] Initialized")
    
    def _initialize_priority_weights(self) -> Dict[str, Dict[str, Any]]:
        """Initialize priority weights for different factors."""
        weights = {
            "authentication": {
                "base_priority": TestPriority.CRITICAL,
                "base_risk": TestRisk.HIGH,
                "weight": 1.0,
            },
            "authorization": {
                "base_priority": TestPriority.CRITICAL,
                "base_risk": TestRisk.HIGH,
                "weight": 1.0,
            },
            "data_deletion": {
                "base_priority": TestPriority.CRITICAL,
                "base_risk": TestRisk.HIGH,
                "weight": 0.9,
            },
            "data_modification": {
                "base_priority": TestPriority.HIGH,
                "base_risk": TestRisk.MEDIUM,
                "weight": 0.8,
            },
            "security": {
                "base_priority": TestPriority.CRITICAL,
                "base_risk": TestRisk.HIGH,
                "weight": 0.95,
            },
            "core_business_flow": {
                "base_priority": TestPriority.HIGH,
                "base_risk": TestRisk.MEDIUM,
                "weight": 0.7,
            },
            "validation": {
                "base_priority": TestPriority.HIGH,
                "base_risk": TestRisk.MEDIUM,
                "weight": 0.6,
            },
            "navigation": {
                "base_priority": TestPriority.MEDIUM,
                "base_risk": TestRisk.LOW,
                "weight": 0.4,
            },
            "search": {
                "base_priority": TestPriority.MEDIUM,
                "base_risk": TestRisk.LOW,
                "weight": 0.4,
            },
            "upload": {
                "base_priority": TestPriority.HIGH,
                "base_risk": TestRisk.MEDIUM,
                "weight": 0.6,
            },
        }
        
        return weights
    
    def prioritize_scenarios(
        self,
        scenarios: List[TestScenario],
        runtime_failure_history: Dict[str, int] = None,
    ) -> List[TestScenario]:
        """Prioritize test scenarios.
        
        Args:
            scenarios: List of test scenarios to prioritize
            runtime_failure_history: History of component failures (component_id -> failure_count)
            
        Returns:
            Prioritized list of test scenarios
        """
        runtime_failure_history = runtime_failure_history or {}
        
        logger.info(f"[TEST PRIORITIZER] Prioritizing {len(scenarios)} scenarios")
        
        # Calculate priority scores for each scenario
        for scenario in scenarios:
            self._calculate_scenario_priority(scenario, runtime_failure_history)
        
        # Sort by priority (critical first, then high, medium, low)
        # Within same priority, sort by risk (critical first)
        # Within same risk, sort by execution cost (lower cost first)
        prioritized = sorted(
            scenarios,
            key=lambda s: (
                self._priority_order(s.priority),
                self._risk_order(s.risk),
                s.execution_cost,
            ),
        )
        
        logger.info(f"[TEST PRIORITIZER] Prioritized scenarios")
        
        return prioritized
    
    def _calculate_scenario_priority(
        self,
        scenario: TestScenario,
        runtime_failure_history: Dict[str, int],
    ):
        """Calculate priority and risk for a scenario."""
        # Determine base priority from scenario type and business intent
        base_priority, base_risk = self._determine_base_priority(scenario)
        
        # Adjust based on runtime failure history
        priority_adjustment = self._calculate_runtime_adjustment(
            scenario,
            runtime_failure_history,
        )
        
        # Apply adjustments
        scenario.priority = self._adjust_priority(base_priority, priority_adjustment)
        scenario.risk = base_risk
        
        # Calculate business impact
        scenario.business_impact = self._calculate_business_impact(scenario)
        
        # Calculate execution cost
        scenario.execution_cost = self._calculate_execution_cost(scenario)
    
    def _determine_base_priority(
        self,
        scenario: TestScenario,
    ) -> tuple[TestPriority, TestRisk]:
        """Determine base priority and risk from scenario characteristics."""
        scenario_type = scenario.scenario_type.value
        business_intent = scenario.business_intent.lower()
        
        # Check for high-priority factors
        if "authentication" in business_intent or "authorization" in business_intent:
            return TestPriority.CRITICAL, TestRisk.HIGH
        
        if scenario_type == "security":
            return TestPriority.CRITICAL, TestRisk.HIGH
        
        if "deletion" in business_intent or "delete" in scenario.title.lower():
            return TestPriority.CRITICAL, TestRisk.HIGH
        
        if scenario_type == "negative" and "unauthorized" in scenario.title.lower():
            return TestPriority.CRITICAL, TestRisk.HIGH
        
        # Check for high-priority factors
        if "modification" in business_intent or "update" in business_intent:
            return TestPriority.HIGH, TestRisk.MEDIUM
        
        if scenario_type == "validation":
            return TestPriority.HIGH, TestRisk.MEDIUM
        
        if scenario_type == "upload":
            return TestPriority.HIGH, TestRisk.MEDIUM
        
        # Check for medium-priority factors
        if scenario_type == "positive":
            return TestPriority.HIGH, TestRisk.LOW
        
        if scenario_type == "boundary":
            return TestPriority.MEDIUM, TestRisk.MEDIUM
        
        if "search" in business_intent:
            return TestPriority.MEDIUM, TestRisk.LOW
        
        if "navigation" in business_intent:
            return TestPriority.MEDIUM, TestRisk.LOW
        
        # Default
        return TestPriority.MEDIUM, TestRisk.MEDIUM
    
    def _calculate_runtime_adjustment(
        self,
        scenario: TestScenario,
        runtime_failure_history: Dict[str, int],
    ) -> float:
        """Calculate priority adjustment based on runtime failure history."""
        adjustment = 0.0
        
        # Check if related components have failure history
        for component_id in scenario.related_components:
            failure_count = runtime_failure_history.get(component_id, 0)
            if failure_count > 0:
                # Increase priority for components that fail often
                adjustment += min(failure_count * 0.1, 0.5)
        
        # Check if related flows have failure history
        for flow_id in scenario.related_flows:
            failure_count = runtime_failure_history.get(flow_id, 0)
            if failure_count > 0:
                # Increase priority for flows that fail often
                adjustment += min(failure_count * 0.1, 0.5)
        
        return adjustment
    
    def _adjust_priority(
        self,
        base_priority: TestPriority,
        adjustment: float,
    ) -> TestPriority:
        """Adjust priority based on runtime adjustments."""
        if adjustment >= 0.5:
            # Significant adjustment - upgrade priority
            if base_priority == TestPriority.LOW:
                return TestPriority.MEDIUM
            elif base_priority == TestPriority.MEDIUM:
                return TestPriority.HIGH
            elif base_priority == TestPriority.HIGH:
                return TestPriority.CRITICAL
        
        return base_priority
    
    def _calculate_business_impact(self, scenario: TestScenario) -> str:
        """Calculate business impact description."""
        if scenario.priority == TestPriority.CRITICAL:
            return "Critical - Failure would block core business operations"
        elif scenario.priority == TestPriority.HIGH:
            return "High - Failure would significantly impact business operations"
        elif scenario.priority == TestPriority.MEDIUM:
            return "Medium - Failure would moderately impact business operations"
        else:
            return "Low - Failure would have minimal business impact"
    
    def _calculate_execution_cost(self, scenario: TestScenario) -> int:
        """Calculate execution cost (1-10)."""
        cost = 1
        
        # More steps = higher cost
        cost += min(len(scenario.steps) * 0.5, 3)
        
        # Complex scenarios = higher cost
        if scenario.scenario_type.value in ["security", "authorization"]:
            cost += 2
        elif scenario.scenario_type.value in ["validation", "boundary"]:
            cost += 1
        
        # Multiple components = higher cost
        cost += min(len(scenario.related_components) * 0.3, 2)
        
        return min(int(cost), 10)
    
    def _priority_order(self, priority: TestPriority) -> int:
        """Get numeric order for priority (lower = higher priority)."""
        order = {
            TestPriority.CRITICAL: 0,
            TestPriority.HIGH: 1,
            TestPriority.MEDIUM: 2,
            TestPriority.LOW: 3,
        }
        return order.get(priority, 2)
    
    def _risk_order(self, risk: TestRisk) -> int:
        """Get numeric order for risk (lower = higher risk)."""
        order = {
            TestRisk.CRITICAL: 0,
            TestRisk.HIGH: 1,
            TestRisk.MEDIUM: 2,
            TestRisk.LOW: 3,
        }
        return order.get(risk, 2)
    
    def get_priority_distribution(
        self,
        scenarios: List[TestScenario],
    ) -> Dict[str, int]:
        """Get distribution of scenarios by priority.
        
        Args:
            scenarios: List of test scenarios
            
        Returns:
            Dictionary with priority counts
        """
        distribution = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        
        for scenario in scenarios:
            distribution[scenario.priority.value] += 1
        
        return distribution
    
    def get_risk_distribution(
        self,
        scenarios: List[TestScenario],
    ) -> Dict[str, int]:
        """Get distribution of scenarios by risk.
        
        Args:
            scenarios: List of test scenarios
            
        Returns:
            Dictionary with risk counts
        """
        distribution = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        
        for scenario in scenarios:
            distribution[scenario.risk.value] += 1
        
        return distribution
