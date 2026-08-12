"""Enhanced Failure Classification - Universal failure analysis.

This module implements enhanced failure classification with comprehensive
failure type detection, root cause analysis, and responsibility determination.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class EnhancedFailureType(str, Enum):
    """Enhanced failure types for execution intelligence."""
    
    LOCATOR_FAILURE = "locator_failure"
    NAVIGATION_FAILURE = "navigation_failure"
    APPLICATION_FAILURE = "application_failure"
    VALIDATION_FAILURE = "validation_failure"
    ASSERTION_FAILURE = "assertion_failure"
    TEST_DATA_FAILURE = "test_data_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    TIMEOUT_FAILURE = "timeout_failure"
    DOM_CHANGE_FAILURE = "dom_change_failure"
    SESSION_FAILURE = "session_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class EnhancedFailureClassifier:
    """Enhanced failure classifier for execution intelligence.
    
    Detects:
    - Locator Failure (element not found, timeout, detached, hidden)
    - Navigation Failure (wrong URL, timeout, redirect, blank page)
    - Application Failure (HTTP error, server error, JavaScript error)
    - Validation Failure (missing validation, unexpected validation)
    - Assertion Failure (wrong text, state, URL, element)
    - Test Data Failure (missing env var, invalid credentials)
    - Infrastructure Failure (browser crash, network, environment)
    """
    
    def __init__(self):
        # Failure patterns for classification
        self.failure_patterns = {
            EnhancedFailureType.LOCATOR_FAILURE: [
                "timeout",
                "not found",
                "locator",
                "selector",
                "element",
                "detached",
                "hidden",
            ],
            EnhancedFailureType.NAVIGATION_FAILURE: [
                "navigation",
                "redirect",
                "timeout",
                "network",
                "url",
                "blank",
            ],
            EnhancedFailureType.APPLICATION_FAILURE: [
                "http error",
                "server error",
                "500",
                "502",
                "503",
                "javascript error",
                "exception",
            ],
            EnhancedFailureType.VALIDATION_FAILURE: [
                "validation",
                "required",
                "invalid",
                "format",
            ],
            EnhancedFailureType.ASSERTION_FAILURE: [
                "assertion",
                "expected",
                "actual",
                "assert",
                "to_be",
                "to_have",
            ],
            EnhancedFailureType.TEST_DATA_FAILURE: [
                "environment variable",
                "credential",
                "missing",
                "authentication",
                "unauthorized",
            ],
            EnhancedFailureType.INFRASTRUCTURE_FAILURE: [
                "browser",
                "crash",
                "launch",
                "connection",
                "network",
                "environment",
            ],
            EnhancedFailureType.TIMEOUT_FAILURE: [
                "timeout",
                "timed out",
            ],
            EnhancedFailureType.DOM_CHANGE_FAILURE: [
                "dom",
                "changed",
                "structure",
                "modified",
            ],
            EnhancedFailureType.SESSION_FAILURE: [
                "session",
                "expired",
                "auth",
                "cookie",
            ],
        }
        
        logger.info("EnhancedFailureClassifier initialized")
    
    def classify_failure(
        self,
        error_message: str,
        stack_trace: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify a failure with comprehensive analysis.
        
        Args:
            error_message: Error message from failure
            stack_trace: Stack trace if available
            context: Additional context
            
        Returns:
            Dictionary with failure classification
        """
        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        error_lower = error_message.lower()
        
        # Determine failure type
        failure_type = self._determine_failure_type(error_lower)
        
        # Determine root cause
        root_cause = self._determine_root_cause(error_lower, failure_type)
        
        # Determine responsibility
        phoenix_responsibility, application_responsibility = self._determine_responsibility(
            error_lower, failure_type, root_cause
        )
        
        # Determine recoverability
        recoverability = self._determine_recoverability(failure_type, root_cause)
        
        # Generate recommendation
        recommended_action = self._generate_recommendation(
            failure_type, root_cause, phoenix_responsibility
        )
        
        classification = {
            "failure_id": failure_id,
            "failure_type": failure_type.value,
            "severity": self._determine_severity(failure_type),
            "error_message": error_message,
            "stack_trace": stack_trace,
            "root_cause": root_cause,
            "evidence": {"error_message": error_message, "context": context or {}},
            "impact": self._determine_impact(failure_type, context),
            "phoenix_responsibility": phoenix_responsibility,
            "application_responsibility": application_responsibility,
            "recoverability": recoverability,
            "recommended_action": recommended_action,
            "confidence": self._calculate_confidence(failure_type, error_lower),
        }
        
        logger.info(
            f"[FAILURE CLASSIFIER] Classified {failure_id} as {failure_type.value} "
            f"(Phoenix: {phoenix_responsibility}, Application: {application_responsibility})"
        )
        
        return classification
    
    def _determine_failure_type(self, error_lower: str) -> EnhancedFailureType:
        """Determine failure type from error message."""
        # Check each failure type's patterns
        for failure_type, patterns in self.failure_patterns.items():
            if any(pattern in error_lower for pattern in patterns):
                return failure_type
        
        return EnhancedFailureType.UNKNOWN_FAILURE
    
    def _determine_root_cause(
        self,
        error_lower: str,
        failure_type: EnhancedFailureType,
    ) -> str:
        """Determine root cause from error and type."""
        if failure_type == EnhancedFailureType.LOCATOR_FAILURE:
            if "timeout" in error_lower:
                return "Element not found within timeout"
            elif "detached" in error_lower:
                return "Element detached from DOM"
            elif "hidden" in error_lower:
                return "Element is hidden"
            else:
                return "Locator does not match any element"
        
        elif failure_type == EnhancedFailureType.NAVIGATION_FAILURE:
            if "timeout" in error_lower:
                return "Navigation timeout"
            elif "network" in error_lower:
                return "Network error during navigation"
            else:
                return "Navigation failed"
        
        elif failure_type == EnhancedFailureType.APPLICATION_FAILURE:
            return "Application error or server issue"
        
        elif failure_type == EnhancedFailureType.ASSERTION_FAILURE:
            return "Assertion condition not met"
        
        elif failure_type == EnhancedFailureType.TEST_DATA_FAILURE:
            return "Test data validation failed"
        
        elif failure_type == EnhancedFailureType.INFRASTRUCTURE_FAILURE:
            return "Infrastructure issue (browser, network, environment)"
        
        else:
            return "Unknown root cause"
    
    def _determine_responsibility(
        self,
        error_lower: str,
        failure_type: EnhancedFailureType,
        root_cause: str,
    ) -> tuple[bool, bool]:
        """Determine responsibility for the failure."""
        phoenix_responsible = False
        application_responsible = False
        
        if failure_type == EnhancedFailureType.LOCATOR_FAILURE:
            phoenix_responsible = True
        
        elif failure_type == EnhancedFailureType.NAVIGATION_FAILURE:
            if "network" in error_lower or "connection" in error_lower:
                application_responsible = True
            else:
                phoenix_responsible = True
        
        elif failure_type == EnhancedFailureType.APPLICATION_FAILURE:
            application_responsible = True
        
        elif failure_type == EnhancedFailureType.ASSERTION_FAILURE:
            application_responsible = True
        
        elif failure_type == EnhancedFailureType.TEST_DATA_FAILURE:
            application_responsible = True
        
        elif failure_type == EnhancedFailureType.INFRASTRUCTURE_FAILURE:
            application_responsible = True
        
        else:
            phoenix_responsible = True
        
        return phoenix_responsible, application_responsible
    
    def _determine_recoverability(
        self,
        failure_type: EnhancedFailureType,
        root_cause: str,
    ) -> str:
        """Determine if failure is recoverable."""
        if failure_type == EnhancedFailureType.LOCATOR_FAILURE:
            return "HIGH"
        elif failure_type == EnhancedFailureType.NAVIGATION_FAILURE:
            return "MEDIUM"
        elif failure_type == EnhancedFailureType.APPLICATION_FAILURE:
            return "LOW"
        elif failure_type == EnhancedFailureType.ASSERTION_FAILURE:
            return "LOW"
        else:
            return "UNKNOWN"
    
    def _determine_severity(self, failure_type: EnhancedFailureType) -> str:
        """Determine failure severity."""
        if failure_type in [
            EnhancedFailureType.INFRASTRUCTURE_FAILURE,
            EnhancedFailureType.APPLICATION_FAILURE,
        ]:
            return "HIGH"
        elif failure_type in [
            EnhancedFailureType.LOCATOR_FAILURE,
            EnhancedFailureType.NAVIGATION_FAILURE,
        ]:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _determine_impact(
        self,
        failure_type: EnhancedFailureType,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Determine failure impact."""
        if failure_type == EnhancedFailureType.INFRASTRUCTURE_FAILURE:
            return "BLOCKING"
        elif failure_type == EnhancedFailureType.APPLICATION_FAILURE:
            return "HIGH"
        else:
            return "MEDIUM"
    
    def _generate_recommendation(
        self,
        failure_type: EnhancedFailureType,
        root_cause: str,
        phoenix_responsible: bool,
    ) -> str:
        """Generate recommended action."""
        if phoenix_responsible:
            if failure_type == EnhancedFailureType.LOCATOR_FAILURE:
                return "Attempt healing with alternative locators"
            elif failure_type == EnhancedFailureType.NAVIGATION_FAILURE:
                return "Retry navigation with different strategy"
            else:
                return "Retry with recovery strategy"
        else:
            return "Application issue - check application status"
    
    def _calculate_confidence(
        self,
        failure_type: EnhancedFailureType,
        error_lower: str,
    ) -> float:
        """Calculate confidence in classification."""
        # Higher confidence for clear pattern matches
        patterns = self.failure_patterns.get(failure_type, [])
        match_count = sum(1 for pattern in patterns if pattern in error_lower)
        
        if match_count > 0:
            return 0.8 + (0.1 * min(match_count, 2))
        else:
            return 0.5
