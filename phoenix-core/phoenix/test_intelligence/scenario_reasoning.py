"""Test Scenario Reasoning - AI Test Scenario Pipeline (Priority 23).

This module implements the AI reasoning pipeline for test scenario generation,
integrating semantic understanding, component intelligence, business flows,
and validation intelligence.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
    TestGenerationRequest,
    TestGenerationResponse,
)
from phoenix.semantic.models import (
    SemanticComponent,
    PageType,
    BusinessIntentType,
)
from phoenix.flow_detection.models import (
    BusinessFlow,
)

logger = logging.getLogger(__name__)


class TestScenarioReasoning:
    """AI test scenario reasoning engine.
    
    This engine coordinates the test scenario generation pipeline:
    - User Story / Requirements Understanding
    - Semantic Page Understanding
    - Component Intelligence
    - Business Flow Detection
    - Validation Intelligence
    - Interaction Model
    - AI Test Scenario Reasoning
    - Test Scenarios
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the test scenario reasoning engine."""
        logger.info("[TEST SCENARIO REASONING] Initialized")
    
    def reason_and_generate(
        self,
        request: TestGenerationRequest,
        user_story: str = None,
        requirements: List[str] = None,
        semantic_components: List[SemanticComponent] = None,
        business_flows: List[BusinessFlow] = None,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
        validation_rules: List[Dict[str, Any]] = None,
    ) -> TestGenerationResponse:
        """Reason about the context and generate test scenarios.
        
        Args:
            request: Test generation request
            user_story: User story describing the feature
            requirements: List of requirements
            semantic_components: List of semantic components
            business_flows: List of business flows
            page_type: Current page type
            business_intent: Current business intent
            validation_rules: List of validation rules
            
        Returns:
            Test generation response with reasoned scenarios
        """
        logger.info("[TEST SCENARIO REASONING] Starting reasoning pipeline")
        
        # Build reasoning context
        reasoning_context = self._build_reasoning_context(
            user_story,
            requirements,
            semantic_components,
            business_flows,
            page_type,
            business_intent,
            validation_rules,
        )
        
        # Analyze context for test opportunities
        test_opportunities = self._analyze_test_opportunities(reasoning_context)
        
        # Generate scenarios based on opportunities
        scenarios = self._generate_scenarios_from_opportunities(
            test_opportunities,
            reasoning_context,
            request,
        )
        
        # Enhance scenarios with reasoning
        enhanced_scenarios = self._enhance_scenarios_with_reasoning(
            scenarios,
            reasoning_context,
        )
        
        # Create response
        response = TestGenerationResponse(
            request_id=request.request_id,
            scenarios=enhanced_scenarios,
            total_generated=len(enhanced_scenarios),
        )
        
        logger.info(f"[TEST SCENARIO REASONING] Generated {len(enhanced_scenarios)} reasoned scenarios")
        
        return response
    
    def _build_reasoning_context(
        self,
        user_story: str = None,
        requirements: List[str] = None,
        semantic_components: List[SemanticComponent] = None,
        business_flows: List[BusinessFlow] = None,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
        validation_rules: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the reasoning context from all available information."""
        context = {
            "user_story": user_story or "",
            "requirements": requirements or [],
            "semantic_components": semantic_components or [],
            "business_flows": business_flows or [],
            "page_type": page_type,
            "business_intent": business_intent,
            "validation_rules": validation_rules or [],
        }
        
        # Add derived context
        context["component_count"] = len(semantic_components or [])
        context["flow_count"] = len(business_flows or [])
        context["has_authentication"] = self._has_authentication_flow(business_flows)
        context["has_crud"] = self._has_crud_flows(business_flows)
        context["has_search"] = self._has_search_flows(business_flows)
        context["has_upload"] = self._has_upload_flows(business_flows)
        context["validation_rule_count"] = len(validation_rules or [])
        
        logger.info(f"[TEST SCENARIO REASONING] Built context: {context['component_count']} components, {context['flow_count']} flows")
        
        return context
    
    def _analyze_test_opportunities(
        self,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analyze the context to identify test opportunities."""
        opportunities = []
        
        # Analyze business flows for opportunities
        for flow in context["business_flows"]:
            flow_opportunities = self._analyze_flow_opportunities(flow, context)
            opportunities.extend(flow_opportunities)
        
        # Analyze components for opportunities
        for component in context["semantic_components"]:
            component_opportunities = self._analyze_component_opportunities(component, context)
            opportunities.extend(component_opportunities)
        
        # Analyze validation rules for opportunities
        for rule in context["validation_rules"]:
            validation_opportunities = self._analyze_validation_opportunities(rule, context)
            opportunities.extend(validation_opportunities)
        
        logger.info(f"[TEST SCENARIO REASONING] Identified {len(opportunities)} test opportunities")
        
        return opportunities
    
    def _analyze_flow_opportunities(
        self,
        flow: BusinessFlow,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analyze a business flow for test opportunities."""
        opportunities = []
        
        # Generic flow-based opportunities
        opportunities.append({
            "type": "flow_happy_path",
            "flow_id": flow.flow_id,
            "flow_type": flow.flow_type,
            "scenario_type": "positive",
            "priority": "high",
            "evidence": f"Flow detected: {flow.flow_type}",
        })
        
        opportunities.append({
            "type": "flow_negative",
            "flow_id": flow.flow_id,
            "flow_type": flow.flow_type,
            "scenario_type": "negative",
            "priority": "high",
            "evidence": f"Flow detected: {flow.flow_type}",
        })
        
        # Flow-specific opportunities
        if flow.flow_type.value == "authentication":
            opportunities.append({
                "type": "authentication_security",
                "flow_id": flow.flow_id,
                "scenario_type": "security",
                "priority": "critical",
                "evidence": "Authentication flow detected",
            })
        
        elif flow.flow_type.value in ["crud_create", "crud_update", "crud_delete"]:
            opportunities.append({
                "type": "crud_authorization",
                "flow_id": flow.flow_id,
                "scenario_type": "security",
                "priority": "high",
                "evidence": f"CRUD flow detected: {flow.flow_type}",
            })
        
        return opportunities
    
    def _analyze_component_opportunities(
        self,
        component: SemanticComponent,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analyze a component for test opportunities."""
        opportunities = []
        
        # Validation-based opportunities
        if component.validation_rules:
            for rule in component.validation_rules:
                opportunities.append({
                    "type": "component_validation",
                    "component_id": component.component_id,
                    "validation_type": rule.get("validation_type"),
                    "scenario_type": "validation",
                    "priority": "high",
                    "evidence": f"Validation rule detected: {rule.get('validation_type')}",
                })
        
        # Boundary-based opportunities
        if component.component_type.value in ["text_field", "dropdown"]:
            opportunities.append({
                "type": "component_boundary",
                "component_id": component.component_id,
                "scenario_type": "boundary",
                "priority": "medium",
                "evidence": f"Input component detected: {component.component_type}",
            })
        
        return opportunities
    
    def _analyze_validation_opportunities(
        self,
        rule: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analyze a validation rule for test opportunities."""
        opportunities = []
        
        rule_type = rule.get("validation_type")
        
        opportunities.append({
            "type": "validation_test",
            "validation_type": rule_type,
            "scenario_type": "validation",
            "priority": "high",
            "evidence": f"Validation rule: {rule_type}",
        })
        
        return opportunities
    
    def _generate_scenarios_from_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
        context: Dict[str, Any],
        request: TestGenerationRequest,
    ) -> List[TestScenario]:
        """Generate test scenarios from identified opportunities."""
        scenarios = []
        
        for opportunity in opportunities:
            scenario = self._generate_scenario_from_opportunity(
                opportunity,
                context,
                request,
            )
            if scenario:
                scenarios.append(scenario)
        
        return scenarios
    
    def _generate_scenario_from_opportunity(
        self,
        opportunity: Dict[str, Any],
        context: Dict[str, Any],
        request: TestGenerationRequest,
    ) -> Optional[TestScenario]:
        """Generate a single test scenario from an opportunity."""
        from phoenix.test_intelligence.models import TestScenarioType, TestPriority, TestRisk
        
        scenario_id = f"scenario_{datetime.now(timezone.utc).timestamp()}_{len(opportunity)}"
        
        scenario = TestScenario(
            scenario_id=scenario_id,
            title=self._generate_title_from_opportunity(opportunity),
            scenario_type=self._map_scenario_type(opportunity["scenario_type"]),
            priority=self._map_priority(opportunity["priority"]),
            risk=self._map_risk(opportunity["priority"]),
            purpose=self._generate_purpose_from_opportunity(opportunity),
            business_intent=context["business_intent"].value if context["business_intent"] else "",
            flow=opportunity.get("flow_id", ""),
            source_evidence={"opportunity": opportunity, "context": self._summarize_context(context)},
            confidence_breakdown=self._calculate_confidence_breakdown(opportunity, context),
            related_flows=[opportunity.get("flow_id")] if opportunity.get("flow_id") else [],
            related_components=[opportunity.get("component_id")] if opportunity.get("component_id") else [],
        )
        
        return scenario
    
    def _generate_title_from_opportunity(self, opportunity: Dict[str, Any]) -> str:
        """Generate a scenario title from an opportunity."""
        opp_type = opportunity["type"]
        scenario_type = opportunity["scenario_type"]
        
        if opp_type == "flow_happy_path":
            return f"Verify successful {opportunity.get('flow_type', 'operation')}"
        elif opp_type == "flow_negative":
            return f"Verify {opportunity.get('flow_type', 'operation')} handles errors correctly"
        elif opp_type == "component_validation":
            return f"Verify {opportunity.get('validation_type', 'validation')} for component"
        elif opp_type == "component_boundary":
            return f"Verify boundary conditions for component"
        else:
            return f"Verify {scenario_type} scenario"
    
    def _generate_purpose_from_opportunity(self, opportunity: Dict[str, Any]) -> str:
        """Generate a scenario purpose from an opportunity."""
        return opportunity.get("evidence", "")
    
    def _map_scenario_type(self, scenario_type: str):
        """Map string scenario type to enum."""
        from phoenix.test_intelligence.models import TestScenarioType
        
        type_map = {
            "positive": TestScenarioType.POSITIVE,
            "negative": TestScenarioType.NEGATIVE,
            "boundary": TestScenarioType.BOUNDARY,
            "validation": TestScenarioType.VALIDATION,
            "security": TestScenarioType.SECURITY,
        }
        
        return type_map.get(scenario_type, TestScenarioType.POSITIVE)
    
    def _map_priority(self, priority: str):
        """Map string priority to enum."""
        from phoenix.test_intelligence.models import TestPriority
        
        priority_map = {
            "critical": TestPriority.CRITICAL,
            "high": TestPriority.HIGH,
            "medium": TestPriority.MEDIUM,
            "low": TestPriority.LOW,
        }
        
        return priority_map.get(priority, TestPriority.MEDIUM)
    
    def _map_risk(self, priority: str):
        """Map priority to risk level."""
        from phoenix.test_intelligence.models import TestRisk
        
        risk_map = {
            "critical": TestRisk.CRITICAL,
            "high": TestRisk.HIGH,
            "medium": TestRisk.MEDIUM,
            "low": TestRisk.LOW,
        }
        
        return risk_map.get(priority, TestRisk.MEDIUM)
    
    def _calculate_confidence_breakdown(
        self,
        opportunity: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate confidence breakdown for the scenario."""
        breakdown = {
            "opportunity_evidence": 0.3,
            "context_evidence": 0.3,
            "pattern_evidence": 0.2,
            "reasoning_evidence": 0.2,
        }
        
        # Adjust based on available evidence
        if opportunity.get("flow_id"):
            breakdown["flow_evidence"] = 0.4
            breakdown["opportunity_evidence"] = 0.2
        
        if opportunity.get("component_id"):
            breakdown["component_evidence"] = 0.3
            breakdown["opportunity_evidence"] = 0.2
        
        return breakdown
    
    def _summarize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize the reasoning context."""
        return {
            "component_count": context["component_count"],
            "flow_count": context["flow_count"],
            "page_type": context["page_type"].value if context["page_type"] else None,
            "business_intent": context["business_intent"].value if context["business_intent"] else None,
            "has_authentication": context["has_authentication"],
            "has_crud": context["has_crud"],
        }
    
    def _enhance_scenarios_with_reasoning(
        self,
        scenarios: List[TestScenario],
        context: Dict[str, Any],
    ) -> List[TestScenario]:
        """Enhance scenarios with additional reasoning."""
        for scenario in scenarios:
            # Add confidence based on context richness
            context_score = self._calculate_context_score(context)
            scenario.confidence = min(0.5 + context_score * 0.4, 1.0)
            
            # Add preconditions based on context
            scenario.preconditions = self._generate_preconditions(scenario, context)
            
            # Add initial steps
            if not scenario.steps:
                scenario.steps = self._generate_initial_steps(scenario, context)
        
        return scenarios
    
    def _calculate_context_score(self, context: Dict[str, Any]) -> float:
        """Calculate a score based on context richness."""
        score = 0.0
        
        # Components provide evidence
        score += min(context["component_count"] * 0.05, 0.3)
        
        # Flows provide evidence
        score += min(context["flow_count"] * 0.1, 0.3)
        
        # Validation rules provide evidence
        score += min(context["validation_rule_count"] * 0.05, 0.2)
        
        # Page type and business intent provide evidence
        if context["page_type"]:
            score += 0.1
        if context["business_intent"]:
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_preconditions(
        self,
        scenario: TestScenario,
        context: Dict[str, Any],
    ) -> List[str]:
        """Generate preconditions for a scenario."""
        preconditions = []
        
        # Add generic preconditions
        if context["page_type"]:
            preconditions.append(f"User is on {context['page_type'].value} page")
        
        if context["business_intent"]:
            preconditions.append(f"User has appropriate permissions for {context['business_intent'].value}")
        
        # Add scenario-specific preconditions
        if scenario.scenario_type.value == "positive":
            preconditions.append("System is in normal operating state")
        elif scenario.scenario_type.value == "negative":
            preconditions.append("System is in normal operating state")
        elif scenario.scenario_type.value == "boundary":
            preconditions.append("System is in normal operating state")
        
        return preconditions
    
    def _generate_initial_steps(
        self,
        scenario: TestScenario,
        context: Dict[str, Any],
    ) -> List[str]:
        """Generate initial steps for a scenario."""
        steps = []
        
        # Add navigation step if page type is known
        if context["page_type"]:
            steps.append(f"Navigate to {context['page_type'].value} page")
        
        return steps
    
    def _has_authentication_flow(self, flows: List[BusinessFlow]) -> bool:
        """Check if there's an authentication flow."""
        for flow in flows:
            if flow.flow_type.value == "authentication":
                return True
        return False
    
    def _has_crud_flows(self, flows: List[BusinessFlow]) -> bool:
        """Check if there are CRUD flows."""
        for flow in flows:
            if flow.flow_type.value.startswith("crud_"):
                return True
        return False
    
    def _has_search_flows(self, flows: List[BusinessFlow]) -> bool:
        """Check if there are search flows."""
        for flow in flows:
            if flow.flow_type.value == "search_flow":
                return True
        return False
    
    def _has_upload_flows(self, flows: List[BusinessFlow]) -> bool:
        """Check if there are upload flows."""
        for flow in flows:
            if flow.flow_type.value == "file_upload_flow":
                return True
        return False
