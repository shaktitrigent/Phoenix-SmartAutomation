"""Universal Automation Planner - Converts test scenarios to executable automation plans.

This module implements a generic automation planner that converts validated
Priority 23 test scenarios into executable automation plans with evidence-based
confidence scoring.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.automation_generation.models import (
    AutomationPlan,
    AutomationStatus,
    Action,
    ActionType,
    Assertion,
    AssertionType,
    TestDataRequirement,
    TestDataType,
)
from phoenix.test_intelligence.models import TestScenario
from phoenix.semantic.models import SemanticComponent
from phoenix.flow_detection.models import BusinessFlow

logger = logging.getLogger(__name__)


class AutomationPlanner:
    """Universal automation planner for converting test scenarios to executable plans.
    
    This planner:
    - Converts validated test scenarios into automation plans
    - Identifies required pages and components
    - Maps semantic actions to executable actions
    - Determines test data requirements
    - Generates evidence-based assertions
    - Calculates plan confidence
    - Validates plan completeness
    """
    
    def __init__(
        self,
        components: Optional[List[SemanticComponent]] = None,
        flows: Optional[List[BusinessFlow]] = None,
    ):
        self.components = components or []
        self.flows = flows or []
        self.component_map = {c.component_id: c for c in self.components}
        self.flow_map = {f.flow_id: f for f in self.flows}
        
        logger.info(
            f"AutomationPlanner initialized with {len(self.components)} components "
            f"and {len(self.flows)} flows"
        )
    
    def create_automation_plan(
        self,
        scenario: TestScenario,
        available_components: Optional[List[SemanticComponent]] = None,
        available_flows: Optional[List[BusinessFlow]] = None,
    ) -> Optional[AutomationPlan]:
        """Create an automation plan from a validated test scenario.
        
        Args:
            scenario: Validated test scenario from Priority 23
            available_components: Available semantic components
            available_flows: Available business flows
            
        Returns:
            AutomationPlan if successful, None if insufficient evidence
        """
        if not scenario.is_validated:
            logger.warning(f"Scenario {scenario.scenario_id} not validated, skipping plan creation")
            return None
        
        if scenario.quality_score < 70.0:
            logger.warning(
                f"Scenario {scenario.scenario_id} quality score too low "
                f"({scenario.quality_score}), skipping plan creation"
            )
            return None
        
        # Update available components and flows
        if available_components:
            self.components = available_components
            self.component_map = {c.component_id: c for c in self.components}
        
        if available_flows:
            self.flows = available_flows
            self.flow_map = {f.flow_id: f for f in self.flows}
        
        # Create automation plan
        automation_id = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
        
        plan = AutomationPlan(
            scenario_id=scenario.scenario_id,
            automation_id=automation_id,
            business_intent=scenario.business_intent,
            preconditions=scenario.preconditions,
            confidence=scenario.confidence,
            evidence=scenario.source_evidence.copy(),
        )
        
        # Identify required pages
        plan.required_pages = self._identify_required_pages(scenario)
        
        # Identify required components
        plan.required_components = self._identify_required_components(scenario)
        
        # Plan actions from scenario steps
        plan.actions = self._plan_actions(scenario)
        
        # Plan locators
        plan.locators = self._plan_locators(scenario, plan.required_components)
        
        # Identify test data requirements
        test_data_reqs = self._identify_test_data_requirements(scenario, plan.required_components)
        plan.test_data = {req.data_id: req for req in test_data_reqs}
        
        # Plan assertions
        plan.assertions = self._plan_assertions(scenario, plan.required_components)
        
        # Plan navigation
        plan.navigation_steps = self._plan_navigation(scenario)
        
        # Expected outcomes
        plan.expected_outcomes = [scenario.expected_result] if scenario.expected_result else []
        
        # Recovery strategy
        plan.recovery_strategy = self._determine_recovery_strategy(scenario)
        
        # Validate plan completeness
        if not self._validate_plan_completeness(plan):
            logger.warning(f"Plan {automation_id} incomplete, rejecting")
            plan.status = AutomationStatus.REJECTED
            return plan
        
        # Recalculate confidence based on plan completeness
        plan.confidence = self._calculate_plan_confidence(plan, scenario)
        
        plan.status = AutomationStatus.PLANNED
        
        logger.info(
            f"Created automation plan {automation_id} for scenario {scenario.scenario_id} "
            f"with confidence {plan.confidence:.2f}"
        )
        
        return plan
    
    def _identify_required_pages(self, scenario: TestScenario) -> List[str]:
        """Identify required page objects from scenario."""
        pages = set()
        
        # Extract from flow
        if scenario.flow:
            flow = self.flow_map.get(scenario.flow)
            if flow:
                for node in flow.nodes:
                    if node.page_type:
                        pages.add(f"{node.page_type}_page")
        
        # Extract from business intent
        if scenario.business_intent:
            intent_lower = scenario.business_intent.lower()
            if "authentication" in intent_lower or "login" in intent_lower:
                pages.add("authentication_screen")
            if "dashboard" in intent_lower:
                pages.add("dashboard")
            if "search" in intent_lower:
                pages.add("search_screen")
        
        # Extract from preconditions
        for precondition in scenario.preconditions:
            if "dashboard" in precondition.lower():
                pages.add("dashboard")
            if "logged in" in precondition.lower():
                pages.add("authentication_screen")
        
        return list(pages) if pages else ["unknown"]
    
    def _identify_required_components(self, scenario: TestScenario) -> List[str]:
        """Identify required component IDs from scenario."""
        components = set()
        
        # Extract from related components
        components.update(scenario.related_components)
        
        # Extract from steps by looking for component references
        for step in scenario.steps:
            # Look for component IDs mentioned in steps
            for comp_id, comp in self.component_map.items():
                if comp.text_content and comp.text_content.lower() in step.lower():
                    components.add(comp_id)
                if comp.label and comp.label.lower() in step.lower():
                    components.add(comp_id)
        
        return list(components)
    
    def _plan_actions(self, scenario: TestScenario) -> List[Dict[str, Any]]:
        """Plan executable actions from scenario steps."""
        actions = []
        
        for step_idx, step in enumerate(scenario.steps):
            action = self._plan_single_action(step, step_idx)
            if action:
                actions.append(action)
        
        return actions
    
    def _plan_single_action(self, step: str, step_idx: int) -> Optional[Dict[str, Any]]:
        """Plan a single action from a step description."""
        step_lower = step.lower()
        
        action = {
            "action_id": f"ACT-{step_idx:03d}",
            "step_description": step,
            "action_type": None,
            "target_component_id": "",
            "parameters": {},
            "confidence": 0.0,
            "evidence": [],
        }
        
        # Determine action type from step semantics
        if any(word in step_lower for word in ["navigate", "go to", "visit", "open"]):
            action["action_type"] = str(ActionType.NAVIGATE)
            action["confidence"] = 0.9
            action["evidence"].append("Navigation keywords detected")
        
        elif any(word in step_lower for word in ["click", "select", "choose", "press"]):
            action["action_type"] = str(ActionType.CLICK)
            action["confidence"] = 0.85
            action["evidence"].append("Click action keywords detected")
        
        elif any(word in step_lower for word in ["enter", "type", "fill", "input"]):
            action["action_type"] = str(ActionType.FILL)
            action["confidence"] = 0.85
            action["evidence"].append("Fill action keywords detected")
        
        elif any(word in step_lower for word in ["select", "choose", "pick"]):
            action["action_type"] = str(ActionType.SELECT)
            action["confidence"] = 0.8
            action["evidence"].append("Select action keywords detected")
        
        elif any(word in step_lower for word in ["check", "tick"]):
            action["action_type"] = str(ActionType.CHECK)
            action["confidence"] = 0.9
            action["evidence"].append("Check action keywords detected")
        
        elif any(word in step_lower for word in ["uncheck", "untick"]):
            action["action_type"] = str(ActionType.UNCHECK)
            action["confidence"] = 0.9
            action["evidence"].append("Uncheck action keywords detected")
        
        elif any(word in step_lower for word in ["upload", "attach"]):
            action["action_type"] = str(ActionType.UPLOAD)
            action["confidence"] = 0.85
            action["evidence"].append("Upload action keywords detected")
        
        elif any(word in step_lower for word in ["submit", "save", "confirm"]):
            action["action_type"] = str(ActionType.SUBMIT)
            action["confidence"] = 0.85
            action["evidence"].append("Submit action keywords detected")
        
        elif any(word in step_lower for word in ["wait", "pause"]):
            action["action_type"] = str(ActionType.WAIT)
            action["confidence"] = 0.7
            action["evidence"].append("Wait action keywords detected")
        
        elif any(word in step_lower for word in ["search", "find"]):
            action["action_type"] = str(ActionType.SEARCH)
            action["confidence"] = 0.85
            action["evidence"].append("Search action keywords detected")
        
        elif any(word in step_lower for word in ["verify", "assert", "check", "ensure"]):
            action["action_type"] = str(ActionType.ASSERT)
            action["confidence"] = 0.8
            action["evidence"].append("Assertion keywords detected")
        
        else:
            # Default to click for interactive elements
            action["action_type"] = str(ActionType.CLICK)
            action["confidence"] = 0.5
            action["evidence"].append("Default action type")
        
        return action if action["action_type"] else None
    
    def _plan_locators(
        self,
        scenario: TestScenario,
        required_components: List[str],
    ) -> Dict[str, str]:
        """Plan locators for required components."""
        locators = {}
        
        for comp_id in required_components:
            component = self.component_map.get(comp_id)
            if component and component.selected_locator:
                locators[comp_id] = component.selected_locator
            elif component and component.locator_candidates:
                # Use highest confidence locator
                best_candidate = max(
                    component.locator_candidates,
                    key=lambda x: x.get("confidence", 0.0),
                )
                locators[comp_id] = best_candidate.get("locator", "")
        
        return locators
    
    def _identify_test_data_requirements(
        self,
        scenario: TestScenario,
        required_components: List[str],
    ) -> List[TestDataRequirement]:
        """Identify test data requirements from scenario and components."""
        requirements = []
        
        # Extract from scenario test data
        for key, value in scenario.test_data.items():
            data_type = self._infer_data_type(key, value)
            req = TestDataRequirement(
                data_id=f"DATA-{uuid.uuid4().hex[:8].upper()}",
                data_type=data_type,
                field_name=key,
                is_required=True,
                provided_value=value,
                is_missing=False,
                source="scenario",
            )
            requirements.append(req)
        
        # Extract from components
        for comp_id in required_components:
            component = self.component_map.get(comp_id)
            if component:
                # Check for username field
                if component.semantic_purpose == "username_input":
                    req = TestDataRequirement(
                        data_id=f"DATA-{uuid.uuid4().hex[:8].upper()}",
                        data_type=TestDataType.USERNAME,
                        field_name="username",
                        is_required=component.is_required,
                        is_missing=True,
                        source="component_analysis",
                    )
                    requirements.append(req)
                
                # Check for password field
                elif component.semantic_purpose == "password_input":
                    req = TestDataRequirement(
                        data_id=f"DATA-{uuid.uuid4().hex[:8].upper()}",
                        data_type=TestDataType.PASSWORD,
                        field_name="password",
                        is_required=component.is_required,
                        is_missing=True,
                        is_sensitive=True,
                        source="component_analysis",
                    )
                    requirements.append(req)
                
                # Check for email field
                elif "email" in component.label.lower() or "email" in component.placeholder.lower():
                    req = TestDataRequirement(
                        data_id=f"DATA-{uuid.uuid4().hex[:8].upper()}",
                        data_type=TestDataType.EMAIL,
                        field_name="email",
                        is_required=component.is_required,
                        is_missing=True,
                        source="component_analysis",
                    )
                    requirements.append(req)
        
        return requirements
    
    def _infer_data_type(self, key: str, value: Any) -> TestDataType:
        """Infer data type from key and value."""
        key_lower = key.lower()
        
        if "username" in key_lower or "user" in key_lower:
            return TestDataType.USERNAME
        elif "password" in key_lower or "pass" in key_lower:
            return TestDataType.PASSWORD
        elif "email" in key_lower:
            return TestDataType.EMAIL
        elif "phone" in key_lower:
            return TestDataType.PHONE
        elif "name" in key_lower:
            return TestDataType.NAME
        elif "date" in key_lower:
            return TestDataType.DATE
        elif isinstance(value, (int, float)):
            return TestDataType.NUMBER
        elif isinstance(value, bool):
            return TestDataType.BOOLEAN
        else:
            return TestDataType.TEXT
    
    def _plan_assertions(
        self,
        scenario: TestScenario,
        required_components: List[str],
    ) -> List[Dict[str, Any]]:
        """Plan assertions from scenario."""
        assertions = []
        
        # Add expected result as assertion
        if scenario.expected_result:
            assertion = {
                "assertion_id": f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                "assertion_type": str(AssertionType.VISIBLE_TEXT),
                "expected_value": scenario.expected_result,
                "comparison_type": "contains",
                "confidence": 0.8,
                "evidence": ["From scenario expected result"],
            }
            assertions.append(assertion)
        
        # Add validation rule assertions
        for rule in scenario.validation_rules:
            assertion = {
                "assertion_id": f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                "assertion_type": str(AssertionType.VALIDATION_MESSAGE),
                "expected_value": rule,
                "comparison_type": "equals",
                "confidence": 0.75,
                "evidence": ["From scenario validation rules"],
            }
            assertions.append(assertion)
        
        return assertions
    
    def _plan_navigation(self, scenario: TestScenario) -> List[Dict[str, Any]]:
        """Plan navigation steps from scenario.
        
        CRITICAL FIX: Never infer URLs from business intent.
        Navigation should only be based on explicit navigation requirements
        in the scenario, not assumed from intent like "login".
        """
        navigation = []
        
        # CRITICAL FIX: Removed automatic navigate_to_login generation
        # Business intent like "login" does NOT imply a specific URL path
        # The application start URL should be configured externally
        # Login components will be detected from DOM at runtime
        
        # Check if navigation is mentioned in preconditions
        for precondition in scenario.preconditions:
            if "navigate" in precondition.lower() or "go to" in precondition.lower():
                navigation.append({
                    "step": "navigate",
                    "target": precondition,
                    "confidence": 0.7,
                })
        
        return navigation
    
    def _determine_recovery_strategy(self, scenario: TestScenario) -> str:
        """Determine recovery strategy based on scenario characteristics."""
        # Handle both enum and string values for risk
        risk_value = scenario.risk.value if hasattr(scenario.risk, 'value') else scenario.risk
        if risk_value in ["critical", "high"]:
            return "healing_with_manual_review"
        elif scenario.confidence < 0.7:
            return "conservative_retry"
        else:
            return "standard_healing"
    
    def _validate_plan_completeness(self, plan: AutomationPlan) -> bool:
        """Validate that the plan has all required elements."""
        if not plan.actions:
            logger.warning("Plan has no actions")
            return False
        
        if not plan.assertions and plan.business_intent not in ["navigation", "data_entry"]:
            logger.warning("Plan has no assertions for non-navigation scenario")
            return False
        
        # Check for missing critical test data
        missing_critical = [
            req for req in plan.test_data.values()
            if req.is_required and req.is_missing and req.is_sensitive
        ]
        if missing_critical:
            logger.warning(f"Plan missing {len(missing_critical)} critical test data requirements")
            return False
        
        return True
    
    def _calculate_plan_confidence(
        self,
        plan: AutomationPlan,
        scenario: TestScenario,
    ) -> float:
        """Calculate overall plan confidence from multiple factors."""
        weights = {
            "scenario_confidence": 0.3,
            "action_confidence": 0.25,
            "locator_confidence": 0.2,
            "assertion_confidence": 0.15,
            "data_completeness": 0.1,
        }
        
        # Scenario confidence
        scenario_conf = scenario.confidence
        
        # Average action confidence
        action_confs = [a.get("confidence", 0.0) for a in plan.actions]
        action_conf = sum(action_confs) / len(action_confs) if action_confs else 0.0
        
        # Locator confidence
        locator_confs = []
        for comp_id in plan.required_components:
            component = self.component_map.get(comp_id)
            if component:
                locator_confs.append(component.locator_confidence)
        locator_conf = sum(locator_confs) / len(locator_confs) if locator_confs else 0.5
        
        # Assertion confidence
        assertion_confs = [a.get("confidence", 0.0) for a in plan.assertions]
        assertion_conf = sum(assertion_confs) / len(assertion_confs) if assertion_confs else 0.5
        
        # Data completeness
        missing_data = sum(1 for req in plan.test_data.values() if req.is_missing)
        total_data = len(plan.test_data) if plan.test_data else 1
        data_completeness = 1.0 - (missing_data / total_data)
        
        # Weighted average
        overall_confidence = (
            weights["scenario_confidence"] * scenario_conf +
            weights["action_confidence"] * action_conf +
            weights["locator_confidence"] * locator_conf +
            weights["assertion_confidence"] * assertion_conf +
            weights["data_completeness"] * data_completeness
        )
        
        return min(max(overall_confidence, 0.0), 1.0)
    
    def batch_create_plans(
        self,
        scenarios: List[TestScenario],
        available_components: Optional[List[SemanticComponent]] = None,
        available_flows: Optional[List[BusinessFlow]] = None,
    ) -> List[AutomationPlan]:
        """Create automation plans for multiple scenarios."""
        plans = []
        
        for scenario in scenarios:
            plan = self.create_automation_plan(
                scenario,
                available_components,
                available_flows,
            )
            if plan and plan.status != AutomationStatus.REJECTED:
                plans.append(plan)
        
        logger.info(
            f"Created {len(plans)} automation plans from {len(scenarios)} scenarios "
            f"({len(scenarios) - len(plans)} rejected)"
        )
        
        return plans
