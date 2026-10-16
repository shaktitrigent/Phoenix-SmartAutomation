"""Impact Analyzer - Priority 29.

This module analyzes the impact of detected changes on existing tests,
automations, and other artifacts.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.change_intelligence.models import (
    SemanticChange,
    ImpactAnalysis,
    MaintenanceAction,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """Analyzes the impact of changes on tests and automations.
    
    This analyzer:
    - Determines affected components
    - Determines affected flows
    - Determines affected scenarios
    - Determines affected automations
    - Calculates risk scores
    - Recommends maintenance actions
    """
    
    def __init__(self):
        """Initialize impact analyzer."""
        self.knowledge_base: Dict[str, Any] = {}
        
        logger.info("[IMPACT ANALYZER] Initialized")
    
    def analyze_impact(
        self,
        change: SemanticChange,
        existing_components: List[Dict[str, Any]],
        existing_flows: List[Dict[str, Any]],
        existing_scenarios: List[Dict[str, Any]],
        existing_automations: List[Dict[str, Any]],
    ) -> ImpactAnalysis:
        """Analyze the impact of a change.
        
        Args:
            change: Detected change
            existing_components: Existing components
            existing_flows: Existing flows
            existing_scenarios: Existing scenarios
            existing_automations: Existing automations
            
        Returns:
            Impact analysis
        """
        logger.info(f"[IMPACT ANALYZER] Analyzing impact for change: {change.change_id}")
        
        # Determine affected components
        affected_components = self._find_affected_components(
            change,
            existing_components,
        )
        
        # Determine affected flows
        affected_flows = self._find_affected_flows(
            change,
            existing_flows,
        )
        
        # Determine affected scenarios
        affected_scenarios = self._find_affected_scenarios(
            change,
            existing_scenarios,
        )
        
        # Determine affected automations
        affected_automations = self._find_affected_automations(
            change,
            existing_automations,
        )
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(
            change,
            affected_components,
            affected_flows,
            affected_scenarios,
            affected_automations,
        )
        
        # Recommend maintenance action
        recommended_action = self._recommend_action(
            change,
            risk_score,
            affected_automations,
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            change,
            affected_components,
            affected_flows,
        )
        
        analysis = ImpactAnalysis(
            analysis_id=f"IMPACT-{uuid4().hex[:8]}",
            change_id=change.change_id,
            affected_components=affected_components,
            affected_flows=affected_flows,
            affected_scenarios=affected_scenarios,
            affected_automations=affected_automations,
            affected_page_objects=[],  # Will be populated if POM intelligence is integrated
            affected_locators=[],  # Will be populated if locator intelligence is integrated
            risk_score=risk_score,
            recommended_action=recommended_action,
            confidence=confidence,
        )
        
        logger.info(f"[IMPACT ANALYZER] Impact analysis complete:")
        logger.info(f"  Affected components: {len(affected_components)}")
        logger.info(f"  Affected flows: {len(affected_flows)}")
        logger.info(f"  Affected scenarios: {len(affected_scenarios)}")
        logger.info(f"  Affected automations: {len(affected_automations)}")
        logger.info(f"  Risk score: {risk_score}")
        logger.info(f"  Recommended action: {recommended_action.value}")
        
        return analysis
    
    def _find_affected_components(
        self,
        change: SemanticChange,
        existing_components: List[Dict[str, Any]],
    ) -> List[str]:
        """Find components affected by the change.
        
        Args:
            change: Detected change
            existing_components: Existing components
            
        Returns:
            List of affected component IDs
        """
        affected = []
        
        change_component_id = change.current_state.get("id", "")
        change_component_tag = change.current_state.get("tag", "")
        
        for component in existing_components:
            comp_id = component.get("id", "")
            comp_tag = component.get("tag", "")
            
            # Direct match
            if comp_id == change_component_id:
                affected.append(comp_id)
            # Tag match
            elif comp_tag == change_component_tag:
                affected.append(comp_id)
        
        return affected
    
    def _find_affected_flows(
        self,
        change: SemanticChange,
        existing_flows: List[Dict[str, Any]],
    ) -> List[str]:
        """Find flows affected by the change.
        
        Args:
            change: Detected change
            existing_flows: Existing flows
            
        Returns:
            List of affected flow IDs
        """
        affected = []
        
        for flow in existing_flows:
            flow_components = flow.get("components", [])
            change_component_id = change.current_state.get("id", "")
            
            # Check if flow uses affected component
            if change_component_id in flow_components:
                affected.append(flow.get("flow_id", ""))
        
        return affected
    
    def _find_affected_scenarios(
        self,
        change: SemanticChange,
        existing_scenarios: List[Dict[str, Any]],
    ) -> List[str]:
        """Find scenarios affected by the change.
        
        Args:
            change: Detected change
            existing_scenarios: Existing scenarios
            
        Returns:
            List of affected scenario IDs
        """
        affected = []
        
        for scenario in existing_scenarios:
            scenario_components = scenario.get("components", [])
            change_component_id = change.current_state.get("id", "")
            
            # Check if scenario uses affected component
            if change_component_id in scenario_components:
                affected.append(scenario.get("scenario_id", ""))
        
        return affected
    
    def _find_affected_automations(
        self,
        change: SemanticChange,
        existing_automations: List[Dict[str, Any]],
    ) -> List[str]:
        """Find automations affected by the change.
        
        Args:
            change: Detected change
            existing_automations: Existing automations
            
        Returns:
            List of affected automation IDs
        """
        affected = []
        
        for automation in existing_automations:
            automation_actions = automation.get("actions", [])
            change_component_id = change.current_state.get("id", "")
            
            # Check if automation uses affected component
            for action in automation_actions:
                if action.get("target", "") == change_component_id:
                    affected.append(automation.get("automation_id", ""))
                    break
        
        return affected
    
    def _calculate_risk_score(
        self,
        change: SemanticChange,
        affected_components: List[str],
        affected_flows: List[str],
        affected_scenarios: List[str],
        affected_automations: List[str],
    ) -> float:
        """Calculate risk score for the change.
        
        Args:
            change: Detected change
            affected_components: Affected components
            affected_flows: Affected flows
            affected_scenarios: Affected scenarios
            affected_automations: Affected automations
            
        Returns:
            Risk score (0-1)
        """
        # Base risk from change severity
        severity_scores = {
            "safe": 0.1,
            "minor": 0.3,
            "significant": 0.6,
            "critical": 0.9,
        }
        base_risk = severity_scores.get(change.severity.value, 0.5)
        
        # Increase risk based on impact
        impact_multiplier = 1.0
        
        if len(affected_flows) > 0:
            impact_multiplier += 0.2
        
        if len(affected_scenarios) > 0:
            impact_multiplier += 0.15
        
        if len(affected_automations) > 0:
            impact_multiplier += 0.1
        
        # Calculate final risk score
        risk_score = min(base_risk * impact_multiplier, 1.0)
        
        return risk_score
    
    def _recommend_action(
        self,
        change: SemanticChange,
        risk_score: float,
        affected_automations: List[str],
    ) -> MaintenanceAction:
        """Recommend maintenance action based on change and risk.
        
        Args:
            change: Detected change
            risk_score: Calculated risk score
            affected_automations: Affected automations
            
        Returns:
            Recommended maintenance action
        """
        # Locator changes
        if change.change_type.value == "locator_changed":
            return MaintenanceAction.REPAIR_LOCATOR
        
        # Component removed
        if change.change_type.value == "component_removed":
            if risk_score > 0.7:
                return MaintenanceAction.REGENERATE_TEST
            else:
                return MaintenanceAction.REGENERATE_TEST_STEP
        
        # Component added
        if change.change_type.value == "component_added":
            return MaintenanceAction.CREATE_NEW_TEST
        
        # Flow changed
        if change.change_type.value.startswith("flow_"):
            if risk_score > 0.8:
                return MaintenanceAction.REGENERATE_FLOW
            else:
                return MaintenanceAction.REVALIDATE
        
        # High risk changes
        if risk_score > 0.8:
            return MaintenanceAction.REQUEST_HUMAN_REVIEW
        
        # Medium risk changes
        if risk_score > 0.5:
            return MaintenanceAction.REGENERATE_ACTION
        
        # Low risk changes
        return MaintenanceAction.REVALIDATE
    
    def _calculate_confidence(
        self,
        change: SemanticChange,
        affected_components: List[str],
        affected_flows: List[str],
    ) -> float:
        """Calculate confidence in impact analysis.
        
        Args:
            change: Detected change
            affected_components: Affected components
            affected_flows: Affected flows
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence from change detection
        base_confidence = change.confidence
        
        # Increase confidence if we found affected items
        if len(affected_components) > 0:
            base_confidence += 0.1
        
        if len(affected_flows) > 0:
            base_confidence += 0.1
        
        # Cap at 1.0
        return min(base_confidence, 1.0)
