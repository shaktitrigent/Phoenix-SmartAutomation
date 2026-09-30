"""Healing Integration - Test Intelligence Healing Integration (Priority 23).

This module integrates test intelligence with the healing engine,
enabling flow-aware and component-aware healing for failed tests.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
    TestHealingContext,
    TestExecutionFeedback,
)

logger = logging.getLogger(__name__)


class TestHealingIntegration:
    """Healing integration for test intelligence.
    
    This integration:
    - Understands test failure context
    - Identifies scenario intent
    - Identifies component and flow context
    - Checks known alternatives from business flows
    - Generates recovery strategies
    - Validates recovery approaches
    
    Healing does NOT blindly change assertions to make tests pass.
    It distinguishes between locator failures, application failures, etc.
    
    Completely generic - no product-specific rules.
"""

    def __init__(self):
        """Initialize the healing integration."""
        logger.info("[TEST HEALING INTEGRATION] Initialized")
    
    def analyze_failure_for_healing(
        self,
        scenario: TestScenario,
        failure_type: str,
        failure_reason: str,
        failing_step_index: int,
        available_components: List[Any] = None,
        available_flows: List[Any] = None,
    ) -> TestHealingContext:
        """Analyze a test failure for healing opportunities.
        
        Args:
            scenario: Test scenario that failed
            failure_type: Type of failure
            failure_reason: Reason for failure
            failing_step_index: Index of the failing step
            available_components: List of available components
            available_flows: List of available flows
            
        Returns:
            Healing context with recovery options
        """
        logger.info(f"[TEST HEALING INTEGRATION] Analyzing failure for scenario {scenario.scenario_id}")
        
        # Determine failure intent
        failure_intent = self._determine_failure_intent(
            scenario,
            failing_step_index,
        )
        
        # Find alternative components
        alternative_components = self._find_alternative_components(
            scenario,
            failing_step_index,
            available_components,
        )
        
        # Find alternative flows
        alternative_flows = self._find_alternative_flows(
            scenario,
            available_flows,
        )
        
        # Generate recovery strategies
        recovery_strategies = self._generate_recovery_strategies(
            failure_type,
            failure_intent,
            alternative_components,
            alternative_flows,
        )
        
        # Calculate recovery confidence
        recovery_confidence = self._calculate_recovery_confidence(
            failure_type,
            alternative_components,
            alternative_flows,
            recovery_strategies,
        )
        
        # Create healing context
        context = TestHealingContext(
            scenario_id=scenario.scenario_id,
            failing_step_index=failing_step_index,
            failure_type=failure_type,
            failure_intent=failure_intent,
            alternative_components=alternative_components,
            alternative_flows=alternative_flows,
            recovery_strategies=recovery_strategies,
            recovery_confidence=recovery_confidence,
        )
        
        logger.info(f"[TEST HEALING INTEGRATION] Generated {len(recovery_strategies)} recovery strategies")
        
        return context
    
    def _determine_failure_intent(
        self,
        scenario: TestScenario,
        failing_step_index: int,
    ) -> str:
        """Determine the intent of the failing step."""
        if failing_step_index < 0 or failing_step_index >= len(scenario.steps):
            return "unknown"
        
        failing_step = scenario.steps[failing_step_index].lower()
        
        # Determine intent from step text
        if "login" in failing_step or "authenticate" in failing_step:
            return "authentication"
        elif "search" in failing_step:
            return "search"
        elif "create" in failing_step or "add" in failing_step:
            return "create"
        elif "edit" in failing_step or "update" in failing_step or "modify" in failing_step:
            return "update"
        elif "delete" in failing_step or "remove" in failing_step:
            return "delete"
        elif "navigate" in failing_step or "go to" in failing_step:
            return "navigation"
        elif "submit" in failing_step or "save" in failing_step:
            return "submission"
        elif "click" in failing_step:
            return "interaction"
        elif "enter" in failing_step or "fill" in failing_step or "type" in failing_step:
            return "data_entry"
        elif "select" in failing_step or "choose" in failing_step:
            return "selection"
        else:
            return "unknown"
    
    def _find_alternative_components(
        self,
        scenario: TestScenario,
        failing_step_index: int,
        available_components: List[Any] = None,
    ) -> List[str]:
        """Find alternative components for the failing step."""
        if not available_components:
            return []
        
        # Get components related to the scenario
        related_component_ids = scenario.related_components
        
        # Find components with similar purposes
        alternatives = []
        
        for component in available_components:
            if hasattr(component, "component_id"):
                component_id = component.component_id
                
                # Don't include the original component
                if component_id in related_component_ids:
                    continue
                
                # Check for similar purpose or type
                if hasattr(component, "semantic_purpose"):
                    for related_id in related_component_ids:
                        # Find the related component
                        related_comp = self._find_component_by_id(
                            available_components,
                            related_id,
                        )
                        if related_comp and hasattr(related_comp, "semantic_purpose"):
                            if component.semantic_purpose == related_comp.semantic_purpose:
                                alternatives.append(component_id)
                                break
        
        return alternatives
    
    def _find_alternative_flows(
        self,
        scenario: TestScenario,
        available_flows: List[Any] = None,
    ) -> List[str]:
        """Find alternative flows for the scenario."""
        if not available_flows:
            return []
        
        # Get flows related to the scenario
        related_flow_ids = scenario.related_flows
        
        # Find flows with similar types
        alternatives = []
        
        for flow in available_flows:
            if hasattr(flow, "flow_id"):
                flow_id = flow.flow_id
                
                # Don't include the original flow
                if flow_id in related_flow_ids:
                    continue
                
                # Check for similar flow type
                if hasattr(flow, "flow_type"):
                    for related_id in related_flow_ids:
                        # Find the related flow
                        related_flow = self._find_flow_by_id(
                            available_flows,
                            related_id,
                        )
                        if related_flow and hasattr(related_flow, "flow_type"):
                            if flow.flow_type == related_flow.flow_type:
                                alternatives.append(flow_id)
                                break
        
        return alternatives
    
    def _generate_recovery_strategies(
        self,
        failure_type: str,
        failure_intent: str,
        alternative_components: List[str],
        alternative_flows: List[str],
    ) -> List[str]:
        """Generate recovery strategies based on failure analysis."""
        strategies = []
        
        # Distinguish failure types
        if failure_type == "locator_failure":
            strategies.append("Try alternative locator strategies")
            if alternative_components:
                strategies.append(f"Try alternative component: {alternative_components[0]}")
            strategies.append("Wait for element to become available")
            strategies.append("Refresh page and retry")
        
        elif failure_type == "application_failure":
            strategies.append("Verify application is in expected state")
            strategies.append("Check for application errors or exceptions")
            strategies.append("Verify preconditions are met")
            if failure_intent in ["authentication", "authorization"]:
                strategies.append("Verify user credentials and permissions")
        
        elif failure_type == "navigation_failure":
            if alternative_flows:
                strategies.append(f"Try alternative flow: {alternative_flows[0]}")
            strategies.append("Verify target page exists")
            strategies.append("Check for navigation restrictions")
        
        elif failure_type == "data_failure":
            strategies.append("Verify test data is valid")
            strategies.append("Check for data constraints")
            strategies.append("Try alternative test data values")
        
        elif failure_type == "assertion_failure":
            strategies.append("Verify expected result is correct")
            strategies.append("Check if application behavior has changed")
            strategies.append("Review if test scenario needs updating")
            strategies.append("Do NOT blindly change assertion - investigate actual behavior")
        
        elif failure_type == "environment_failure":
            strategies.append("Verify environment configuration")
            strategies.append("Check for network or connectivity issues")
            strategies.append("Verify required services are available")
        
        else:
            strategies.append("Investigate failure type")
            strategies.append("Review failure logs for details")
        
        return strategies
    
    def _calculate_recovery_confidence(
        self,
        failure_type: str,
        alternative_components: List[str],
        alternative_flows: List[str],
        recovery_strategies: List[str],
    ) -> float:
        """Calculate confidence in recovery."""
        confidence = 0.0
        
        # Base confidence based on failure type
        if failure_type == "locator_failure":
            confidence += 0.4
        elif failure_type == "navigation_failure":
            confidence += 0.3
        elif failure_type == "data_failure":
            confidence += 0.3
        elif failure_type == "assertion_failure":
            confidence += 0.1  # Low confidence for assertion failures - don't hide real issues
        else:
            confidence += 0.2
        
        # Bonus for alternatives
        if alternative_components:
            confidence += 0.2
        if alternative_flows:
            confidence += 0.2
        
        # Bonus for strategies
        confidence += min(len(recovery_strategies) * 0.05, 0.2)
        
        return min(confidence, 1.0)
    
    def _find_component_by_id(
        self,
        components: List[Any],
        component_id: str,
    ) -> Optional[Any]:
        """Find a component by ID."""
        for component in components:
            if hasattr(component, "component_id") and component.component_id == component_id:
                return component
        return None
    
    def _find_flow_by_id(
        self,
        flows: List[Any],
        flow_id: str,
    ) -> Optional[Any]:
        """Find a flow by ID."""
        for flow in flows:
            if hasattr(flow, "flow_id") and flow.flow_id == flow_id:
                return flow
        return None
    
    def classify_failure_type(
        self,
        failure_reason: str,
        error_message: str = "",
    ) -> str:
        """Classify the type of failure.
        
        Distinguishes between:
        - Locator Failure
        - Application Failure
        - Navigation Failure
        - Data Failure
        - Assertion Failure
        - Environment Failure
        - Test Generation Failure
        
        Args:
            failure_reason: Reason for failure
            error_message: Error message (optional)
            
        Returns:
            Failure type
        """
        failure_text = (failure_reason + " " + error_message).lower()
        
        # Locator failure indicators
        if any(indicator in failure_text for indicator in [
            "element not found",
            "locator",
            "selector",
            "timeout",
            "element click intercepted",
            "element not visible",
        ]):
            return "locator_failure"
        
        # Navigation failure indicators
        if any(indicator in failure_text for indicator in [
            "navigation",
            "redirect",
            "page not found",
            "404",
            "timeout",
        ]):
            return "navigation_failure"
        
        # Assertion failure indicators
        if any(indicator in failure_text for indicator in [
            "assertion",
            "expected",
            "actual",
            "does not match",
        ]):
            return "assertion_failure"
        
        # Data failure indicators
        if any(indicator in failure_text for indicator in [
            "invalid data",
            "data constraint",
            "validation",
            "format",
        ]):
            return "data_failure"
        
        # Environment failure indicators
        if any(indicator in failure_text for indicator in [
            "network",
            "connection",
            "service unavailable",
            "environment",
            "configuration",
        ]):
            return "environment_failure"
        
        # Application failure indicators
        if any(indicator in failure_text for indicator in [
            "error",
            "exception",
            "crash",
            "application",
        ]):
            return "application_failure"
        
        # Default
        return "unknown_failure"
    
    def classify_failure_type(
        self,
        failure_reason: str,
        error_message: str = "",
    ) -> str:
        """Classify the type of failure.
        
        Distinguishes between:
        - Locator Failure
        - Application Failure
        - Navigation Failure
        - Data Failure
        - Assertion Failure
        - Environment Failure
        - Test Generation Failure
        
        Args:
            failure_reason: Reason for failure
            error_message: Error message (optional)
            
        Returns:
            Failure type
        """
        failure_text = (failure_reason + " " + error_message).lower()
        
        # Locator failure indicators
        if any(indicator in failure_text for indicator in [
            "element not found",
            "locator",
            "selector",
            "timeout",
            "element click intercepted",
            "element not visible",
        ]):
            return "locator_failure"
        
        # Navigation failure indicators
        if any(indicator in failure_text for indicator in [
            "navigation",
            "redirect",
            "page not found",
            "404",
            "timeout",
        ]):
            return "navigation_failure"
        
        # Assertion failure indicators
        if any(indicator in failure_text for indicator in [
            "assertion",
            "expected",
            "actual",
            "does not match",
        ]):
            return "assertion_failure"
        
        # Data failure indicators
        if any(indicator in failure_text for indicator in [
            "invalid data",
            "data constraint",
            "validation",
            "format",
        ]):
            return "data_failure"
        
        # Environment failure indicators
        if any(indicator in failure_text for indicator in [
            "network",
            "connection",
            "service unavailable",
            "environment",
            "configuration",
        ]):
            return "environment_failure"
        
        # Application failure indicators
        if any(indicator in failure_text for indicator in [
            "error",
            "exception",
            "crash",
            "application",
        ]):
            return "application_failure"
        
        # Default
        return "unknown_failure"
