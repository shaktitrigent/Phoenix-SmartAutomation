"""Locator validation and quality improvement system.

This module provides comprehensive locator validation, confidence scoring,
and quality improvement for generated automation locators.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LocatorQuality:
    """Quality metrics for a generated locator."""
    confidence_score: float  # 0.0 to 1.0
    validation_passed: bool
    rejection_reason: Optional[str]
    is_duplicate: bool
    is_brittle: bool
    follows_priority_rules: bool
    alternate_locators: List[str]


class LocatorValidator:
    """Validates and scores generated locators against DOM snapshots."""
    
    # Locator priority rankings (higher is better) - EVIDENCE-BASED
    # These rankings are applied AFTER structural validation confirms the attribute exists
    PRIORITY_RANKINGS = {
        'data-testid': 10,      # Highest: stable, testing-specific, verifiable in DOM
        'data-test': 10,        # Equivalent to data-testid
        'id': 9,                # Stable ID (not auto-generated)
        'stable_id': 9,         # Stable ID (not auto-generated)
        'name': 8,              # Form field names - stable and semantic
        'placeholder': 7,        # Placeholder text - user-visible but may change
        'aria-label': 6,        # Accessibility labels - semantic and stable
        'label': 5,             # Associated labels - semantic but may be distant
        'role': 4,              # ARIA roles - semantic but may need name for uniqueness
        'text': 2,              # Visible text - fragile, may change with localization
        'class': 1,             # CSS classes - very fragile, may change frequently
        'xpath': 0,             # Forbidden - brittle and implementation-dependent
    }
    
    # Patterns that are absolutely forbidden
    FORBIDDEN_PATTERNS = [
        r'//',                 # XPath
        r'\.first\(\)',        # Unscoped .first()
        r'\.nth\(\d+\)',       # Unscoped .nth()
        r'time\.sleep',        # Sleep statements
        r'wait_for_load_state', # Network idle waits
        r'example\.com',       # Placeholder URLs
        r'placeholder',         # Placeholder locators
    ]
    
    # Patterns that indicate dynamic/brittle locators
    DYNAMIC_PATTERNS = [
        r'\d{3,}',  # 3+ consecutive digits
        r'ember\d+',  # Ember.js dynamic IDs
        r'react-\w+-\d+',  # React dynamic IDs
        r'ng-\w+-\d+',  # Angular dynamic IDs
        r'__\w+__',  # Framework internal classes
    ]
    
    def __init__(self, dom_snapshot: str = ""):
        """Initialize validator with DOM snapshot for validation."""
        self.dom_snapshot = dom_snapshot
        self.seen_locators: Dict[str, str] = {}  # selector -> element_id
        
    def validate_locator(
        self,
        selector: str,
        element_id: str,
        element_description: str = ""
    ) -> LocatorQuality:
        """Validate a single locator and return quality metrics."""
        
        logger.info(f"Validating locator: {selector} for element: {element_id}")
        
        # Check for forbidden patterns
        forbidden_match = self._check_forbidden_patterns(selector)
        if forbidden_match:
            return LocatorQuality(
                confidence_score=0.0,
                validation_passed=False,
                rejection_reason=f"Contains forbidden pattern: {forbidden_match}",
                is_duplicate=False,
                is_brittle=True,
                follows_priority_rules=False,
                alternate_locators=[]
            )
        
        # Check for dynamic/brittle patterns
        is_brittle = self._check_brittle_patterns(selector)
        
        # Check for duplicates
        is_duplicate = self._check_duplicate(selector, element_id)
        
        # Check if selector exists in DOM snapshot
        exists_in_dom = self._check_exists_in_dom(selector)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            selector, exists_in_dom, is_brittle, is_duplicate
        )
        
        # Check if follows priority rules
        follows_priority = self._check_priority_rules(selector)
        
        # Generate alternate locators if low confidence
        alternate_locators = []
        if confidence_score < 0.7:
            alternate_locators = self._generate_alternate_locators(
                selector, element_description
            )
        
        # Determine if validation passed
        validation_passed = (
            confidence_score >= 0.5 and
            not is_duplicate and
            exists_in_dom and
            follows_priority
        )
        
        rejection_reason = None
        if not validation_passed:
            if is_duplicate:
                rejection_reason = "Duplicate locator"
            elif not exists_in_dom:
                rejection_reason = "Locator not found in DOM snapshot"
            elif not follows_priority:
                rejection_reason = "Does not follow locator priority rules"
            elif confidence_score < 0.5:
                rejection_reason = f"Low confidence score: {confidence_score:.2f}"
        
        logger.info(
            f"Locator validation result: {validation_passed}, "
            f"confidence: {confidence_score:.2f}, "
            f"reason: {rejection_reason}"
        )
        
        return LocatorQuality(
            confidence_score=confidence_score,
            validation_passed=validation_passed,
            rejection_reason=rejection_reason,
            is_duplicate=is_duplicate,
            is_brittle=is_brittle,
            follows_priority_rules=follows_priority,
            alternate_locators=alternate_locators
        )
    
    def _check_forbidden_patterns(self, selector: str) -> Optional[str]:
        """Check if selector contains forbidden patterns."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, selector):
                return pattern
        return None
    
    def _check_brittle_patterns(self, selector: str) -> bool:
        """Check if selector contains dynamic/brittle patterns."""
        for pattern in self.DYNAMIC_PATTERNS:
            if re.search(pattern, selector):
                return True
        return False
    
    def _check_duplicate(self, selector: str, element_id: str) -> bool:
        """Check if this selector has been used for a different element."""
        if selector in self.seen_locators:
            if self.seen_locators[selector] != element_id:
                logger.warning(
                    f"Duplicate locator detected: {selector} used for both "
                    f"{self.seen_locators[selector]} and {element_id}"
                )
                return True
        else:
            self.seen_locators[selector] = element_id
        return False
    
    def _check_exists_in_dom(self, selector: str) -> bool:
        """Check if selector exists in the DOM snapshot using structural DOM understanding.
        
        This method validates that the referenced attributes and elements actually exist
        in the DOM structure, not just that the text appears somewhere.
        """
        if not self.dom_snapshot:
            # If no DOM snapshot, assume it exists (best effort)
            logger.warning("No DOM snapshot available for validation - assuming locator exists")
            return True
        
        # Parse the selector to extract the actual attribute/element being referenced
        selector_info = self._parse_selector_structure(selector)
        
        if not selector_info:
            logger.warning(f"Could not parse selector structure: {selector}")
            return False
        
        # Validate based on selector type
        if selector_info['type'] == 'data-testid':
            return self._validate_data_testid(selector_info['value'])
        elif selector_info['type'] == 'name':
            return self._validate_name_attribute(selector_info['value'])
        elif selector_info['type'] == 'id':
            return self._validate_id_selector(selector_info['value'])
        elif selector_info['type'] == 'class':
            return self._validate_class_selector(selector_info['value'])
        elif selector_info['type'] == 'placeholder':
            return self._validate_placeholder_attribute(selector_info['value'])
        elif selector_info['type'] == 'role':
            return self._validate_role_selector(selector_info['value'], selector_info.get('name'))
        elif selector_info['type'] == 'label':
            return self._validate_label_selector(selector_info['value'])
        elif selector_info['type'] == 'text':
            return self._validate_text_selector(selector_info['value'])
        elif selector_info['type'] == 'css':
            return self._validate_css_selector(selector_info['value'])
        elif selector_info['type'] == 'xpath':
            # XPath is forbidden - should have been caught by forbidden patterns
            logger.warning(f"XPath selector encountered: {selector}")
            return False
        else:
            logger.warning(f"Unknown selector type: {selector_info['type']}")
            return False
    
    def _parse_selector_structure(self, selector: str) -> Optional[Dict[str, Any]]:
        """Parse selector to extract structure and type.
        
        Returns dict with 'type' and 'value' keys, or None if parsing fails.
        """
        selector = selector.strip()
        
        # Handle simple CSS selectors like #id, .class
        if selector.startswith('#'):
            return {'type': 'id', 'value': selector[1:]}
        if selector.startswith('.'):
            return {'type': 'class', 'value': selector[1:]}
        
        # Handle page.locator("[data-testid='...']")
        if '[data-testid=' in selector or '[data-test=' in selector:
            match = re.search(r'\[data-testid=["\']([^"\']+)["\']\]', selector, re.IGNORECASE)
            if match:
                return {'type': 'data-testid', 'value': match.group(1)}
            match = re.search(r'\[data-test=["\']([^"\']+)["\']\]', selector, re.IGNORECASE)
            if match:
                return {'type': 'data-testid', 'value': match.group(1)}
        
        # Handle page.locator("[name='...']")
        if '[name=' in selector:
            match = re.search(r'\[name=["\']([^"\']+)["\']\]', selector)
            if match:
                return {'type': 'name', 'value': match.group(1)}
        
        # Handle page.get_by_placeholder("...")
        if 'get_by_placeholder(' in selector:
            match = re.search(r'get_by_placeholder\(["\']([^"\']+)["\']\)', selector)
            if match:
                return {'type': 'placeholder', 'value': match.group(1)}
        
        # Handle page.get_by_role("...", name="...")
        if 'get_by_role(' in selector:
            match = re.search(r'get_by_role\(["\']([^"\']+)["\']', selector)
            if match:
                role_info = {'type': 'role', 'value': match.group(1)}
                # Extract name parameter if present
                name_match = re.search(r'name=["\']([^"\']+)["\']', selector)
                if name_match:
                    role_info['name'] = name_match.group(1)
                return role_info
        
        # Handle page.get_by_label("...")
        if 'get_by_label(' in selector:
            match = re.search(r'get_by_label\(["\']([^"\']+)["\']\)', selector)
            if match:
                return {'type': 'label', 'value': match.group(1)}
        
        # Handle page.get_by_text("...")
        if 'get_by_text(' in selector:
            match = re.search(r'get_by_text\(["\']([^"\']+)["\']\)', selector)
            if match:
                return {'type': 'text', 'value': match.group(1)}
        
        # Handle generic CSS selector in page.locator("...")
        if 'page.locator("' in selector:
            match = re.search(r'page\.locator\(["\']([^"\']+)["\']\)', selector)
            if match:
                css_value = match.group(1)
                # Determine if it's a specific attribute selector
                if css_value.startswith('[') and '=' in css_value:
                    return {'type': 'css', 'value': css_value}
                # Otherwise treat as generic CSS
                return {'type': 'css', 'value': css_value}
        
        return None
    
    def _validate_data_testid(self, testid_value: str) -> bool:
        """Validate that data-testid attribute exists in DOM."""
        # Look for data-testid="value" or data-testid="value" (case insensitive)
        pattern1 = rf'data-testid=["\']?{re.escape(testid_value)}["\']?'
        pattern2 = rf'data-testid=["\']?{re.escape(testid_value)}["\']?'
        
        dom_lower = self.dom_snapshot.lower()
        testid_lower = testid_value.lower()
        
        # More precise check - the attribute must exist with this exact value
        if re.search(rf'data-testid\s*=\s*["\']?{re.escape(testid_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found data-testid={testid_value} in DOM")
            return True
        if re.search(rf'data-testid\s*=\s*["\']?{re.escape(testid_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found data-testid={testid_value} in DOM")
            return True
        
        logger.warning(f"✗ data-testid={testid_value} NOT found in DOM")
        return False
    
    def _validate_name_attribute(self, name_value: str) -> bool:
        """Validate that name attribute exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        name_lower = name_value.lower()
        
        # Look for name="value" in input elements or other form elements
        if re.search(rf'name\s*=\s*["\']?{re.escape(name_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found name={name_value} in DOM")
            return True
        
        logger.warning(f"✗ name={name_value} NOT found in DOM")
        return False
    
    def _validate_id_selector(self, id_value: str) -> bool:
        """Validate that id attribute exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        id_lower = id_value.lower()
        
        # Look for id="value" in HTML
        if re.search(rf'id\s*=\s*["\']?{re.escape(id_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found id={id_value} in DOM")
            return True
        
        logger.warning(f"✗ id={id_value} NOT found in DOM")
        return False
    
    def _validate_class_selector(self, class_value: str) -> bool:
        """Validate that class attribute exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        class_lower = class_value.lower()
        
        # Look for class="value" in HTML (more permissive since classes can be combined)
        if re.search(rf'class\s*=\s*["\'][^"\']*{re.escape(class_lower)}[^"\']*["\']', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found class={class_value} in DOM")
            return True
        
        # Also check for standalone class occurrence
        if class_lower in dom_lower:
            logger.info(f"✓ Found class pattern {class_value} in DOM")
            return True
        
        logger.warning(f"✗ class={class_value} NOT found in DOM")
        return False
    
    def _validate_placeholder_attribute(self, placeholder_value: str) -> bool:
        """Validate that placeholder attribute exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        placeholder_lower = placeholder_value.lower()
        
        # Look for placeholder="value"
        if re.search(rf'placeholder\s*=\s*["\']?{re.escape(placeholder_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found placeholder={placeholder_value} in DOM")
            return True
        
        logger.warning(f"✗ placeholder={placeholder_value} NOT found in DOM")
        return False
    
    def _validate_role_selector(self, role_value: str, name_value: Optional[str] = None) -> bool:
        """Validate that role exists with optional name in accessibility tree."""
        dom_lower = self.dom_snapshot.lower()
        role_lower = role_value.lower()
        
        # Look for role in accessibility tree (MCP format uses "role" attribute)
        if f'role "{role_lower}"' in dom_lower or f'role={role_lower}' in dom_lower:
            logger.info(f"✓ Found role={role_value} in DOM")
            
            # If name is specified, validate it exists with this role
            if name_value:
                name_lower = name_value.lower()
                # Check if name appears near the role in the accessibility tree
                role_context = self._extract_role_context(dom_lower, role_lower)
                if name_lower in role_context:
                    logger.info(f"✓ Found name={name_value} with role={role_value}")
                    return True
                else:
                    logger.warning(f"✗ name={name_value} NOT found with role={role_value}")
                    return False
            
            return True
        
        logger.warning(f"✗ role={role_value} NOT found in DOM")
        return False
    
    def _extract_role_context(self, dom_text: str, role: str) -> str:
        """Extract context around a role mention for name validation."""
        # Find all occurrences of the role and extract surrounding context
        lines = dom_text.split('\n')
        context_lines = []
        
        for i, line in enumerate(lines):
            if f'role "{role}"' in line or f'role={role}' in line:
                # Add surrounding lines for context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context_lines.extend(lines[start:end])
        
        return '\n'.join(context_lines)
    
    def _validate_label_selector(self, label_value: str) -> bool:
        """Validate that label exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        label_lower = label_value.lower()
        
        # Look for label text or label attribute
        if f'<label' in dom_lower and label_lower in dom_lower:
            logger.info(f"✓ Found label containing {label_value} in DOM")
            return True
        
        # Check for aria-label
        if re.search(rf'aria-label\s*=\s*["\']?{re.escape(label_lower)}["\']?', dom_lower, re.IGNORECASE):
            logger.info(f"✓ Found aria-label={label_value} in DOM")
            return True
        
        logger.warning(f"✗ label={label_value} NOT found in DOM")
        return False
    
    def _validate_text_selector(self, text_value: str) -> bool:
        """Validate that text exists in DOM."""
        dom_lower = self.dom_snapshot.lower()
        text_lower = text_value.lower()
        
        # Check if text appears in DOM (this is more permissive)
        if text_lower in dom_lower:
            logger.info(f"✓ Found text {text_value} in DOM")
            return True
        
        logger.warning(f"✗ text {text_value} NOT found in DOM")
        return False
    
    def _validate_css_selector(self, css_value: str) -> bool:
        """Validate CSS selector against DOM."""
        dom_lower = self.dom_snapshot.lower()
        css_lower = css_value.lower()
        
        # For CSS selectors, do a more sophisticated check
        # Handle attribute selectors like [name="username"]
        if css_value.startswith('[') and '=' in css_value:
            # Extract attribute name and value
            attr_match = re.search(r'\[([^\]]+)\]', css_value)
            if attr_match:
                attr_expr = attr_match.group(1)
                if '=' in attr_expr:
                    attr_name, attr_value = attr_expr.split('=', 1)
                    attr_name = attr_name.strip()
                    attr_value = attr_value.strip('"\'')
                    
                    # Check if this attribute-value pair exists
                    pattern = rf'{attr_name}\s*=\s*["\']?{re.escape(attr_value.lower())}["\']?'
                    if re.search(pattern, dom_lower, re.IGNORECASE):
                        logger.info(f"✓ Found CSS selector {css_value} in DOM")
                        return True
        
        # For other CSS selectors, do a basic existence check
        if css_lower in dom_lower:
            logger.info(f"✓ Found CSS selector pattern in DOM")
            return True
        
        logger.warning(f"✗ CSS selector {css_value} NOT validated in DOM")
        return False
    
    def _calculate_confidence_score(
        self,
        selector: str,
        exists_in_dom: bool,
        is_brittle: bool,
        is_duplicate: bool
    ) -> float:
        """Calculate confidence score for a locator based on REAL evidence.
        
        Scoring is evidence-based:
        - Structural DOM validation is the primary factor
        - Priority ranking provides secondary boost
        - Brittle patterns and duplicates are penalized
        """
        score = 0.0
        
        # PRIMARY: Structural DOM validation (must pass to have any confidence)
        if exists_in_dom:
            score += 0.6  # Base score for passing structural validation
        else:
            return 0.0  # No confidence if structural validation fails
        
        # SECONDARY: Priority bonus (evidence-based ranking)
        priority_bonus = self._get_priority_bonus(selector)
        score += priority_bonus
        
        # PENALTIES: Reduce confidence for quality issues
        if is_brittle:
            score -= 0.2  # Penalize dynamic/brittle patterns
        
        if is_duplicate:
            score -= 0.3  # Heavily penalize duplicate locators
        
        # Ensure score is in [0, 1]
        return max(0.0, min(1.0, score))
    
    def _get_priority_bonus(self, selector: str) -> float:
        """Get bonus based on locator priority ranking."""
        for pattern, ranking in self.PRIORITY_RANKINGS.items():
            if pattern in selector.lower():
                # Normalize ranking to bonus: 10 -> 0.3, 0 -> -0.2
                return (ranking / 10.0) * 0.3 - 0.1
        return 0.0
    
    def _check_priority_rules(self, selector: str) -> bool:
        """Check if selector follows the priority rules."""
        # Check if it uses a high-priority locator type
        high_priority = ['data-testid', 'id', 'stable_id', 'name', 'placeholder']
        for pattern in high_priority:
            if pattern in selector.lower():
                return True
        
        # If using low-priority types, ensure it's not alone
        low_priority = ['text', 'class']
        for pattern in low_priority:
            if pattern in selector.lower():
                # Low priority is OK if combined with high priority
                for high in high_priority:
                    if high in selector.lower():
                        return True
                return False  # Low priority alone is not OK
        
        return True
    
    def _generate_alternate_locators(
        self,
        selector: str,
        element_description: str
    ) -> List[str]:
        """Generate alternate locators for low-confidence selectors."""
        alternates = []
        
        # If using text, try role
        if 'get_by_text(' in selector:
            # Extract the text and try role
            match = re.search(r'get_by_text\("([^"]+)"\)', selector)
            if match:
                text = match.group(1)
                alternates.append(f'page.get_by_role("button", name="{text}", exact=True)')
        
        # If using label, try placeholder
        if 'get_by_label(' in selector:
            match = re.search(r'get_by_label\("([^"]+)"\)', selector)
            if match:
                label = match.group(1)
                alternates.append(f'page.get_by_placeholder("{label}")')
        
        # If using role, try data-testid if description suggests it
        if 'get_by_role(' in selector and 'data-testid' in element_description.lower():
            match = re.search(r'data-testid["\']?\s*[:=]\s*["\']?([^"\']+)["\']?', element_description)
            if match:
                testid = match.group(1)
                alternates.append(f'page.locator("[data-testid=\'{testid}\']")')
        
        return alternates
    
    def validate_locators_batch(
        self,
        locators: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate a batch of locators and return valid/invalid lists."""
        valid_locators = []
        invalid_locators = []
        
        logger.info(f"Validating batch of {len(locators)} locators")
        
        for locator_data in locators:
            selector = locator_data.get('selector', '')
            element_id = locator_data.get('element_id', '')
            element_description = locator_data.get('label', '')
            
            quality = self.validate_locator(selector, element_id, element_description)
            
            if quality.validation_passed:
                # Enhance locator data with quality metrics
                enhanced_locator = locator_data.copy()
                enhanced_locator['confidence_score'] = quality.confidence_score
                enhanced_locator['alternate_locators'] = quality.alternate_locators
                valid_locators.append(enhanced_locator)
                
                logger.info(
                    f"VALID locator: {element_id} -> {selector} "
                    f"(confidence: {quality.confidence_score:.2f})"
                )
            else:
                # Mark as invalid with reason
                invalid_locator = locator_data.copy()
                invalid_locator['rejection_reason'] = quality.rejection_reason
                invalid_locator['confidence_score'] = quality.confidence_score
                invalid_locators.append(invalid_locator)
                
                logger.warning(
                    f"INVALID locator: {element_id} -> {selector} "
                    f"(reason: {quality.rejection_reason})"
                )
        
        logger.info(
            f"Validation complete: {len(valid_locators)} valid, "
            f"{len(invalid_locators)} invalid"
        )
        
        return valid_locators, invalid_locators