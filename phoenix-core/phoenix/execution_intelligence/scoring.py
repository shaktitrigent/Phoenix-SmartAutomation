"""Execution Intelligence Scorer - Evidence-based scoring.

This module implements evidence-based execution intelligence scoring that
calculates a comprehensive score from multiple dimensions.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import ExecutionIntelligenceScore

logger = logging.getLogger(__name__)


class ExecutionIntelligenceScorer:
    """Execution intelligence scorer for evidence-based scoring.
    
    Calculates score from dimensions:
    - Locator Confidence
    - DOM Confidence
    - Semantic Confidence
    - Flow Confidence
    - Action Confidence
    - Assertion Confidence
    - Runtime Stability
    - Healing Confidence
    
    Every score must have explainable evidence.
    """
    
    def __init__(self):
        logger.info("ExecutionIntelligenceScorer initialized")
    
    def calculate_score(
        self,
        execution_id: str,
        execution_evidence: Dict[str, Any],
    ) -> ExecutionIntelligenceScore:
        """Calculate execution intelligence score.
        
        Args:
            execution_id: Execution identifier
            execution_evidence: Complete execution evidence
            
        Returns:
            ExecutionIntelligenceScore with component scores
        """
        score_id = f"SCORE-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate component scores
        locator_confidence = self._calculate_locator_confidence(execution_evidence)
        dom_confidence = self._calculate_dom_confidence(execution_evidence)
        semantic_confidence = self._calculate_semantic_confidence(execution_evidence)
        flow_confidence = self._calculate_flow_confidence(execution_evidence)
        action_confidence = self._calculate_action_confidence(execution_evidence)
        assertion_confidence = self._calculate_assertion_confidence(execution_evidence)
        runtime_stability = self._calculate_runtime_stability(execution_evidence)
        healing_confidence = self._calculate_healing_confidence(execution_evidence)
        
        # Calculate overall score (weighted average)
        weights = {
            "locator": 0.15,
            "dom": 0.10,
            "semantic": 0.15,
            "flow": 0.10,
            "action": 0.15,
            "assertion": 0.10,
            "stability": 0.15,
            "healing": 0.10,
        }
        
        overall_score = (
            locator_confidence * weights["locator"] +
            dom_confidence * weights["dom"] +
            semantic_confidence * weights["semantic"] +
            flow_confidence * weights["flow"] +
            action_confidence * weights["action"] +
            assertion_confidence * weights["assertion"] +
            runtime_stability * weights["stability"] +
            healing_confidence * weights["healing"]
        )
        
        score = ExecutionIntelligenceScore(
            score_id=score_id,
            execution_id=execution_id,
            locator_confidence=locator_confidence,
            dom_confidence=dom_confidence,
            semantic_confidence=semantic_confidence,
            flow_confidence=flow_confidence,
            action_confidence=action_confidence,
            assertion_confidence=assertion_confidence,
            runtime_stability=runtime_stability,
            healing_confidence=healing_confidence,
            overall_score=overall_score,
            score_evidence=execution_evidence,
        )
        
        logger.info(
            f"[SCORER] Execution {execution_id} score: {overall_score:.1f}/100"
        )
        
        return score
    
    def _calculate_locator_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate locator confidence score."""
        locators = evidence.get("locators", {})
        
        if not locators:
            return 50.0  # Low confidence if no locators
        
        # Average locator confidence
        total_confidence = 0.0
        count = 0
        
        for locator_data in locators.values():
            conf = locator_data.get("confidence", 0.5)
            total_confidence += conf
            count += 1
        
        if count > 0:
            avg_confidence = (total_confidence / count) * 100
            return min(100.0, max(0.0, avg_confidence))
        
        return 50.0
    
    def _calculate_dom_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate DOM confidence score."""
        dom_cache_hits = evidence.get("dom_cache_hits", 0)
        dom_cache_misses = evidence.get("dom_cache_misses", 0)
        
        total = dom_cache_hits + dom_cache_misses
        if total == 0:
            return 50.0
        
        # Higher score for high cache hit rate
        hit_rate = dom_cache_hits / total
        return hit_rate * 100
    
    def _calculate_semantic_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate semantic confidence score."""
        semantic_pages = evidence.get("semantic_pages", {})
        
        if not semantic_pages:
            return 50.0
        
        # Average semantic confidence
        total_confidence = 0.0
        count = 0
        
        for page_data in semantic_pages.values():
            conf = page_data.get("confidence", 0.5)
            total_confidence += conf
            count += 1
        
        if count > 0:
            avg_confidence = (total_confidence / count) * 100
            return min(100.0, max(0.0, avg_confidence))
        
        return 50.0
    
    def _calculate_flow_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate flow confidence score."""
        flows = evidence.get("flows", {})
        
        if not flows:
            return 50.0
        
        # Average flow confidence
        total_confidence = 0.0
        count = 0
        
        for flow_data in flows.values():
            conf = flow_data.get("confidence", 0.5)
            total_confidence += conf
            count += 1
        
        if count > 0:
            avg_confidence = (total_confidence / count) * 100
            return min(100.0, max(0.0, avg_confidence))
        
        return 50.0
    
    def _calculate_action_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate action confidence score."""
        actions = evidence.get("actions", {})
        
        if not actions:
            return 50.0
        
        # Success rate of actions
        successful = sum(1 for a in actions.values() if a.get("result") == "success")
        total = len(actions)
        
        if total > 0:
            success_rate = (successful / total) * 100
            return success_rate
        
        return 50.0
    
    def _calculate_assertion_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate assertion confidence score."""
        assertions = evidence.get("assertions", {})
        
        if not assertions:
            return 50.0
        
        # Success rate of assertions
        successful = sum(1 for a in assertions.values() if a.get("result") == "success")
        total = len(assertions)
        
        if total > 0:
            success_rate = (successful / total) * 100
            return success_rate
        
        return 50.0
    
    def _calculate_runtime_stability(self, evidence: Dict[str, Any]) -> float:
        """Calculate runtime stability score."""
        # Based on consistency of execution time
        execution_times = evidence.get("execution_times", [])
        
        if len(execution_times) < 2:
            return 50.0
        
        # Calculate variance
        avg_time = sum(execution_times) / len(execution_times)
        variance = sum((t - avg_time) ** 2 for t in execution_times) / len(execution_times)
        
        # Lower variance = higher stability
        stability = max(0.0, 100.0 - (variance / avg_time) * 10)
        return min(100.0, max(0.0, stability))
    
    def _calculate_healing_confidence(self, evidence: Dict[str, Any]) -> float:
        """Calculate healing confidence score."""
        healing_attempts = evidence.get("healing_attempts", 0)
        healing_successes = evidence.get("healing_successes", 0)
        
        if healing_attempts == 0:
            return 100.0  # No healing needed = perfect
        
        if healing_attempts > 0:
            success_rate = (healing_successes / healing_attempts) * 100
            return success_rate
        
        return 50.0
