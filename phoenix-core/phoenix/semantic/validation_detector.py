"""Validation Detector - Generic Component Validation Intelligence (Priority 22).

This module detects validation rules and characteristics for form components
by analyzing DOM attributes, runtime behavior, and error messages.

This is completely generic and works for ANY web application without product-specific rules.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    ValidationRule,
)

logger = logging.getLogger(__name__)


class ValidationDetector:
    """Generic validation detector for form components.
    
    This detector identifies:
    - Required field validation
    - Format validation (email, phone, etc.)
    - Length validation (min, max)
    - Pattern validation (regex)
    - Value range validation
    - Custom validation rules
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the validation detector."""
        self.validation_patterns = self._initialize_validation_patterns()
        logger.info(f"[VALIDATION DETECTOR] Initialized with {len(self.validation_patterns)} validation patterns")
    
    def _initialize_validation_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize generic validation patterns."""
        patterns = {}
        
        # Required field patterns
        patterns["required"] = {
            "attributes": {"required": "true", "aria-required": "true", "data-required": "true"},
            "class_patterns": ["required", "mandatory", "obligatory"],
            "error_indicators": ["required", "mandatory", "must be filled", "cannot be empty"],
            "confidence": 0.9,
        }
        
        # Email format patterns
        patterns["email_format"] = {
            "attributes": {"type": "email"},
            "class_patterns": ["email", "email-field"],
            "error_indicators": ["valid email", "email format", "invalid email"],
            "confidence": 0.95,
        }
        
        # Phone format patterns
        patterns["phone_format"] = {
            "attributes": {"type": "tel"},
            "class_patterns": ["phone", "telephone", "mobile"],
            "error_indicators": ["valid phone", "phone format", "invalid phone"],
            "confidence": 0.9,
        }
        
        # URL format patterns
        patterns["url_format"] = {
            "attributes": {"type": "url"},
            "class_patterns": ["url", "website", "link"],
            "error_indicators": ["valid url", "url format", "invalid url"],
            "confidence": 0.9,
        }
        
        # Number format patterns
        patterns["number_format"] = {
            "attributes": {"type": "number"},
            "class_patterns": ["number", "numeric", "quantity"],
            "error_indicators": ["valid number", "numeric", "must be a number"],
            "confidence": 0.95,
        }
        
        # Min length patterns
        patterns["min_length"] = {
            "attributes": {"minlength": None, "data-minlength": None, "min-length": None},
            "error_indicators": ["at least", "minimum", "too short"],
            "confidence": 0.85,
        }
        
        # Max length patterns
        patterns["max_length"] = {
            "attributes": {"maxlength": None, "data-maxlength": None, "max-length": None},
            "error_indicators": ["at most", "maximum", "too long", "exceeds"],
            "confidence": 0.85,
        }
        
        # Min value patterns
        patterns["min_value"] = {
            "attributes": {"min": None, "data-min": None, "min-value": None},
            "error_indicators": ["must be at least", "minimum value", "too low"],
            "confidence": 0.85,
        }
        
        # Max value patterns
        patterns["max_value"] = {
            "attributes": {"max": None, "data-max": None, "max-value": None},
            "error_indicators": ["must be at most", "maximum value", "too high"],
            "confidence": 0.85,
        }
        
        return patterns
    
    def detect_validation_rules(
        self,
        component: SemanticComponent,
        error_messages: List[str] = None,
        runtime_observations: List[Dict[str, Any]] = None,
    ) -> List[ValidationRule]:
        """Detect validation rules for a component.
        
        Args:
            component: The component to analyze
            error_messages: Observed error messages
            runtime_observations: Runtime behavior observations
            
        Returns:
            List of detected validation rules
        """
        error_messages = error_messages or []
        runtime_observations = runtime_observations or []
        
        validation_rules = []
        
        # Only analyze form-related components
        if component.component_type not in [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.FILE_UPLOAD,
        ]:
            return validation_rules
        
        # Check each validation pattern
        for validation_type, pattern in self.validation_patterns.items():
            rule = self._check_validation_pattern(
                component,
                validation_type,
                pattern,
                error_messages,
                runtime_observations,
            )
            
            if rule:
                validation_rules.append(rule)
        
        # Extract specific validation values from attributes
        attribute_rules = self._extract_attribute_rules(component)
        validation_rules.extend(attribute_rules)
        
        logger.info(f"[VALIDATION DETECTOR] Detected {len(validation_rules)} validation rules for component")
        
        return validation_rules
    
    def _check_validation_pattern(
        self,
        component: SemanticComponent,
        validation_type: str,
        pattern: Dict[str, Any],
        error_messages: List[str],
        runtime_observations: List[Dict[str, Any]],
    ) -> Optional[ValidationRule]:
        """Check if a specific validation pattern applies."""
        evidence = []
        rule_value = None
        confidence = pattern["confidence"]
        
        # Check attributes
        for attr_name, expected_value in pattern.get("attributes", {}).items():
            if attr_name in component.attributes:
                # Check if value matches (if specified)
                actual_value = component.attributes[attr_name]
                
                if expected_value is not None and actual_value:
                    if expected_value == actual_value:
                        evidence.append(f"Attribute found: {attr_name}={expected_value}")
                    else:
                        continue  # Value doesn't match
                else:
                    evidence.append(f"Attribute found: {attr_name}")
                
                # Extract value if present
                if actual_value and actual_value != "true":
                    rule_value = actual_value
        
        # Check class patterns
        component_class = component.element_class.lower()
        for class_pattern in pattern.get("class_patterns", []):
            if class_pattern in component_class:
                evidence.append(f"Class pattern matched: {class_pattern}")
        
        # Check error messages
        combined_errors = " ".join(error_messages).lower()
        for error_indicator in pattern.get("error_indicators", []):
            if error_indicator in combined_errors:
                evidence.append(f"Error message indicator: {error_indicator}")
                confidence += 0.1  # Boost confidence with error message evidence
        
        # Check runtime observations
        for obs in runtime_observations:
            if obs.get("validation_triggered"):
                evidence.append("Runtime validation observed")
                confidence += 0.05
        
        # If we have evidence, create a validation rule
        if evidence:
            confidence = min(confidence, 1.0)
            
            return ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type=validation_type,
                confidence=confidence,
                rule_value=rule_value,
                error_message=self._find_relevant_error_message(validation_type, error_messages),
                trigger_condition="on_submit" if validation_type != "required" else "on_blur",
                evidence=evidence,
                observation_count=len([e for e in error_messages if any(ind in e.lower() for ind in pattern.get("error_indicators", []))]),
            )
        
        return None
    
    def _extract_attribute_rules(
        self,
        component: SemanticComponent,
    ) -> List[ValidationRule]:
        """Extract specific validation rules from attributes."""
        rules = []
        
        # Extract minlength
        if "minlength" in component.attributes:
            rules.append(ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type="min_length",
                confidence=0.9,
                rule_value=int(component.attributes["minlength"]),
                evidence=[f"Attribute minlength={component.attributes['minlength']}"],
            ))
        
        # Extract maxlength
        if "maxlength" in component.attributes:
            rules.append(ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type="max_length",
                confidence=0.9,
                rule_value=int(component.attributes["maxlength"]),
                evidence=[f"Attribute maxlength={component.attributes['maxlength']}"],
            ))
        
        # Extract min
        if "min" in component.attributes:
            rules.append(ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type="min_value",
                confidence=0.9,
                rule_value=float(component.attributes["min"]),
                evidence=[f"Attribute min={component.attributes['min']}"],
            ))
        
        # Extract max
        if "max" in component.attributes:
            rules.append(ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type="max_value",
                confidence=0.9,
                rule_value=float(component.attributes["max"]),
                evidence=[f"Attribute max={component.attributes['max']}"],
            ))
        
        # Extract pattern
        if "pattern" in component.attributes:
            rules.append(ValidationRule(
                field=component.name or component.component_id or "unknown",
                validation_type="pattern",
                confidence=0.8,
                rule_value=component.attributes["pattern"],
                evidence=[f"Attribute pattern={component.attributes['pattern']}"],
            ))
        
        return rules
    
    def _find_relevant_error_message(
        self,
        validation_type: str,
        error_messages: List[str],
    ) -> str:
        """Find the most relevant error message for a validation type."""
        pattern = self.validation_patterns.get(validation_type, {})
        indicators = pattern.get("error_indicators", [])
        
        for error_msg in error_messages:
            error_lower = error_msg.lower()
            for indicator in indicators:
                if indicator in error_lower:
                    return error_msg
        
        return ""
    
    def detect_validation_characteristics(
        self,
        component: SemanticComponent,
        validation_rules: List[ValidationRule],
    ) -> Dict[str, Any]:
        """Detect overall validation characteristics for a component.
        
        Args:
            component: The component to analyze
            validation_rules: Detected validation rules
            
        Returns:
            Dictionary of validation characteristics
        """
        characteristics = {
            "is_required": False,
            "has_format_validation": False,
            "has_length_validation": False,
            "has_range_validation": False,
            "has_pattern_validation": False,
            "validation_types": [],
            "validation_severity": "low",
        }
        
        for rule in validation_rules:
            characteristics["validation_types"].append(rule.validation_type)
            
            if rule.validation_type == "required":
                characteristics["is_required"] = True
                characteristics["validation_severity"] = "high"
            elif "format" in rule.validation_type:
                characteristics["has_format_validation"] = True
                characteristics["validation_severity"] = "medium"
            elif "length" in rule.validation_type:
                characteristics["has_length_validation"] = True
                characteristics["validation_severity"] = "medium"
            elif "value" in rule.validation_type:
                characteristics["has_range_validation"] = True
                characteristics["validation_severity"] = "medium"
            elif rule.validation_type == "pattern":
                characteristics["has_pattern_validation"] = True
                characteristics["validation_severity"] = "high"
        
        return characteristics