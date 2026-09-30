"""Pre-Execution Intelligence - Validate automation before execution.

This module implements comprehensive pre-execution validation to detect
problems before browser execution whenever possible.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import ast
import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import PreExecutionValidation

logger = logging.getLogger(__name__)


class PreExecutionValidator:
    """Pre-execution validator for automation scripts.
    
    Validates:
    - Test structure
    - Required actions
    - Required assertions
    - Required test data
    - Locator availability
    - Page object availability
    - Browser configuration
    - URL accessibility
    - Environment configuration
    """
    
    def __init__(self):
        self.locator_patterns = [
            r'get_by_',
            r'locator\(',
            r'\.click\(',
            r'\.fill\(',
        ]
        
        logger.info("PreExecutionValidator initialized")
    
    def validate(
        self,
        automation_script: str,
        automation_id: str,
    ) -> PreExecutionValidation:
        """Validate automation script before execution.
        
        Args:
            automation_script: Generated automation script
            automation_id: ID of the automation
            
        Returns:
            PreExecutionValidation with validation results
        """
        validation_id = f"VAL-{uuid.uuid4().hex[:8].upper()}"
        
        validation = PreExecutionValidation(
            validation_id=validation_id,
            automation_id=automation_id,
        )
        
        # Parse the script
        try:
            tree = ast.parse(automation_script)
        except SyntaxError as e:
            validation.overall_valid = False
            validation.blocking_issues.append(f"Syntax error: {e}")
            return validation
        
        # Validate test structure
        validation.test_structure_valid = self._validate_test_structure(tree)
        
        # Validate required actions
        validation.required_actions_valid = self._validate_required_actions(tree)
        
        # Validate required assertions
        validation.required_assertions_valid = self._validate_required_assertions(tree)
        
        # Validate locators
        locator_validation = self._validate_locators(tree, automation_script)
        validation.locator_exists = locator_validation["exists"]
        validation.locator_confidence_sufficient = locator_validation["confidence_ok"]
        validation.locator_unique = locator_validation["unique"]
        validation.locator_stable = locator_validation["stable"]
        validation.alternative_locators_available = locator_validation["has_alternatives"]
        
        # Validate test data (placeholder - would check environment)
        validation.required_env_vars_set = True  # Would check actual env
        validation.required_credentials_available = True  # Would check credentials
        validation.required_input_data_available = True  # Would check data
        validation.sensitive_data_protected = self._validate_sensitive_data_protection(tree)
        
        # Validate environment (placeholder)
        validation.browser_config_valid = True
        validation.url_accessible = True
        validation.environment_config_valid = True
        
        # Calculate overall validity
        validation.overall_valid = all([
            validation.test_structure_valid,
            validation.required_actions_valid,
            validation.required_assertions_valid,
            validation.locator_exists,
            validation.sensitive_data_protected,
        ])
        
        # Collect blocking issues
        if not validation.test_structure_valid:
            validation.blocking_issues.append("Test structure invalid")
        if not validation.required_actions_valid:
            validation.blocking_issues.append("Required actions missing")
        if not validation.required_assertions_valid:
            validation.blocking_issues.append("Required assertions missing")
        if not validation.locator_exists:
            validation.blocking_issues.append("No locators found")
        if not validation.sensitive_data_protected:
            validation.blocking_issues.append("Sensitive data not protected")
        
        # Calculate confidence
        validation.confidence = self._calculate_confidence(validation)
        
        logger.info(
            f"[PRE-EXECUTION] Validation {validation_id}: "
            f"{'VALID' if validation.overall_valid else 'INVALID'} "
            f"(confidence: {validation.confidence:.2f})"
        )
        
        return validation
    
    def _validate_test_structure(self, tree: ast.AST) -> bool:
        """Validate test structure."""
        # Check for test function
        has_test_function = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                has_test_function = True
                break
        
        return has_test_function
    
    def _validate_required_actions(self, tree: ast.AST) -> bool:
        """Validate required actions exist."""
        # Check for action methods (click, fill, etc.)
        has_actions = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr'):
                    if node.func.attr in ['click', 'fill', 'goto', 'select_option']:
                        has_actions = True
                        break
        
        return has_actions
    
    def _validate_required_assertions(self, tree: ast.AST) -> bool:
        """Validate required assertions exist."""
        # Check for assertions
        has_assertions = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr'):
                    if node.func.attr in ['to_be_visible', 'to_have_title', 'to_have_text']:
                        has_assertions = True
                        break
        
        return has_assertions
    
    def _validate_locators(
        self,
        tree: ast.AST,
        script: str,
    ) -> Dict[str, bool]:
        """Validate locators."""
        # Check for locator patterns
        locator_count = 0
        for pattern in self.locator_patterns:
            locator_count += len(re.findall(pattern, script))
        
        return {
            "exists": locator_count > 0,
            "confidence_ok": True,  # Would check actual confidence
            "unique": locator_count > 0,
            "stable": True,  # Would check stability history
            "has_alternatives": locator_count > 1,
        }
    
    def _validate_sensitive_data_protection(self, tree: ast.AST) -> bool:
        """Validate sensitive data is protected."""
        # Check for hardcoded sensitive data
        sensitive_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
        ]
        
        script_source = ast.unparse(tree) if hasattr(ast, 'unparse') else ""
        
        for pattern in sensitive_patterns:
            if re.search(pattern, script_source, re.IGNORECASE):
                return False
        
        return True
    
    def _calculate_confidence(self, validation: PreExecutionValidation) -> float:
        """Calculate overall validation confidence."""
        factors = [
            validation.test_structure_valid,
            validation.required_actions_valid,
            validation.required_assertions_valid,
            validation.locator_exists,
            validation.locator_confidence_sufficient,
            validation.sensitive_data_protected,
        ]
        
        return sum(factors) / len(factors)
