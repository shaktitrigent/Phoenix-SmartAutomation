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
    
    # Locator priority rankings (higher is better)
    PRIORITY_RANKINGS = {
        'data-testid': 10,
        'stable_id': 9,
        'name': 8,
        'placeholder': 7,
        'aria-label': 6,
        'label': 5,
        'role': 4,
        'text': 2,
        'class': 1,
        'xpath': 0,  # Forbidden
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
        """Check if selector exists in the DOM snapshot."""
        if not self.dom_snapshot:
            # If no DOM snapshot, assume it exists (best effort)
            return True
        
        # Extract the key part of the selector for checking
        # This is a simplified check - in production, you'd parse the selector properly
        selector_key = self._extract_selector_key(selector)
        return selector_key.lower() in self.dom_snapshot.lower()
    
    def _extract_selector_key(self, selector: str) -> str:
        """Extract the meaningful part of a selector for DOM checking."""
        # Remove function calls and extract the core selector
        selector = selector.strip()
        
        # Handle page.locator("...")
        if 'page.locator("' in selector:
            match = re.search(r'page\.locator\("([^"]+)"\)', selector)
            if match:
                return match.group(1)
        
        # Handle get_by_role("...", name="...")
        if 'get_by_role(' in selector:
            match = re.search(r'get_by_role\("([^"]+)"', selector)
            if match:
                return match.group(1)
        
        # Handle get_by_label("...")
        if 'get_by_label(' in selector:
            match = re.search(r'get_by_label\("([^"]+)"', selector)
            if match:
                return match.group(1)
        
        # Handle get_by_placeholder("...")
        if 'get_by_placeholder(' in selector:
            match = re.search(r'get_by_placeholder\("([^"]+)"', selector)
            if match:
                return match.group(1)
        
        # Handle [data-testid="..."]
        if '[data-testid=' in selector:
            match = re.search(r'\[data-testid="([^"]+)"\]', selector)
            if match:
                return match.group(1)
        
        # Fallback: return the selector as-is
        return selector
    
    def _calculate_confidence_score(
        self,
        selector: str,
        exists_in_dom: bool,
        is_brittle: bool,
        is_duplicate: bool
    ) -> float:
        """Calculate confidence score for a locator."""
        score = 1.0
        
        # Penalize if not in DOM
        if not exists_in_dom:
            score -= 0.4
        
        # Penalize brittle patterns
        if is_brittle:
            score -= 0.3
        
        # Penalize duplicates heavily
        if is_duplicate:
            score -= 0.5
        
        # Add bonus based on priority
        priority_bonus = self._get_priority_bonus(selector)
        score += priority_bonus
        
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
        high_priority = ['data-testid', 'stable_id', 'name', 'placeholder']
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