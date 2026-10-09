"""Failure Classification - Classifies failures in generated automation.

This module implements a failure classification system that categorizes
failures and determines responsibility (Phoenix vs Application).

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from phoenix.automation_generation.models import (
    FailureClassification,
    FailureType,
)

logger = logging.getLogger(__name__)


class FailureClassifier:
    """Failure classification system for generated automation.
    
    This classifier:
    - Categorizes failures by type
    - Determines root cause
    - Assigns responsibility (Phoenix vs Application)
    - Provides recommended actions
    - Tracks healing attempts
    """
    
    def __init__(self):
        # Failure patterns for classification
        self.failure_patterns = {
            FailureType.LOCATOR_FAILURE: [
                "timeout",
                "not found",
                "locator",
                "selector",
                "element",
            ],
            FailureType.NAVIGATION_FAILURE: [
                "navigation",
                "redirect",
                "timeout",
                "network",
            ],
            FailureType.ASSERTION_FAILURE: [
                "assertion",
                "expected",
                "actual",
                "assert",
            ],
            FailureType.DATA_FAILURE: [
                "data",
                "value",
                "invalid",
                "format",
            ],
            FailureType.ENVIRONMENT_FAILURE: [
                "environment",
                "network",
                "timeout",
                "connection",
            ],
        }
        
        logger.info("FailureClassifier initialized")
    
    def classify_failure(
        self,
        error_message: str,
        stack_trace: str = "",
        automation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> FailureClassification:
        """Classify a failure from execution.
        
        Args:
            error_message: Error message from failure
            stack_trace: Stack trace if available
            automation_id: ID of failed automation
            context: Additional context
            
        Returns:
            FailureClassification with analysis
        """
        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        error_lower = error_message.lower()
        
        # Determine failure type
        failure_type = self._determine_failure_type(error_lower)
        
        # Determine root cause
        root_cause = self._determine_root_cause(error_lower, failure_type)
        
        # Determine responsibility
        phoenix_responsibility, application_responsibility = self._determine_responsibility(
            error_lower,
            failure_type,
            root_cause,
        )
        
        # Determine impact
        impact = self._determine_impact(failure_type, context)
        
        # Provide recommendation
        recommended_action = self._generate_recommendation(
            failure_type,
            root_cause,
            phoenix_responsibility,
        )
        
        classification = FailureClassification(
            failure_id=failure_id,
            automation_id=automation_id,
            failure_type=failure_type,
            severity=self._determine_severity(failure_type),
            error_message=error_message,
            stack_trace=stack_trace,
            root_cause=root_cause,
            evidence={"error_message": error_message, "context": context or {}},
            impact=impact,
            phoenix_responsibility=phoenix_responsibility,
            application_responsibility=application_responsibility,
            recommended_action=recommended_action,
        )
        
        logger.info(
            f"Classified failure {failure_id} as {failure_type.value} "
            f"(Phoenix: {phoenix_responsibility}, Application: {application_responsibility})"
        )
        
        return classification
    
    def _determine_failure_type(self, error_lower: str) -> FailureType:
        """Determine failure type from error message."""
        # Check navigation failures first (more specific)
        if any(pattern in error_lower for pattern in self.failure_patterns[FailureType.NAVIGATION_FAILURE]):
            return FailureType.NAVIGATION_FAILURE
        
        # Check locator failures
        if any(pattern in error_lower for pattern in self.failure_patterns[FailureType.LOCATOR_FAILURE]):
            return FailureType.LOCATOR_FAILURE
        
        # Check assertion failures
        if any(pattern in error_lower for pattern in self.failure_patterns[FailureType.ASSERTION_FAILURE]):
            return FailureType.ASSERTION_FAILURE
        
        # Check data failures
        if any(pattern in error_lower for pattern in self.failure_patterns[FailureType.DATA_FAILURE]):
            return FailureType.DATA_FAILURE
        
        # Check environment failures
        if any(pattern in error_lower for pattern in self.failure_patterns[FailureType.ENVIRONMENT_FAILURE]):
            return FailureType.ENVIRONMENT_FAILURE
        
        # Default to automation failure
        return FailureType.AUTOMATION_FAILURE
    
    def _determine_root_cause(self, error_lower: str, failure_type: FailureType) -> str:
        """Determine root cause from error and type."""
        if failure_type == FailureType.LOCATOR_FAILURE:
            if "timeout" in error_lower:
                return "Element not found within timeout"
            elif "not found" in error_lower:
                return "Locator does not match any element"
            else:
                return "Locator resolution failed"
        
        elif failure_type == FailureType.NAVIGATION_FAILURE:
            if "timeout" in error_lower:
                return "Navigation timeout"
            elif "network" in error_lower:
                return "Network error during navigation"
            else:
                return "Navigation failed"
        
        elif failure_type == FailureType.ASSERTION_FAILURE:
            return "Assertion condition not met"
        
        elif failure_type == FailureType.DATA_FAILURE:
            return "Data validation failed"
        
        elif failure_type == FailureType.ENVIRONMENT_FAILURE:
            return "Environment issue (network, timeout, etc.)"
        
        else:
            return "Unknown root cause"
    
    def _determine_responsibility(
        self,
        error_lower: str,
        failure_type: FailureType,
        root_cause: str,
    ) -> tuple[bool, bool]:
        """Determine responsibility for the failure."""
        phoenix_responsible = False
        application_responsible = False
        
        if failure_type == FailureType.LOCATOR_FAILURE:
            # Locator failures are typically Phoenix's responsibility
            phoenix_responsible = True
        
        elif failure_type == FailureType.NAVIGATION_FAILURE:
            # Navigation failures could be either
            if "network" in error_lower or "connection" in error_lower:
                application_responsible = True
            else:
                phoenix_responsible = True
        
        elif failure_type == FailureType.ASSERTION_FAILURE:
            # Assertion failures indicate the application is not behaving as expected
            application_responsible = True
        
        elif failure_type == FailureType.DATA_FAILURE:
            # Data failures are typically application validation issues
            application_responsible = True
        
        elif failure_type == FailureType.ENVIRONMENT_FAILURE:
            # Environment failures are typically not Phoenix's fault
            application_responsible = True
        
        else:
            # Default to Phoenix responsibility for automation failures
            phoenix_responsible = True
        
        return phoenix_responsible, application_responsible
    
    def _determine_severity(self, failure_type: FailureType) -> str:
        """Determine severity based on failure type."""
        severity_map = {
            FailureType.LOCATOR_FAILURE: "high",
            FailureType.NAVIGATION_FAILURE: "high",
            FailureType.ASSERTION_FAILURE: "medium",
            FailureType.DATA_FAILURE: "medium",
            FailureType.ENVIRONMENT_FAILURE: "high",
            FailureType.AUTOMATION_FAILURE: "critical",
            FailureType.GENERATION_FAILURE: "critical",
        }
        return severity_map.get(failure_type, "medium")
    
    def _determine_impact(self, failure_type: FailureType, context: Dict[str, Any]) -> str:
        """Determine impact of the failure."""
        if failure_type == FailureType.ASSERTION_FAILURE:
            return "Test validation failed - application may have defect"
        elif failure_type == FailureType.LOCATOR_FAILURE:
            return "Cannot interact with element - automation blocked"
        elif failure_type == FailureType.NAVIGATION_FAILURE:
            return "Cannot reach target page - automation blocked"
        elif failure_type == FailureType.DATA_FAILURE:
            return "Data validation failed - may indicate application issue"
        else:
            return "Automation execution blocked"
    
    def _generate_recommendation(
        self,
        failure_type: FailureType,
        root_cause: str,
        phoenix_responsible: bool,
    ) -> str:
        """Generate recommended action for the failure."""
        if phoenix_responsible:
            if failure_type == FailureType.LOCATOR_FAILURE:
                return "Attempt healing with alternative locators"
            elif failure_type == FailureType.NAVIGATION_FAILURE:
                return "Check navigation logic and retry"
            else:
                return "Review automation generation logic"
        else:
            return "Application issue - report as defect"
    
    def batch_classify_failures(
        self,
        failures: List[Dict[str, Any]],
    ) -> List[FailureClassification]:
        """Classify multiple failures."""
        classifications = []
        
        for failure in failures:
            classification = self.classify_failure(
                error_message=failure.get("error_message", ""),
                stack_trace=failure.get("stack_trace", ""),
                automation_id=failure.get("automation_id", ""),
                context=failure.get("context"),
            )
            classifications.append(classification)
        
        logger.info(f"Classified {len(classifications)} failures")
        return classifications
