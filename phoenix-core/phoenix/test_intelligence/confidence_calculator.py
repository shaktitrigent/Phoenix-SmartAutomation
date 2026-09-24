"""Confidence Calculator - Test Generation Confidence (Priority 23).

This module calculates confidence scores for generated test scenarios
based on available evidence.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
)

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """Confidence calculator for test scenario generation.
    
    This calculator considers:
    - DOM component evidence
    - Business flow evidence
    - Validation evidence
    - Runtime evidence
    - Semantic understanding evidence
    
    Confidence is based on actual available evidence, not fake values.
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the confidence calculator."""
        self.evidence_weights = self._initialize_evidence_weights()
        logger.info("[CONFIDENCE CALCULATOR] Initialized")
    
    def _initialize_evidence_weights(self) -> Dict[str, float]:
        """Initialize evidence weights for confidence calculation."""
        weights = {
            "dom_component": 0.35,
            "business_flow": 0.30,
            "validation_evidence": 0.20,
            "runtime_evidence": 0.15,
        }
        
        return weights
    
    def calculate_confidence(
        self,
        scenario: TestScenario,
        dom_component_count: int = 0,
        business_flow_count: int = 0,
        validation_rule_count: int = 0,
        runtime_observation_count: int = 0,
    ) -> float:
        """Calculate confidence for a test scenario.
        
        Args:
            scenario: Test scenario to calculate confidence for
            dom_component_count: Number of DOM components available
            business_flow_count: Number of business flows available
            validation_rule_count: Number of validation rules available
            runtime_observation_count: Number of runtime observations available
            
        Returns:
            Confidence score (0-1)
        """
        evidence_scores = {}
        
        # DOM component evidence
        evidence_scores["dom_component"] = self._calculate_dom_evidence_score(
            dom_component_count,
            scenario,
        )
        
        # Business flow evidence
        evidence_scores["business_flow"] = self._calculate_flow_evidence_score(
            business_flow_count,
            scenario,
        )
        
        # Validation evidence
        evidence_scores["validation_evidence"] = self._calculate_validation_evidence_score(
            validation_rule_count,
            scenario,
        )
        
        # Runtime evidence
        evidence_scores["runtime_evidence"] = self._calculate_runtime_evidence_score(
            runtime_observation_count,
            scenario,
        )
        
        # Calculate weighted average
        confidence = 0.0
        total_weight = 0.0
        
        for evidence_type, score in evidence_scores.items():
            weight = self.evidence_weights.get(evidence_type, 0.0)
            confidence += score * weight
            total_weight += weight
        
        confidence = confidence / total_weight if total_weight > 0 else 0.0
        
        # Update scenario confidence breakdown
        scenario.confidence_breakdown = evidence_scores
        scenario.confidence = confidence
        
        logger.debug(f"[CONFIDENCE CALCULATOR] Scenario {scenario.scenario_id}: {confidence:.2f}")
        
        return confidence
    
    def _calculate_dom_evidence_score(
        self,
        component_count: int,
        scenario: TestScenario,
    ) -> float:
        """Calculate DOM component evidence score."""
        if component_count == 0:
            return 0.0
        
        # Base score from component count
        base_score = min(component_count * 0.1, 0.7)
        
        # Bonus if scenario references specific components
        if scenario.related_components:
            component_bonus = min(len(scenario.related_components) * 0.1, 0.3)
        else:
            component_bonus = 0.0
        
        return min(base_score + component_bonus, 1.0)
    
    def _calculate_flow_evidence_score(
        self,
        flow_count: int,
        scenario: TestScenario,
    ) -> float:
        """Calculate business flow evidence score."""
        if flow_count == 0:
            return 0.0
        
        # Base score from flow count
        base_score = min(flow_count * 0.15, 0.7)
        
        # Bonus if scenario references specific flows
        if scenario.related_flows:
            flow_bonus = min(len(scenario.related_flows) * 0.15, 0.3)
        else:
            flow_bonus = 0.0
        
        return min(base_score + flow_bonus, 1.0)
    
    def _calculate_validation_evidence_score(
        self,
        validation_count: int,
        scenario: TestScenario,
    ) -> float:
        """Calculate validation evidence score."""
        if validation_count == 0:
            return 0.0
        
        # Base score from validation count
        base_score = min(validation_count * 0.1, 0.6)
        
        # Bonus if scenario has validation rules
        if scenario.validation_rules:
            validation_bonus = min(len(scenario.validation_rules) * 0.1, 0.4)
        else:
            validation_bonus = 0.0
        
        # Additional bonus for validation scenarios
        if scenario.scenario_type.value == "validation":
            validation_bonus += 0.2
        
        return min(base_score + validation_bonus, 1.0)
    
    def _calculate_runtime_evidence_score(
        self,
        observation_count: int,
        scenario: TestScenario,
    ) -> float:
        """Calculate runtime evidence score."""
        if observation_count == 0:
            return 0.0
        
        # Base score from observation count
        base_score = min(observation_count * 0.05, 0.5)
        
        # Bonus if scenario has runtime evidence in source
        if scenario.source_evidence and "runtime" in str(scenario.source_evidence).lower():
            runtime_bonus = 0.3
        else:
            runtime_bonus = 0.0
        
        return min(base_score + runtime_bonus, 1.0)
    
    def calculate_batch_confidence(
        self,
        scenarios: List[TestScenario],
        dom_component_count: int = 0,
        business_flow_count: int = 0,
        validation_rule_count: int = 0,
        runtime_observation_count: int = 0,
    ) -> Dict[str, Any]:
        """Calculate confidence for multiple scenarios.
        
        Args:
            scenarios: List of test scenarios
            dom_component_count: Number of DOM components available
            business_flow_count: Number of business flows available
            validation_rule_count: Number of validation rules available
            runtime_observation_count: Number of runtime observations available
            
        Returns:
            Dictionary with confidence statistics
        """
        confidences = []
        
        for scenario in scenarios:
            confidence = self.calculate_confidence(
                scenario,
                dom_component_count,
                business_flow_count,
                validation_rule_count,
                runtime_observation_count,
            )
            confidences.append(confidence)
        
        if not confidences:
            return {
                "average": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
            }
        
        return {
            "average": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences),
            "count": len(confidences),
        }
    
    def get_confidence_breakdown_summary(
        self,
        scenarios: List[TestScenario],
    ) -> Dict[str, Dict[str, float]]:
        """Get a summary of confidence breakdowns across scenarios.
        
        Args:
            scenarios: List of test scenarios
            
        Returns:
            Dictionary with average breakdown by evidence type
        """
        if not scenarios:
            return {}
        
        breakdowns = {
            "dom_component": [],
            "business_flow": [],
            "validation_evidence": [],
            "runtime_evidence": [],
        }
        
        for scenario in scenarios:
            if scenario.confidence_breakdown:
                for evidence_type, score in scenario.confidence_breakdown.items():
                    if evidence_type in breakdowns:
                        breakdowns[evidence_type].append(score)
        
        # Calculate averages
        summary = {}
        for evidence_type, scores in breakdowns.items():
            if scores:
                summary[evidence_type] = sum(scores) / len(scores)
            else:
                summary[evidence_type] = 0.0
        
        return summary
