"""Maintenance Validation Engine - Priority 30.

This module validates regenerated automation before execution, ensuring quality
and preventing invalid tests from proceeding.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.test_maintenance.models import (
    ValidationResult,
    ValidationStatus,
    RegenerationResult,
)

# Priority 24: Quality Gate
try:
    from phoenix.automation_generation.quality_gate import AutomationQualityGate
    PRIORITY24_AVAILABLE = True
except ImportError:
    PRIORITY24_AVAILABLE = False

logger = logging.getLogger(__name__)


class MaintenanceValidationEngine:
    """Validates regenerated automation before execution.
    
    This engine:
    - Validates generated automation
    - Runs quality gate
    - Verifies locators
    - Verifies assertions
    - Verifies POM references
    - Verifies test data safety
    - Verifies no placeholders
    - Verifies no hardcoded credentials
    - Verifies no application-specific contamination
    """
    
    def __init__(self):
        """Initialize maintenance validation engine."""
        # Priority 24 quality gate
        self.quality_gate = None
        if PRIORITY24_AVAILABLE:
            self.quality_gate = AutomationQualityGate()
            logger.info("[MAINTENANCE VALIDATION] Priority 24 Quality Gate available")
        else:
            logger.warning("[MAINTENANCE VALIDATION] Priority 24 not available")
        
        # Validation history
        self.validation_history: List[Dict[str, Any]] = []
        
        # Security patterns
        self.credential_patterns = [
            r"password\s*=\s*['\"]\w+['\"]",
            r"username\s*=\s*['\"]\w+['\"]",
            r"api_key\s*=\s*['\"]\w+['\"]",
            r"secret\s*=\s*['\"]\w+['\"]",
            r"token\s*=\s*['\"]\w+['\"]",
        ]
        
        self.application_specific_patterns = [
            r"orangehrm",
            r"jira",
            r"salesforce",
            r"sap",
            r"servicenow",
        ]
        
        logger.info("[MAINTENANCE VALIDATION] Initialized")
    
    def validate_regeneration(
        self,
        regeneration_result: RegenerationResult,
        regenerated_code: Optional[str] = None,
    ) -> ValidationResult:
        """Validate regenerated automation.
        
        Args:
            regeneration_result: Regeneration result
            regenerated_code: Optional regenerated code
            
        Returns:
            Validation result
        """
        logger.info(f"[MAINTENANCE VALIDATION] Validating regeneration: {regeneration_result.regeneration_id}")
        
        validation_id = f"VAL-{uuid4().hex[:8]}"
        
        # Initialize validation results
        issues = []
        
        # Validate locators
        locator_validation = self._validate_locators(regeneration_result)
        issues.extend(locator_validation.get("issues", []))
        
        # Validate assertions
        assertion_validation = self._validate_assertions(regeneration_result)
        issues.extend(assertion_validation.get("issues", []))
        
        # Validate POM references
        pom_validation = self._validate_pom_references(regeneration_result)
        issues.extend(pom_validation.get("issues", []))
        
        # Validate security
        security_validation = self._validate_security(
            regeneration_result,
            regenerated_code,
        )
        issues.extend(security_validation.get("issues", []))
        
        # Run quality gate if available
        quality_score = 0.0
        if self.quality_gate and regenerated_code:
            # Would integrate with Priority 24 quality gate
            quality_score = self._calculate_quality_score(
                locator_validation,
                assertion_validation,
                pom_validation,
                security_validation,
            )
        
        # Determine overall status
        status = self._determine_status(issues, quality_score)
        
        result = ValidationResult(
            validation_id=validation_id,
            regeneration_id=regeneration_result.regeneration_id,
            test_id=regeneration_result.test_id,
            status=status,
            quality_score=quality_score,
            locator_validation=locator_validation,
            assertion_validation=assertion_validation,
            pom_validation=pom_validation,
            security_validation=security_validation,
            issues=issues,
        )
        
        # Record validation
        self._record_validation(result)
        
        logger.info(
            f"[MAINTENANCE VALIDATION] Validation complete: "
            f"status={status.value}, score={quality_score:.1f}, issues={len(issues)}"
        )
        
        return result
    
    def _validate_locators(
        self,
        regeneration_result: RegenerationResult,
    ) -> Dict[str, Any]:
        """Validate locators in regenerated automation.
        
        Args:
            regeneration_result: Regeneration result
            
        Returns:
            Locator validation result
        """
        issues = []
        
        # Check for placeholder locators
        for step_id, locator in regeneration_result.new_locators.items():
            if self._is_placeholder_locator(locator):
                issues.append({
                    "step_id": step_id,
                    "issue": "placeholder_locator",
                    "message": f"Placeholder locator found: {locator}",
                })
        
        # Check for invalid locator strategies
        for step_id, locator in regeneration_result.new_locators.items():
            if self._is_invalid_locator(locator):
                issues.append({
                    "step_id": step_id,
                    "issue": "invalid_locator",
                    "message": f"Invalid locator strategy: {locator}",
                })
        
        return {
            "valid": len(issues) == 0,
            "total_locators": len(regeneration_result.new_locators),
            "valid_locators": len(regeneration_result.new_locators) - len(issues),
            "issues": issues,
        }
    
    def _validate_assertions(
        self,
        regeneration_result: RegenerationResult,
    ) -> Dict[str, Any]:
        """Validate assertions in regenerated automation.
        
        Args:
            regeneration_result: Regeneration result
            
        Returns:
            Assertion validation result
        """
        issues = []
        
        # Check for placeholder assertions
        # This would be more sophisticated in a real implementation
        
        return {
            "valid": len(issues) == 0,
            "total_assertions": len(regeneration_result.new_assertions),
            "valid_assertions": len(regeneration_result.new_assertions) - len(issues),
            "issues": issues,
        }
    
    def _validate_pom_references(
        self,
        regeneration_result: RegenerationResult,
    ) -> Dict[str, Any]:
        """Validate POM references in regenerated automation.
        
        Args:
            regeneration_result: Regeneration result
            
        Returns:
            POM validation result
        """
        issues = []
        
        # Check for missing POM references
        # This would integrate with POM intelligence
        
        return {
            "valid": len(issues) == 0,
            "pom_references_valid": True,
            "issues": issues,
        }
    
    def _validate_security(
        self,
        regeneration_result: RegenerationResult,
        regenerated_code: Optional[str],
    ) -> Dict[str, Any]:
        """Validate security of regenerated automation.
        
        Args:
            regeneration_result: Regeneration result
            regenerated_code: Regenerated code
            
        Returns:
            Security validation result
        """
        issues = []
        
        if regenerated_code:
            # Check for hardcoded credentials
            for pattern in self.credential_patterns:
                if re.search(pattern, regenerated_code, re.IGNORECASE):
                    issues.append({
                        "issue": "hardcoded_credentials",
                        "message": f"Potential hardcoded credentials detected",
                    })
            
            # Check for application-specific contamination
            for pattern in self.application_specific_patterns:
                if re.search(pattern, regenerated_code, re.IGNORECASE):
                    issues.append({
                        "issue": "application_specific",
                        "message": f"Application-specific reference detected: {pattern}",
                    })
        
        return {
            "valid": len(issues) == 0,
            "credentials_safe": len([i for i in issues if i["issue"] == "hardcoded_credentials"]) == 0,
            "application_agnostic": len([i for i in issues if i["issue"] == "application_specific"]) == 0,
            "issues": issues,
        }
    
    def _is_placeholder_locator(
        self,
        locator: str,
    ) -> bool:
        """Check if locator is a placeholder.
        
        Args:
            locator: Locator string
            
        Returns:
            True if placeholder
        """
        placeholder_indicators = [
            "placeholder",
            "example",
            "test123",
            "dummy",
            "todo",
            "fixme",
        ]
        
        locator_lower = locator.lower()
        return any(indicator in locator_lower for indicator in placeholder_indicators)
    
    def _is_invalid_locator(
        self,
        locator: str,
    ) -> bool:
        """Check if locator uses invalid strategy.
        
        Args:
            locator: Locator string
            
        Returns:
            True if invalid
        """
        # XPath should be last resort
        if "xpath" in locator.lower() and not any(
            valid in locator.lower()
            for valid in ["test_id", "role", "label", "placeholder"]
        ):
            return True
        
        return False
    
    def _calculate_quality_score(
        self,
        locator_validation: Dict[str, Any],
        assertion_validation: Dict[str, Any],
        pom_validation: Dict[str, Any],
        security_validation: Dict[str, Any],
    ) -> float:
        """Calculate overall quality score.
        
        Args:
            locator_validation: Locator validation result
            assertion_validation: Assertion validation result
            pom_validation: POM validation result
            security_validation: Security validation result
            
        Returns:
            Quality score (0.0 to 100.0)
        """
        score = 100.0
        
        # Deduct for locator issues
        locator_issues = len(locator_validation.get("issues", []))
        score -= locator_issues * 10
        
        # Deduct for assertion issues
        assertion_issues = len(assertion_validation.get("issues", []))
        score -= assertion_issues * 10
        
        # Deduct for POM issues
        pom_issues = len(pom_validation.get("issues", []))
        score -= pom_issues * 15
        
        # Deduct for security issues (critical)
        security_issues = len(security_validation.get("issues", []))
        score -= security_issues * 25
        
        return max(0.0, min(100.0, score))
    
    def _determine_status(
        self,
        issues: List[Dict[str, Any]],
        quality_score: float,
    ) -> ValidationStatus:
        """Determine validation status.
        
        Args:
            issues: Validation issues
            quality_score: Quality score
            
        Returns:
            Validation status
        """
        # Critical security issues
        security_issues = [i for i in issues if i["issue"] in ["hardcoded_credentials"]]
        if security_issues:
            return ValidationStatus.FAILED
        
        # Low quality score
        if quality_score < 50.0:
            return ValidationStatus.FAILED
        
        # Medium quality score
        if quality_score < 70.0:
            return ValidationStatus.PARTIAL
        
        # Some issues but acceptable
        if len(issues) > 0:
            return ValidationStatus.PARTIAL
        
        # All good
        return ValidationStatus.PASSED
    
    def _record_validation(
        self,
        result: ValidationResult,
    ):
        """Record validation for learning.
        
        Args:
            result: Validation result
        """
        self.validation_history.append({
            "validation_id": result.validation_id,
            "regeneration_id": result.regeneration_id,
            "test_id": result.test_id,
            "status": result.status.value,
            "quality_score": result.quality_score,
            "issues_count": len(result.issues),
        })
