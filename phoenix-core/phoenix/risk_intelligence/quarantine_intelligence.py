"""Test Quarantine Intelligence - Priority 31.

This module implements intelligent test quarantine support for unstable or problematic tests.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.risk_intelligence.models import (
    QuarantineRecord,
    ExecutionPolicy,
)

logger = logging.getLogger(__name__)


class QuarantineIntelligence:
    """Manages test quarantine for unstable tests.
    
    This intelligence:
    - Detects quarantine conditions
    - Records quarantine reasons
    - Tracks failure history
    - Provides recommendations
    - Manages quarantine lifecycle
    """
    
    def __init__(self):
        """Initialize quarantine intelligence."""
        self.quarantine_records: Dict[str, QuarantineRecord] = {}
        
        # Quarantine threshold configuration
        self.quarantine_thresholds = {
            "repeated_failures": 3,
            "infrastructure_failure_threshold": 5,
            "automation_instability_threshold": 0.3,
            "confidence_threshold": 0.5,
        }
        
        logger.info("[QUARANTINE INTELLIGENCE] Initialized")
    
    def should_quarantine(
        self,
        test_id: str,
        execution_history: List[Dict[str, Any]],
        current_failure: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str]]:
        """Determine if a test should be quarantined.
        
        Args:
            test_id: Test ID
            execution_history: Execution history
            current_failure: Current failure details
            
        Returns:
            Tuple of (should_quarantine, reason)
        """
        # Check repeated failures
        if self._has_repeated_failures(execution_history):
            return True, "Repeated failures detected"
        
        # Check infrastructure-related failures
        if current_failure and self._is_infrastructure_failure(current_failure):
            if self._has_infrastructure_failures(execution_history):
                return True, "Infrastructure-related failures"
        
        # Check automation instability
        if self._has_automation_instability(execution_history):
            return True, "Automation instability detected"
        
        # Check ambiguous behaviour
        if self._has_ambiguous_behaviour(execution_history):
            return True, "Ambiguous test behaviour"
        
        # Check maintenance failures
        if self._has_maintenance_failures(execution_history):
            return True, "Repeated maintenance failures"
        
        # Check healing failures
        if self._has_healing_failures(execution_history):
            return True, "Repeated healing failures"
        
        # Check low confidence
        if self._has_low_confidence(execution_history):
            return True, "Test confidence below threshold"
        
        # Check inconsistent results
        if self._has_inconsistent_results(execution_history):
            return True, "Inconsistent test results"
        
        return False, None
    
    def quarantine_test(
        self,
        test_id: str,
        reason: str,
        evidence: List[str],
        failure_history: List[Dict[str, Any]],
        last_successful_execution: Optional[datetime],
        confidence: float,
        affected_flow: Optional[str],
    ) -> QuarantineRecord:
        """Quarantine a test.
        
        Args:
            test_id: Test ID
            reason: Quarantine reason
            evidence: Supporting evidence
            failure_history: Failure history
            last_successful_execution: Last successful execution
            confidence: Current confidence
            affected_flow: Affected flow
            
        Returns:
            Quarantine record
        """
        quarantine_id = f"QUARANTINE-{uuid4().hex[:8]}"
        
        # Generate recommended action
        recommended_action = self._generate_quarantine_recommendation(reason, confidence)
        
        record = QuarantineRecord(
            quarantine_id=quarantine_id,
            test_id=test_id,
            reason=reason,
            evidence=evidence,
            failure_history=failure_history,
            last_successful_execution=last_successful_execution,
            confidence=confidence,
            affected_flow=affected_flow,
            recommended_action=recommended_action,
        )
        
        self.quarantine_records[quarantine_id] = record
        
        logger.warning(f"[QUARANTINE] Test quarantined: {test_id} - {reason}")
        
        return record
    
    def release_quarantine(
        self,
        quarantine_id: str,
        release_reason: str,
    ) -> bool:
        """Release a test from quarantine.
        
        Args:
            quarantine_id: Quarantine ID
            release_reason: Reason for release
            
        Returns:
            True if released successfully
        """
        if quarantine_id not in self.quarantine_records:
            logger.warning(f"[QUARANTINE] Quarantine not found: {quarantine_id}")
            return False
        
        record = self.quarantine_records[quarantine_id]
        
        logger.info(f"[QUARANTINE] Test released from quarantine: {record.test_id}")
        
        del self.quarantine_records[quarantine_id]
        
        return True
    
    def _has_repeated_failures(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for repeated failures.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if repeated failures detected
        """
        if len(execution_history) < self.quarantine_thresholds["repeated_failures"]:
            return False
        
        # Check last N executions
        recent = execution_history[-self.quarantine_thresholds["repeated_failures"]:]
        failed_count = sum(1 for e in recent if not e.get("success", True))
        
        return failed_count >= self.quarantine_thresholds["repeated_failures"]
    
    def _is_infrastructure_failure(
        self,
        failure: Dict[str, Any],
    ) -> bool:
        """Check if failure is infrastructure-related.
        
        Args:
            failure: Failure details
            
        Returns:
            True if infrastructure failure
        """
        error_message = failure.get("error", "").lower()
        
        infrastructure_keywords = [
            "timeout",
            "network",
            "connection",
            "infrastructure",
            "environment",
            "resource",
        ]
        
        return any(keyword in error_message for keyword in infrastructure_keywords)
    
    def _has_infrastructure_failures(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for repeated infrastructure failures.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if infrastructure failures detected
        """
        infrastructure_failures = 0
        
        for execution in execution_history:
            if not execution.get("success", True):
                if self._is_infrastructure_failure(execution):
                    infrastructure_failures += 1
        
        return infrastructure_failures >= self.quarantine_thresholds["infrastructure_failure_threshold"]
    
    def _has_automation_instability(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for automation instability.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if automation instability detected
        """
        if not execution_history:
            return False
        
        # Calculate success rate
        total = len(execution_history)
        failed = sum(1 for e in execution_history if not e.get("success", True))
        success_rate = 1.0 - (failed / total) if total > 0 else 1.0
        
        return success_rate < self.quarantine_thresholds["automation_instability_threshold"]
    
    def _has_ambiguous_behaviour(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for ambiguous test behaviour.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if ambiguous behaviour detected
        """
        # Check for alternating pass/fail
        if len(execution_history) < 4:
            return False
        
        recent = execution_history[-4:]
        results = [e.get("success", True) for e in recent]
        
        # Check for alternation
        alternations = 0
        for i in range(len(results) - 1):
            if results[i] != results[i + 1]:
                alternations += 1
        
        return alternations >= 2
    
    def _has_maintenance_failures(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for repeated maintenance failures.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if maintenance failures detected
        """
        maintenance_failures = sum(
            1 for e in execution_history
            if e.get("maintenance_failed", False)
        )
        
        return maintenance_failures >= 2
    
    def _has_healing_failures(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for repeated healing failures.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if healing failures detected
        """
        healing_failures = sum(
            1 for e in execution_history
            if e.get("healing_failed", False)
        )
        
        return healing_failures >= 3
    
    def _has_low_confidence(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for low confidence.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if low confidence detected
        """
        if not execution_history:
            return False
        
        # Get average confidence
        confidences = [e.get("confidence", 1.0) for e in execution_history]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        
        return avg_confidence < self.quarantine_thresholds["confidence_threshold"]
    
    def _has_inconsistent_results(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> bool:
        """Check for inconsistent results.
        
        Args:
            execution_history: Execution history
            
        Returns:
            True if inconsistent results detected
        """
        if len(execution_history) < 5:
            return False
        
        # Check for high variance in execution time
        execution_times = [e.get("duration_ms", 0) for e in execution_history]
        
        if not execution_times:
            return False
        
        avg_time = sum(execution_times) / len(execution_times)
        variance = sum((t - avg_time) ** 2 for t in execution_times) / len(execution_times)
        
        # High variance indicates inconsistency
        return variance > (avg_time * 0.5) ** 2
    
    def _generate_quarantine_recommendation(
        self,
        reason: str,
        confidence: float,
    ) -> str:
        """Generate recommendation for quarantined test.
        
        Args:
            reason: Quarantine reason
            confidence: Current confidence
            
        Returns:
            Recommended action
        """
        if "infrastructure" in reason.lower():
            return "Investigate infrastructure issues before re-enabling"
        elif "maintenance" in reason.lower():
            return "Review and fix automation before re-enabling"
        elif "healing" in reason.lower():
            return "Review locators and improve stability before re-enabling"
        elif "ambiguous" in reason.lower() or "inconsistent" in reason.lower():
            return "Review test logic and stabilize before re-enabling"
        elif confidence < 0.3:
            return "Major test redesign required"
        else:
            return "Monitor and investigate before re-enabling"
    
    def get_quarantined_tests(self) -> List[QuarantineRecord]:
        """Get all quarantined tests.
        
        Returns:
            List of quarantine records
        """
        return list(self.quarantine_records.values())
    
    def get_quarantine_stats(self) -> Dict[str, Any]:
        """Get quarantine statistics.
        
        Returns:
            Quarantine statistics
        """
        return {
            "total_quarantined": len(self.quarantine_records),
            "by_reason": self._group_by_reason(),
        }
    
    def _group_by_reason(self) -> Dict[str, int]:
        """Group quarantines by reason.
        
        Returns:
            Reason counts
        """
        reason_counts = {}
        
        for record in self.quarantine_records.values():
            reason = record.reason
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return reason_counts
