"""Post-LLM locator correction system.

This module provides post-processing to detect and fix obvious field mapping errors
where the LLM generates locators for the wrong field types.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LocatorCorrector:
    """Corrects obvious field mapping errors in generated locators."""
    
    # Field type patterns for detection
    FIELD_PATTERNS = {
        'username': [r'username', r'user', r'user-name', r'user_name'],
        'password': [r'password', r'pwd', r'pass'],
        'email': [r'email', r'mail', r'e-mail', r'e_mail'],
        'login': [r'login', r'sign\s*in', r'submit'],
        'first_name': [r'first\s*name', r'firstname', r'first_name'],
        'last_name': [r'last\s*name', r'lastname', r'last_name'],
    }
    
    # Priority locator types for each field type
    FIELD_LOCATOR_PRIORITIES = {
        'username': ['name="username"', 'name="user"', 'placeholder="username"', 'placeholder="user"'],
        'password': ['name="password"', 'name="pwd"', 'placeholder="password"', 'placeholder="pwd"'],
        'email': ['name="email"', 'type="email"', 'placeholder="email"'],
        'login': ['type="submit"', 'name="login"', 'data-testid="login"'],
    }
    
    def __init__(self, dom_snapshot: str = ""):
        """Initialize corrector with DOM snapshot for reference."""
        self.dom_snapshot = dom_snapshot
        self.corrections_made = []
    
    def detect_field_mapping_error(
        self,
        step_description: str,
        generated_locator: str
    ) -> Optional[Tuple[str, str, str]]:
        """Detect if a step description and generated locator have field type mismatch.
        
        Returns:
            Tuple of (detected_field_type, generated_field_type, suggested_correction) 
            or None if no error detected.
        """
        step_lower = step_description.lower()
        locator_lower = generated_locator.lower()
        
        # Detect intended field type from step description
        intended_field = None
        for field_type, patterns in self.FIELD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, step_lower):
                    intended_field = field_type
                    break
            if intended_field:
                break
        
        if not intended_field:
            return None
        
        # Detect actual field type from generated locator
        actual_field = None
        for field_type, patterns in self.FIELD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, locator_lower):
                    actual_field = field_type
                    break
            if actual_field:
                break
        
        # If no field detected in locator, it might be a generic locator
        if not actual_field:
            return None
        
        # Check for mismatch
        if intended_field != actual_field:
            logger.warning(
                f"Field mapping error detected: step mentions '{intended_field}' "
                f"but locator targets '{actual_field}'"
            )
            
            # Generate suggested correction
            suggested_correction = self._generate_correction(
                intended_field, generated_locator
            )
            
            return (intended_field, actual_field, suggested_correction)
        
        return None
    
    def _generate_correction(
        self,
        intended_field: str,
        original_locator: str
    ) -> str:
        """Generate a corrected locator for the intended field type."""
        
        # Try to find a suitable locator from DOM snapshot
        if self.dom_snapshot:
            corrected = self._find_locator_in_dom(intended_field)
            if corrected:
                return corrected
        
        # Fallback to priority locators
        priorities = self.FIELD_LOCATOR_PRIORITIES.get(intended_field, [])
        for priority in priorities:
            # Convert priority to actual locator syntax
            if 'name=' in priority:
                attr_value = priority.split('=')[1].strip('"\'')
                return f'page.locator("input[name=\'{attr_value}\']")'
            elif 'placeholder=' in priority:
                attr_value = priority.split('=')[1].strip('"\'')
                return f'page.get_by_placeholder("{attr_value}")'
            elif 'type=' in priority:
                attr_value = priority.split('=')[1].strip('"\'')
                return f'page.locator("input[type=\'{attr_value}\']")'
            elif 'data-testid=' in priority:
                attr_value = priority.split('=')[1].strip('"\'')
                return f'page.locator("[data-testid=\'{attr_value}\']")'
        
        # Ultimate fallback - keep original but add warning
        return original_locator
    
    def _find_locator_in_dom(self, field_type: str) -> Optional[str]:
        """Find a suitable locator for the field type in the DOM snapshot."""
        if not self.dom_snapshot:
            return None
        
        dom_lower = self.dom_snapshot.lower()
        
        # Look for patterns in DOM that match the field type
        patterns = self.FIELD_PATTERNS.get(field_type, [])
        for pattern in patterns:
            # Search for the pattern in DOM
            if re.search(pattern, dom_lower):
                # Try to extract a specific locator
                # Look for name attributes
                name_match = re.search(
                    rf'name=["\']({pattern})["\']',
                    dom_lower,
                    re.IGNORECASE
                )
                if name_match:
                    name_value = name_match.group(1)
                    return f'page.locator("input[name=\'{name_value}\']")'
                
                # Look for placeholder attributes
                placeholder_match = re.search(
                    rf'placeholder=["\']({pattern})["\']',
                    dom_lower,
                    re.IGNORECASE
                )
                if placeholder_match:
                    placeholder_value = placeholder_match.group(1)
                    return f'page.get_by_placeholder("{placeholder_value}")'
        
        return None
    
    def correct_script_locators(
        self,
        script: str,
        step_descriptions: List[str]
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Correct locator mapping errors in a generated script.
        
        Args:
            script: The generated Playwright script
            step_descriptions: List of step descriptions from the manual test
            
        Returns:
            Tuple of (corrected_script, list of corrections_made)
        """
        corrections = []
        corrected_script = script
        
        # Extract step comments and their locators
        step_pattern = r'# --- Step \d+: ([^-]+) ---'
        steps = re.finditer(step_pattern, script)
        
        for step_match in steps:
            step_desc = step_match.group(1).strip()
            step_start = step_match.start()
            
            # Find the next step or end of function
            next_step = re.search(r'# --- Step \d+:', script[step_start + 1:])
            if next_step:
                step_end = step_start + 1 + next_step.start()
            else:
                step_end = len(script)
            
            step_code = script[step_start:step_end]
            
            # Find locators in this step
            locator_pattern = r'(page\.(?:locator|get_by_\w+)\([^)]+\))'
            locators = re.finditer(locator_pattern, step_code)
            
            for locator_match in locators:
                locator = locator_match.group(1)
                
                # Check for field mapping error
                error = self.detect_field_mapping_error(step_desc, locator)
                if error:
                    intended_field, actual_field, correction = error
                    
                    logger.info(
                        f"Correcting locator: {locator} -> {correction} "
                        f"(intended: {intended_field}, actual: {actual_field})"
                    )
                    
                    # Replace in script
                    corrected_script = corrected_script.replace(locator, correction)
                    
                    corrections.append({
                        'step_description': step_desc,
                        'original_locator': locator,
                        'corrected_locator': correction,
                        'intended_field': intended_field,
                        'actual_field': actual_field,
                    })
        
        self.corrections_made = corrections
        return corrected_script, corrections
    
    def apply_corrections_to_fill_operations(
        self,
        script: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Specifically correct fill() operations that target wrong fields.
        
        This is a targeted fix for the common issue where fill() operations
        target the wrong field type (e.g., filling username value into password field).
        """
        corrections = []
        corrected_script = script
        
        # Pattern to find fill operations with comments
        fill_pattern = r'fill_ready\(page,\s*([^,]+),\s*"([^"]+)",\s*"([^"]+)"\)'
        
        for match in re.finditer(fill_pattern, script):
            locator = match.group(1)
            value = match.group(2)
            description = match.group(3)
            
            # Check if this is a field mapping error
            error = self.detect_field_mapping_error(description, locator)
            if error:
                intended_field, actual_field, correction = error
                
                logger.info(
                    f"Correcting fill operation: {description} "
                    f"(locator: {locator} -> {correction})"
                )
                
                # Replace the locator in the fill operation
                old_fill = match.group(0)
                new_fill = old_fill.replace(locator, correction)
                corrected_script = corrected_script.replace(old_fill, new_fill)
                
                corrections.append({
                    'description': description,
                    'value': value,
                    'original_locator': locator,
                    'corrected_locator': correction,
                    'intended_field': intended_field,
                    'actual_field': actual_field,
                })
        
        self.corrections_made = corrections
        return corrected_script, corrections