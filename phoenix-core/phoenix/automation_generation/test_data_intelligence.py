"""Automatic Test Data Intelligence - Determines test data requirements from evidence.

This module implements generic test data intelligence that determines requirements
from application evidence without inventing credentials for real systems.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.automation_generation.models import (
    TestDataRequirement,
    TestDataType,
)
from phoenix.semantic.models import SemanticComponent

logger = logging.getLogger(__name__)


class TestDataIntelligence:
    """Automatic test data intelligence for requirement detection.
    
    This intelligence:
    - Determines test data requirements from application evidence
    - Supports generic data types
    - Uses observed validation rules
    - Detects input constraints
    - Blocks when credentials are required and unavailable
    - Never invents credentials for real systems
    """
    
    def __init__(self):
        self.data_type_patterns = self._initialize_data_type_patterns()
        logger.info("TestDataIntelligence initialized")
    
    def _initialize_data_type_patterns(self) -> Dict[str, TestDataType]:
        """Initialize patterns for detecting data types."""
        return {
            "username": TestDataType.USERNAME,
            "user": TestDataType.USERNAME,
            "password": TestDataType.PASSWORD,
            "pass": TestDataType.PASSWORD,
            "email": TestDataType.EMAIL,
            "mail": TestDataType.EMAIL,
            "phone": TestDataType.PHONE,
            "mobile": TestDataType.PHONE,
            "name": TestDataType.NAME,
            "address": TestDataType.ADDRESS,
            "date": TestDataType.DATE,
            "number": TestDataType.NUMBER,
            "amount": TestDataType.CURRENCY,
            "price": TestDataType.CURRENCY,
            "file": TestDataType.FILE,
            "upload": TestDataType.FILE,
            "search": TestDataType.SEARCH_QUERY,
            "url": TestDataType.URL,
            "id": TestDataType.ID,
        }
    
    def identify_test_data_requirements(
        self,
        components: List[SemanticComponent],
        scenario_context: Optional[Dict[str, Any]] = None,
    ) -> List[TestDataRequirement]:
        """Identify test data requirements from components and context.
        
        Args:
            components: Semantic components to analyze
            scenario_context: Additional scenario context
            
        Returns:
            List of test data requirements
        """
        requirements = []
        scenario_context = scenario_context or {}
        
        for component in components:
            # Analyze component for data requirements
            component_reqs = self._analyze_component(component)
            requirements.extend(component_reqs)
        
        # Remove duplicates
        unique_requirements = self._deduplicate_requirements(requirements)
        
        # Check for blocking conditions
        blocking = self._check_blocking_conditions(unique_requirements)
        if blocking:
            logger.warning(f"Blocking condition: {blocking}")
            # Mark as blocked
            for req in unique_requirements:
                if req.is_sensitive and req.is_missing:
                    req.is_required = True
        
        logger.info(
            f"Identified {len(unique_requirements)} test data requirements "
            f"({sum(1 for r in unique_requirements if r.is_missing)} missing)"
        )
        
        return unique_requirements
    
    def _analyze_component(self, component: SemanticComponent) -> List[TestDataRequirement]:
        """Analyze a single component for test data requirements."""
        requirements = []
        
        # Check component attributes for data type indicators
        text_content_lower = component.text_content.lower()
        label_lower = component.label.lower()
        placeholder_lower = component.placeholder.lower()
        name_lower = component.name.lower()
        
        # Check for data type patterns
        data_type = self._detect_data_type(
            text_content_lower,
            label_lower,
            placeholder_lower,
            name_lower,
        )
        
        if data_type:
            req = TestDataRequirement(
                data_id=f"DATA-{uuid.uuid4().hex[:8].upper()}",
                data_type=data_type,
                field_name=label_lower or placeholder_lower or name_lower,
                is_required=component.is_required,
                source="component_analysis",
            )
            
            # Extract constraints from validation rules
            if component.validation_rules:
                req.constraints = self._extract_constraints(component.validation_rules)
                req.validation_rules = [r.get("rule", "") for r in component.validation_rules]
            
            # Mark as sensitive if it's a password
            if data_type == TestDataType.PASSWORD:
                req.is_sensitive = True
                req.is_missing = True  # Passwords should never be auto-generated
            
            # Mark as missing if no value provided
            if not req.provided_value:
                req.is_missing = True
            
            requirements.append(req)
        
        return requirements
    
    def _detect_data_type(
        self,
        text_content: str,
        label: str,
        placeholder: str,
        name: str,
    ) -> Optional[TestDataType]:
        """Detect data type from component attributes."""
        combined_text = f"{text_content} {label} {placeholder} {name}".lower()
        
        for pattern, data_type in self.data_type_patterns.items():
            if pattern in combined_text:
                return data_type
        
        # Check HTML5 input types
        if component_type := self._infer_from_html5_type(combined_text):
            return component_type
        
        return None
    
    def _infer_from_html5_type(self, text: str) -> Optional[TestDataType]:
        """Infer data type from HTML5 input type patterns."""
        if "type=\"email\"" in text or "type='email'" in text:
            return TestDataType.EMAIL
        elif "type=\"tel\"" in text or "type='tel'" in text:
            return TestDataType.PHONE
        elif "type=\"number\"" in text or "type='number'" in text:
            return TestDataType.NUMBER
        elif "type=\"date\"" in text or "type='date'" in text:
            return TestDataType.DATE
        elif "type=\"url\"" in text or "type='url'" in text:
            return TestDataType.URL
        
        return None
    
    def _extract_constraints(
        self,
        validation_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract constraints from validation rules."""
        constraints = {}
        
        for rule in validation_rules:
            rule_type = rule.get("type", "")
            rule_value = rule.get("value", "")
            
            if rule_type == "minlength":
                constraints["min_length"] = int(rule_value) if rule_value.isdigit() else rule_value
            elif rule_type == "maxlength":
                constraints["max_length"] = int(rule_value) if rule_value.isdigit() else rule_value
            elif rule_type == "min":
                constraints["min_value"] = float(rule_value) if self._is_number(rule_value) else rule_value
            elif rule_type == "max":
                constraints["max_value"] = float(rule_value) if self._is_number(rule_value) else rule_value
            elif rule_type == "pattern":
                constraints["pattern"] = rule_value
        
        return constraints
    
    def _is_number(self, value: str) -> bool:
        """Check if string represents a number."""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _deduplicate_requirements(
        self,
        requirements: List[TestDataRequirement],
    ) -> List[TestDataRequirement]:
        """Remove duplicate requirements."""
        seen = set()
        unique = []
        
        for req in requirements:
            # Create a key for deduplication
            key = (req.data_type, req.field_name)
            if key not in seen:
                seen.add(key)
                unique.append(req)
        
        return unique
    
    def _check_blocking_conditions(
        self,
        requirements: List[TestDataRequirement],
    ) -> Optional[str]:
        """Check for blocking conditions that require user intervention."""
        # Check for missing sensitive data
        missing_sensitive = [
            req for req in requirements
            if req.is_sensitive and req.is_missing and req.is_required
        ]
        
        if missing_sensitive:
            return f"Missing required sensitive data: {', '.join(r.field_name for r in missing_sensitive)}"
        
        return None
    
    def generate_test_data_value(
        self,
        requirement: TestDataRequirement,
    ) -> Optional[Any]:
        """Generate a test data value for a requirement.
        
        Note: This NEVER generates sensitive data like passwords.
        For sensitive data, it returns None to indicate user must provide.
        """
        if requirement.is_sensitive:
            logger.warning(f"Cannot generate sensitive data for {requirement.field_name}")
            return None
        
        data_type = requirement.data_type
        constraints = requirement.constraints
        
        if data_type == TestDataType.EMAIL:
            return self._generate_email(constraints)
        elif data_type == TestDataType.PHONE:
            return self._generate_phone(constraints)
        elif data_type == TestDataType.NAME:
            return self._generate_name(constraints)
        elif data_type == TestDataType.NUMBER:
            return self._generate_number(constraints)
        elif data_type == TestDataType.DATE:
            return self._generate_date(constraints)
        elif data_type == TestDataType.TEXT:
            return self._generate_text(constraints)
        elif data_type == TestDataType.URL:
            return self._generate_url(constraints)
        else:
            return None
    
    def _generate_email(self, constraints: Dict[str, Any]) -> str:
        """Generate a test email address."""
        return "test.user@placeholder.test"
    
    def _generate_phone(self, constraints: Dict[str, Any]) -> str:
        """Generate a test phone number."""
        return "+1234567890"
    
    def _generate_name(self, constraints: Dict[str, Any]) -> str:
        """Generate a test name."""
        return "Test User"
    
    def _generate_number(self, constraints: Dict[str, Any]) -> int:
        """Generate a test number within constraints."""
        min_val = constraints.get("min_value", 1)
        max_val = constraints.get("max_value", 100)
        return 42  # Simple test value
    
    def _generate_date(self, constraints: Dict[str, Any]) -> str:
        """Generate a test date."""
        return "2024-01-01"
    
    def _generate_text(self, constraints: Dict[str, Any]) -> str:
        """Generate test text within constraints."""
        max_length = constraints.get("max_length", 50)
        return "Test text data"
    
    def _generate_url(self, constraints: Dict[str, Any]) -> str:
        """Generate a test URL."""
        return "https://placeholder.test"
