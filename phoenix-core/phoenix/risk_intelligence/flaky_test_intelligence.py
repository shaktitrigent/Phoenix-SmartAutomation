"""Flaky Test Intelligence - Priority 31.

This module detects flaky tests using runtime evidence.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.risk_intelligence.models import (
    FlakyTestAssessment,
    FlakyClassification,
)

logger = logging.getLogger(__name__)


class FlakyTestIntelligence:
    """Detects flaky tests using runtime evidence.
    
    This intelligence:
    - Analyzes pass/fail oscillation
    - Analyzes timing variation
    - Analyzes locator instability
    - Analyzes navigation instability
    - Analyzes intermittent assertions
    - Analyzes retry dependency
    - Analyzes healing dependency
    - Analyzes environment dependency
    - Classifies flakiness
    """
    
    def __init__(self):
        """Initialize flaky test intelligence."""
        self.flaky_assessments: Dict[str, FlakyTestAssessment] = {}
        
        # Flakiness thresholds
        self.thresholds = {
            "oscillation_threshold": 0.5,  # 50% oscillation
            "timing_variation_threshold": 0.3,  # 30% variation
            "instability_threshold": 0.4,  # 40% instability
        }
        
        logger.info("[FLAKY TEST INTELLIGENCE] Initialized")
    
    def assess_flakiness(
        self,
        test_id: str,
        execution_history: List[Dict[str, Any]],
    ) -> FlakyTestAssessment:
        """Assess test flakiness from execution history.
        
        Args:
            test_id: Test ID
            execution_history: Execution history
            
        Returns:
            Flaky test assessment
        """
        logger.info(f"[FLAKY TEST] Assessing flakiness for: {test_id}")
        
        if len(execution_history) < 3:
            # Not enough data to assess
            return self._create_insufficient_data_assessment(test_id)
        
        # Calculate flakiness dimensions
        pass_fail_oscillation = self._calculate_pass_fail_oscillation(execution_history)
        timing_variation = self._calculate_timing_variation(execution_history)
        locator_instability = self._calculate_locator_instability(execution_history)
        navigation_instability = self._calculate_navigation_instability(execution_history)
        intermittent_assertions = self._calculate_intermittent_assertions(execution_history)
        retry_dependency = self._calculate_retry_dependency(execution_history)
        healing_dependency = self._calculate_healing_dependency(execution_history)
        environment_dependency = self._calculate_environment_dependency(execution_history)
        
        # Calculate overall flakiness score
        overall_flakiness = self._calculate_overall_flakiness(
            pass_fail_oscillation,
            timing_variation,
            locator_instability,
            navigation_instability,
            intermittent_assertions,
            retry_dependency,
            healing_dependency,
            environment_dependency,
        )
        
        # Classify flakiness
        classification = self._classify_flakiness(overall_flakiness)
        
        # Generate evidence
        evidence = self._generate_flakiness_evidence(
            pass_fail_oscillation,
            timing_variation,
            locator_instability,
            classification,
        )
        
        # Calculate confidence
        confidence = min(1.0, len(execution_history) / 10.0)
        
        assessment = FlakyTestAssessment(
            assessment_id=f"FLAKY-{uuid4().hex[:8]}",
            test_id=test_id,
            classification=classification,
            pass_fail_oscillation=pass_fail_oscillation,
            timing_variation=timing_variation,
            locator_instability=locator_instability,
            navigation_instability=navigation_instability,
            intermittent_assertions=intermittent_assertions,
            retry_dependency=retry_dependency,
            healing_dependency=healing_dependency,
            environment_dependency=environment_dependency,
            overall_flakiness_score=overall_flakiness,
            evidence=evidence,
            confidence=confidence,
        )
        
        self.flaky_assessments[assessment.assessment_id] = assessment
        
        logger.info(
            f"[FLAKY TEST] Flakiness assessment: {classification.value}, "
            f"score={overall_flakiness:.2f}"
        )
        
        return assessment
    
    def _create_insufficient_data_assessment(
        self,
        test_id: str,
    ) -> FlakyTestAssessment:
        """Create assessment when insufficient data available.
        
        Args:
            test_id: Test ID
            
        Returns:
            Flaky test assessment
        """
        return FlakyTestAssessment(
            assessment_id=f"FLAKY-{uuid4().hex[:8]}",
            test_id=test_id,
            classification=FlakyClassification.STABLE,
            pass_fail_oscillation=0.0,
            timing_variation=0.0,
            locator_instability=0.0,
            navigation_instability=0.0,
            intermittent_assertions=0.0,
            retry_dependency=0.0,
            healing_dependency=0.0,
            environment_dependency=0.0,
            overall_flakiness_score=0.0,
            evidence=["Insufficient execution data for flakiness assessment"],
            confidence=0.3,
        )
    
    def _calculate_pass_fail_oscillation(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate pass/fail oscillation.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Oscillation score (0.0 to 1.0)
        """
        if len(execution_history) < 2:
            return 0.0
        
        results = [e.get("success", True) for e in execution_history]
        
        # Count transitions
        transitions = 0
        for i in range(len(results) - 1):
            if results[i] != results[i + 1]:
                transitions += 1
        
        # Oscillation rate
        oscillation_rate = transitions / (len(results) - 1) if len(results) > 1 else 0.0
        
        return oscillation_rate
    
    def _calculate_timing_variation(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate timing variation.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Timing variation score (0.0 to 1.0)
        """
        execution_times = [e.get("duration_ms", 0) for e in execution_history if e.get("duration_ms", 0) > 0]
        
        if len(execution_times) < 2:
            return 0.0
        
        avg_time = sum(execution_times) / len(execution_times)
        
        # Calculate coefficient of variation
        variance = sum((t - avg_time) ** 2 for t in execution_times) / len(execution_times)
        std_dev = variance ** 0.5
        
        cv = std_dev / avg_time if avg_time > 0 else 0.0
        
        return min(1.0, cv)
    
    def _calculate_locator_instability(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate locator instability.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Locator instability score (0.0 to 1.0)
        """
        healing_count = sum(1 for e in execution_history if e.get("healed", False))
        
        if len(execution_history) == 0:
            return 0.0
        
        return healing_count / len(execution_history)
    
    def _calculate_navigation_instability(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate navigation instability.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Navigation instability score (0.0 to 1.0)
        """
        nav_failures = sum(1 for e in execution_history if e.get("navigation_failed", False))
        
        if len(execution_history) == 0:
            return 0.0
        
        return nav_failures / len(execution_history)
    
    def _calculate_intermittent_assertions(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate intermittent assertion failures.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Intermittent assertion score (0.0 to 1.0)
        """
        assertion_failures = sum(
            1 for e in execution_history
            if e.get("assertion_failed", False) and e.get("success", True)
        )
        
        if len(execution_history) == 0:
            return 0.0
        
        return assertion_failures / len(execution_history)
    
    def _calculate_retry_dependency(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate retry dependency.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Retry dependency score (0.0 to 1.0)
        """
        retry_count = sum(e.get("retry_count", 0) for e in execution_history)
        
        if len(execution_history) == 0:
            return 0.0
        
        return min(1.0, retry_count / len(execution_history))
    
    def _calculate_healing_dependency(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate healing dependency.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Healing dependency score (0.0 to 1.0)
        """
        healing_count = sum(1 for e in execution_history if e.get("healed", False))
        
        if len(execution_history) == 0:
            return 0.0
        
        return healing_count / len(execution_history)
    
    def _calculate_environment_dependency(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> float:
        """Calculate environment dependency.
        
        Args:
            execution_history: Execution history
            
        Returns:
            Environment dependency score (0.0 to 1.0)
        """
        env_failures = sum(1 for e in execution_history if e.get("environment_failure", False))
        
        if len(execution_history) == 0:
            return 0.0
        
        return env_failures / len(execution_history)
    
    def _calculate_overall_flakiness(
        self,
        pass_fail_oscillation: float,
        timing_variation: float,
        locator_instability: float,
        navigation_instability: float,
        intermittent_assertions: float,
        retry_dependency: float,
        healing_dependency: float,
        environment_dependency: float,
    ) -> float:
        """Calculate overall flakiness score.
        
        Args:
            pass_fail_oscillation: Pass/fail oscillation
            timing_variation: Timing variation
            locator_instability: Locator instability
            navigation_instability: Navigation instability
            intermittent_assertions: Intermittent assertions
            retry_dependency: Retry dependency
            healing_dependency: Healing dependency
            environment_dependency: Environment dependency
            
        Returns:
            Overall flakiness score (0.0 to 1.0)
        """
        # Weighted average of dimensions
        weights = {
            "pass_fail_oscillation": 0.35,
            "timing_variation": 0.15,
            "locator_instability": 0.15,
            "navigation_instability": 0.10,
            "intermittent_assertions": 0.10,
            "retry_dependency": 0.05,
            "healing_dependency": 0.05,
            "environment_dependency": 0.05,
        }
        
        weighted_sum = (
            pass_fail_oscillation * weights["pass_fail_oscillation"] +
            timing_variation * weights["timing_variation"] +
            locator_instability * weights["locator_instability"] +
            navigation_instability * weights["navigation_instability"] +
            intermittent_assertions * weights["intermittent_assertions"] +
            retry_dependency * weights["retry_dependency"] +
            healing_dependency * weights["healing_dependency"] +
            environment_dependency * weights["environment_dependency"]
        )
        
        return min(1.0, weighted_sum)
    
    def _classify_flakiness(
        self,
        flakiness_score: float,
    ) -> FlakyClassification:
        """Classify flakiness from score.
        
        Args:
            flakiness_score: Flakiness score
            
        Returns:
            Flaky classification
        """
        if flakiness_score >= 0.8:
            return FlakyClassification.HIGHLY_FLAKY
        elif flakiness_score >= 0.6:
            return FlakyClassification.FLAKY
        elif flakiness_score >= 0.3:
            return FlakyClassification.POSSIBLY_FLAKY
        else:
            return FlakyClassification.STABLE
    
    def _generate_flakiness_evidence(
        self,
        pass_fail_oscillation: float,
        timing_variation: float,
        locator_instability: float,
        classification: FlakyClassification,
    ) -> List[str]:
        """Generate evidence for flakiness assessment.
        
        Args:
            pass_fail_oscillation: Pass/fail oscillation
            timing_variation: Timing variation
            locator_instability: Locator instability
            classification: Flaky classification
            
        Returns:
            Evidence list
        """
        evidence = []
        
        if pass_fail_oscillation > self.thresholds["oscillation_threshold"]:
            evidence.append(f"High pass/fail oscillation: {pass_fail_oscillation:.2f}")
        
        if timing_variation > self.thresholds["timing_variation_threshold"]:
            evidence.append(f"High timing variation: {timing_variation:.2f}")
        
        if locator_instability > self.thresholds["instability_threshold"]:
            evidence.append(f"High locator instability: {locator_instability:.2f}")
        
        evidence.append(f"Classification: {classification.value}")
        
        return evidence
