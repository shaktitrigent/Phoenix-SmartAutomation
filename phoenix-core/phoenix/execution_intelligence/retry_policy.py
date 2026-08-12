"""Smart Retry Policy - Evidence-driven retry decisions.

This module implements intelligent retry policy that does not blindly retry
but makes evidence-based decisions about when and how to retry.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import SmartRetryDecision

logger = logging.getLogger(__name__)


class SmartRetryPolicy:
    """Smart retry policy for evidence-driven retry decisions.
    
    Instead of blindly retrying 3 times, this policy:
    - Analyzes failure type
    - Checks recoverability
    - Evaluates retry confidence
    - Determines retry strategy
    - Calculates backoff
    """
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        
        # Failure types that are generally retryable
        self.retryable_failures = [
            "locator_failure",
            "navigation_failure",
            "timeout_failure",
            "infrastructure_failure",
        ]
        
        # Failure types that are generally not retryable
        self.non_retryable_failures = [
            "test_data_failure",
            "application_failure",
            "assertion_failure",
        ]
        
        logger.info(f"SmartRetryPolicy initialized (max_retries={max_retries})")
    
    def should_retry(
        self,
        failure_classification: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> SmartRetryDecision:
        """Determine if execution should be retried.
        
        Args:
            failure_classification: Failure classification
            context: Execution context
            
        Returns:
            SmartRetryDecision with reasoning
        """
        decision_id = f"RETRY-{uuid.uuid4().hex[:8].upper()}"
        
        context = context or {}
        failure_count = context.get("failure_count", 0)
        
        if failure_classification:
            failure_type = failure_classification.get("failure_type", "")
            recoverability = failure_classification.get("recoverability", "UNKNOWN")
            phoenix_responsible = failure_classification.get("phoenix_responsibility", False)
        else:
            failure_type = ""
            recoverability = "UNKNOWN"
            phoenix_responsible = False
        
        # Check if we've exceeded max retries
        if failure_count >= self.max_retries:
            return SmartRetryDecision(
                decision_id=decision_id,
                should_retry=False,
                reason=f"Exceeded max retries ({self.max_retries})",
                confidence=0.99,
                failure_type=failure_type,
                failure_count=failure_count,
                max_retries=self.max_retries,
            )
        
        # Check if failure is retryable
        if failure_type in self.non_retryable_failures:
            return SmartRetryDecision(
                decision_id=decision_id,
                should_retry=False,
                reason=f"Failure type {failure_type} is not retryable",
                confidence=0.95,
                failure_type=failure_type,
                failure_count=failure_count,
                max_retries=self.max_retries,
            )
        
        # Check if Phoenix is responsible
        if not phoenix_responsible:
            return SmartRetryDecision(
                decision_id=decision_id,
                should_retry=False,
                reason="Application is responsible for failure",
                confidence=0.9,
                failure_type=failure_type,
                failure_count=failure_count,
                max_retries=self.max_retries,
            )
        
        # Check recoverability
        if recoverability == "LOW":
            return SmartRetryDecision(
                decision_id=decision_id,
                should_retry=False,
                reason="Failure has low recoverability",
                confidence=0.85,
                failure_type=failure_type,
                failure_count=failure_count,
                max_retries=self.max_retries,
            )
        
        # Failure is retryable
        retry_delay_ms = self._calculate_retry_delay(failure_count)
        backoff_multiplier = self._calculate_backoff(failure_count)
        confidence = self._calculate_retry_confidence(failure_type, failure_count)
        
        return SmartRetryDecision(
            decision_id=decision_id,
            should_retry=True,
            reason=f"Transient failure ({failure_type}) - retryable",
            confidence=confidence,
            failure_type=failure_type,
            failure_count=failure_count,
            max_retries=self.max_retries,
            retry_strategy="exponential_backoff",
            retry_delay_ms=retry_delay_ms,
            backoff_multiplier=backoff_multiplier,
            evidence=[f"Failure type: {failure_type}", f"Recoverability: {recoverability}"],
        )
    
    def _calculate_retry_delay(self, failure_count: int) -> int:
        """Calculate retry delay based on failure count."""
        base_delay = 1000  # 1 second
        return base_delay * (2 ** failure_count)
    
    def _calculate_backoff(self, failure_count: int) -> float:
        """Calculate backoff multiplier."""
        return 2.0
    
    def _calculate_retry_confidence(
        self,
        failure_type: str,
        failure_count: int,
    ) -> float:
        """Calculate confidence in retry decision."""
        base_confidence = 0.8
        
        # Reduce confidence for each failure
        confidence = base_confidence - (failure_count * 0.1)
        
        # Increase confidence for highly retryable failures
        if failure_type in ["locator_failure", "timeout_failure"]:
            confidence += 0.1
        
        return max(0.5, min(0.95, confidence))
