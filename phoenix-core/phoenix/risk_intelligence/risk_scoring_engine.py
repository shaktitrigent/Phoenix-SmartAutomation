"""Risk Scoring Engine - Priority 31.

This module implements evidence-based risk scoring that aggregates multiple
dimensions to provide comprehensive risk assessments.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.risk_intelligence.models import (
    RiskAssessment,
    RiskDimension,
    BusinessCriticality,
    TestPriority,
    ExecutionPolicy,
)

logger = logging.getLogger(__name__)


class RiskScoringEngine:
    """Calculates evidence-based risk scores.
    
    This engine:
    - Aggregates multiple risk dimensions
    - Calculates weighted risk scores
    - Provides evidence breakdown
    - Determines risk levels
    - Maps to test priorities
    - Determines execution policies
    """
    
    def __init__(self):
        """Initialize risk scoring engine."""
        # Risk dimension weights (sum to 1.0)
        self.dimension_weights = {
            "business_criticality": 0.25,
            "change_impact": 0.20,
            "failure_history": 0.15,
            "test_coverage": 0.10,
            "automation_confidence": 0.10,
            "execution_stability": 0.10,
            "locator_stability": 0.05,
            "healing_frequency": 0.05,
        }
        
        logger.info("[RISK SCORING ENGINE] Initialized")
    
    def calculate_risk_assessment(
        self,
        target_id: str,
        target_type: str,
        business_criticality: BusinessCriticality,
        change_impact: Optional[float] = None,
        failure_history: Optional[float] = None,
        test_coverage: Optional[float] = None,
        automation_confidence: Optional[float] = None,
        execution_stability: Optional[float] = None,
        locator_stability: Optional[float] = None,
        healing_frequency: Optional[float] = None,
        additional_evidence: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Calculate comprehensive risk assessment.
        
        Args:
            target_id: ID of target (test, component, or flow)
            target_type: Type of target
            business_criticality: Business criticality
            change_impact: Change impact score (0.0 to 1.0)
            failure_history: Failure history score (0.0 to 1.0)
            test_coverage: Test coverage score (0.0 to 1.0)
            automation_confidence: Automation confidence score (0.0 to 1.0)
            execution_stability: Execution stability score (0.0 to 1.0)
            locator_stability: Locator stability score (0.0 to 1.0)
            healing_frequency: Healing frequency score (0.0 to 1.0)
            additional_evidence: Additional evidence
            
        Returns:
            Comprehensive risk assessment
        """
        logger.info(f"[RISK SCORING] Calculating risk for {target_type}: {target_id}")
        
        # Calculate individual dimensions
        dimensions = []
        
        # Business criticality dimension
        business_score = self._calculate_business_criticality_score(business_criticality)
        dimensions.append(RiskDimension(
            dimension_name="business_criticality",
            score=business_score,
            weight=self.dimension_weights["business_criticality"],
            evidence=[f"Business criticality: {business_criticality.value}"],
            confidence=0.9,
        ))
        
        # Change impact dimension
        if change_impact is not None:
            dimensions.append(RiskDimension(
                dimension_name="change_impact",
                score=change_impact,
                weight=self.dimension_weights["change_impact"],
                evidence=[f"Change impact: {change_impact:.2f}"],
                confidence=0.85,
            ))
        
        # Failure history dimension
        if failure_history is not None:
            dimensions.append(RiskDimension(
                dimension_name="failure_history",
                score=failure_history,
                weight=self.dimension_weights["failure_history"],
                evidence=[f"Failure history: {failure_history:.2f}"],
                confidence=0.8,
            ))
        
        # Test coverage dimension
        if test_coverage is not None:
            # Invert coverage (low coverage = higher risk)
            coverage_risk = 1.0 - test_coverage
            dimensions.append(RiskDimension(
                dimension_name="test_coverage",
                score=coverage_risk,
                weight=self.dimension_weights["test_coverage"],
                evidence=[f"Coverage gap: {coverage_risk:.2f}"],
                confidence=0.75,
            ))
        
        # Automation confidence dimension
        if automation_confidence is not None:
            # Invert confidence (low confidence = higher risk)
            confidence_risk = 1.0 - automation_confidence
            dimensions.append(RiskDimension(
                dimension_name="automation_confidence",
                score=confidence_risk,
                weight=self.dimension_weights["automation_confidence"],
                evidence=[f"Automation confidence risk: {confidence_risk:.2f}"],
                confidence=0.8,
            ))
        
        # Execution stability dimension
        if execution_stability is not None:
            # Invert stability (low stability = higher risk)
            stability_risk = 1.0 - execution_stability
            dimensions.append(RiskDimension(
                dimension_name="execution_stability",
                score=stability_risk,
                weight=self.dimension_weights["execution_stability"],
                evidence=[f"Execution stability risk: {stability_risk:.2f}"],
                confidence=0.85,
            ))
        
        # Locator stability dimension
        if locator_stability is not None:
            # Invert stability (low stability = higher risk)
            locator_risk = 1.0 - locator_stability
            dimensions.append(RiskDimension(
                dimension_name="locator_stability",
                score=locator_risk,
                weight=self.dimension_weights["locator_stability"],
                evidence=[f"Locator stability risk: {locator_risk:.2f}"],
                confidence=0.8,
            ))
        
        # Healing frequency dimension
        if healing_frequency is not None:
            dimensions.append(RiskDimension(
                dimension_name="healing_frequency",
                score=healing_frequency,
                weight=self.dimension_weights["healing_frequency"],
                evidence=[f"Healing frequency: {healing_frequency:.2f}"],
                confidence=0.75,
            ))
        
        # Calculate overall risk score
        overall_risk_score = self._calculate_weighted_risk_score(dimensions)
        
        # Determine risk level
        risk_level = self._determine_risk_level(overall_risk_score)
        
        # Determine test priority
        test_priority = self._determine_test_priority(overall_risk_score, business_criticality)
        
        # Determine execution policy
        execution_policy = self._determine_execution_policy(
            overall_risk_score,
            business_criticality,
            automation_confidence or 1.0,
        )
        
        # Calculate overall confidence
        confidence = self._calculate_overall_confidence(dimensions)
        
        assessment = RiskAssessment(
            assessment_id=f"RISK-{uuid4().hex[:8]}",
            target_id=target_id,
            target_type=target_type,
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            dimensions=dimensions,
            business_criticality=business_criticality,
            test_priority=test_priority,
            execution_policy=execution_policy,
            confidence=confidence,
        )
        
        logger.info(
            f"[RISK SCORING] Risk assessment complete: "
            f"score={overall_risk_score:.1f}, level={risk_level}, "
            f"priority={test_priority.value}, policy={execution_policy.value}"
        )
        
        return assessment
    
    def _calculate_business_criticality_score(
        self,
        criticality: BusinessCriticality,
    ) -> float:
        """Calculate risk score from business criticality.
        
        Args:
            criticality: Business criticality
            
        Returns:
            Risk score (0.0 to 1.0)
        """
        criticality_scores = {
            BusinessCriticality.CRITICAL: 1.0,
            BusinessCriticality.HIGH: 0.75,
            BusinessCriticality.MEDIUM: 0.5,
            BusinessCriticality.LOW: 0.25,
        }
        
        return criticality_scores.get(criticality, 0.5)
    
    def _calculate_weighted_risk_score(
        self,
        dimensions: List[RiskDimension],
    ) -> float:
        """Calculate weighted risk score from dimensions.
        
        Args:
            dimensions: Risk dimensions
            
        Returns:
            Weighted risk score (0.0 to 100.0)
        """
        weighted_sum = 0.0
        total_weight = 0.0
        
        for dimension in dimensions:
            weighted_sum += dimension.score * dimension.weight
            total_weight += dimension.weight
        
        if total_weight == 0:
            return 50.0  # Default medium risk
        
        # Normalize to 0-100 scale
        normalized_score = (weighted_sum / total_weight) * 100
        
        return min(100.0, max(0.0, normalized_score))
    
    def _determine_risk_level(
        self,
        score: float,
    ) -> str:
        """Determine risk level from score.
        
        Args:
            score: Risk score (0.0 to 100.0)
            
        Returns:
            Risk level
        """
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"
    
    def _determine_test_priority(
        self,
        risk_score: float,
        business_criticality: BusinessCriticality,
    ) -> TestPriority:
        """Determine test priority from risk and criticality.
        
        Args:
            risk_score: Risk score
            business_criticality: Business criticality
            
        Returns:
            Test priority
        """
        # Critical business always gets P0
        if business_criticality == BusinessCriticality.CRITICAL:
            return TestPriority.P0
        
        # High risk gets P0 or P1
        if risk_score >= 80:
            return TestPriority.P0
        elif risk_score >= 60:
            return TestPriority.P1
        
        # High business gets P1
        if business_criticality == BusinessCriticality.HIGH:
            return TestPriority.P1
        
        # Medium risk gets P2
        if risk_score >= 40:
            return TestPriority.P2
        
        # Low risk gets P3
        return TestPriority.P3
    
    def _determine_execution_policy(
        self,
        risk_score: float,
        business_criticality: BusinessCriticality,
        automation_confidence: float,
    ) -> ExecutionPolicy:
        """Determine execution policy from risk assessment.
        
        Args:
            risk_score: Risk score
            business_criticality: Business criticality
            automation_confidence: Automation confidence
            
        Returns:
            Execution policy
        """
        # Critical risk + low confidence = human review
        if risk_score >= 80 and automation_confidence < 0.7:
            return ExecutionPolicy.HUMAN_REVIEW
        
        # Critical risk = block or human review
        if risk_score >= 90:
            return ExecutionPolicy.BLOCK_EXECUTION
        elif risk_score >= 80:
            return ExecutionPolicy.HUMAN_REVIEW
        
        # High risk + low confidence = human review
        if risk_score >= 60 and automation_confidence < 0.6:
            return ExecutionPolicy.HUMAN_REVIEW
        
        # High risk = monitor only
        if risk_score >= 60:
            return ExecutionPolicy.MONITOR_ONLY
        
        # Medium risk = autonomous execute
        if risk_score >= 40:
            return ExecutionPolicy.AUTONOMOUS_EXECUTE
        
        # Low risk = autonomous execute
        return ExecutionPolicy.AUTONOMOUS_EXECUTE
    
    def _calculate_overall_confidence(
        self,
        dimensions: List[RiskDimension],
    ) -> float:
        """Calculate overall confidence from dimensions.
        
        Args:
            dimensions: Risk dimensions
            
        Returns:
            Overall confidence (0.0 to 1.0)
        """
        if not dimensions:
            return 0.5
        
        # Average confidence across dimensions
        total_confidence = sum(d.confidence for d in dimensions)
        return total_confidence / len(dimensions)
