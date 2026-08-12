"""Locator Intelligence - Generic Multi-Strategy Locator Generation (Priority 22).

This module generates multiple locator strategies for each component with
confidence scores, stability analysis, and uniqueness scoring.

This is completely generic and works for ANY web application without product-specific rules.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    LocatorCandidate,
)

logger = logging.getLogger(__name__)


class LocatorIntelligence:
    """Generic locator intelligence for generating multiple locator strategies.
    
    This intelligence generates:
    - Role-based locators (preferred)
    - Accessible name locators
    - Label-based locators
    - Placeholder-based locators
    - Test ID locators
    - Name attribute locators
    - ID-based locators
    - Stable CSS selectors
    - Text-based locators
    - XPath locators (last resort)
    
    Each locator is scored for:
    - Confidence (how likely to work)
    - Stability (how likely to remain unchanged)
    - Uniqueness (how likely to be unique on page)
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the locator intelligence."""
        self.locator_strategies = self._initialize_locator_strategies()
        logger.info(f"[LOCATOR INTELLIGENCE] Initialized with {len(self.locator_strategies)} strategies")
    
    def _initialize_locator_strategies(self) -> List[Dict[str, Any]]:
        """Initialize locator strategy priorities."""
        strategies = [
            {
                "name": "role",
                "priority": 1,
                "confidence_base": 0.95,
                "stability_base": 0.9,
                "uniqueness_base": 0.7,
            },
            {
                "name": "test_id",
                "priority": 2,
                "confidence_base": 0.98,
                "stability_base": 0.95,
                "uniqueness_base": 0.95,
            },
            {
                "name": "accessible_name",
                "priority": 3,
                "confidence_base": 0.9,
                "stability_base": 0.85,
                "uniqueness_base": 0.8,
            },
            {
                "name": "label",
                "priority": 4,
                "confidence_base": 0.85,
                "stability_base": 0.8,
                "uniqueness_base": 0.75,
            },
            {
                "name": "placeholder",
                "priority": 5,
                "confidence_base": 0.8,
                "stability_base": 0.75,
                "uniqueness_base": 0.7,
            },
            {
                "name": "name",
                "priority": 6,
                "confidence_base": 0.85,
                "stability_base": 0.85,
                "uniqueness_base": 0.8,
            },
            {
                "name": "id",
                "priority": 7,
                "confidence_base": 0.9,
                "stability_base": 0.7,
                "uniqueness_base": 0.85,
            },
            {
                "name": "stable_css",
                "priority": 8,
                "confidence_base": 0.75,
                "stability_base": 0.6,
                "uniqueness_base": 0.65,
            },
            {
                "name": "text",
                "priority": 9,
                "confidence_base": 0.7,
                "stability_base": 0.5,
                "uniqueness_base": 0.6,
            },
            {
                "name": "xpath",
                "priority": 10,
                "confidence_base": 0.6,
                "stability_base": 0.4,
                "uniqueness_base": 0.5,
            },
        ]
        
        return strategies
    
    def generate_locator_candidates(
        self,
        component: SemanticComponent,
        page_context: Dict[str, Any] = None,
    ) -> List[LocatorCandidate]:
        """Generate multiple locator candidates for a component.
        
        Args:
            component: The component to generate locators for
            page_context: Context about the page (other components, etc.)
            
        Returns:
            List of locator candidates with confidence scores
        """
        page_context = page_context or {}
        candidates = []
        
        # Generate candidates for each strategy
        for strategy in self.locator_strategies:
            candidate = self._generate_locator_for_strategy(
                component,
                strategy,
                page_context,
            )
            
            if candidate:
                candidates.append(candidate)
        
        # Sort by priority and confidence
        candidates.sort(key=lambda c: (c.confidence + c.stability_score + c.uniqueness_score) / 3, reverse=True)
        
        logger.info(f"[LOCATOR INTELLIGENCE] Generated {len(candidates)} locator candidates for component")
        
        return candidates
    
    def _generate_locator_for_strategy(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
        page_context: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate a locator for a specific strategy."""
        strategy_name = strategy["name"]
        
        if strategy_name == "role":
            return self._generate_role_locator(component, strategy)
        elif strategy_name == "test_id":
            return self._generate_test_id_locator(component, strategy)
        elif strategy_name == "accessible_name":
            return self._generate_accessible_name_locator(component, strategy)
        elif strategy_name == "label":
            return self._generate_label_locator(component, strategy)
        elif strategy_name == "placeholder":
            return self._generate_placeholder_locator(component, strategy)
        elif strategy_name == "name":
            return self._generate_name_locator(component, strategy)
        elif strategy_name == "id":
            return self._generate_id_locator(component, strategy)
        elif strategy_name == "stable_css":
            return self._generate_stable_css_locator(component, strategy, page_context)
        elif strategy_name == "text":
            return self._generate_text_locator(component, strategy)
        elif strategy_name == "xpath":
            return self._generate_xpath_locator(component, strategy)
        
        return None
    
    def _generate_role_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate role-based locator (preferred strategy)."""
        if not component.aria_role:
            return None
        
        # Build role locator
        locator = f"get_by_role('{component.aria_role}'"
        
        # Add name if available
        if component.aria_label:
            locator += f", name='{component.aria_label}'"
        elif component.name:
            locator += f", name='{component.name}'"
        elif component.label:
            locator += f", name='{component.label}'"
        
        locator += ")"
        
        return LocatorCandidate(
            strategy="role",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["ARIA role present", "Semantic locator"],
            generation_method="role_based",
        )
    
    def _generate_test_id_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate test ID locator (highest priority if available)."""
        # Check for common test ID attributes
        test_id_attrs = ["data-testid", "data-test-id", "test-id", "data-cy", "data-qa"]
        
        for attr in test_id_attrs:
            if attr in component.attributes:
                test_id = component.attributes[attr]
                locator = f"get_by_test_id('{test_id}')"
                
                return LocatorCandidate(
                    strategy="test_id",
                    locator=locator,
                    confidence=strategy["confidence_base"],
                    stability_score=strategy["stability_base"],
                    uniqueness_score=strategy["uniqueness_base"],
                    evidence=[f"Test ID attribute found: {attr}"],
                    generation_method="test_id",
                )
        
        return None
    
    def _generate_accessible_name_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate accessible name locator."""
        if not component.aria_label and not component.label:
            return None
        
        name = component.aria_label or component.label
        locator = f"get_by_role('{component.aria_role or component.component_type.value}', name='{name}')"
        
        return LocatorCandidate(
            strategy="accessible_name",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["Accessible name present"],
            generation_method="accessible_name",
        )
    
    def _generate_label_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate label-based locator."""
        if not component.label:
            return None
        
        locator = f"get_by_label('{component.label}')"
        
        return LocatorCandidate(
            strategy="label",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["Label present"],
            generation_method="label",
        )
    
    def _generate_placeholder_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate placeholder-based locator."""
        if not component.placeholder:
            return None
        
        locator = f"get_by_placeholder('{component.placeholder}')"
        
        return LocatorCandidate(
            strategy="placeholder",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["Placeholder present"],
            generation_method="placeholder",
        )
    
    def _generate_name_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate name attribute locator."""
        if not component.name:
            return None
        
        locator = f"get_by_name('{component.name}')"
        
        return LocatorCandidate(
            strategy="name",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["Name attribute present"],
            generation_method="name",
        )
    
    def _generate_id_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate ID-based locator."""
        if not component.element_id:
            return None
        
        # Check if ID looks stable (not auto-generated)
        if self._is_stable_id(component.element_id):
            locator = f"get_by_id('{component.element_id}')"
            
            return LocatorCandidate(
                strategy="id",
                locator=locator,
                confidence=strategy["confidence_base"],
                stability_score=strategy["stability_base"],
                uniqueness_score=strategy["uniqueness_base"],
                evidence=["Stable ID present"],
                generation_method="id",
            )
        
        return None
    
    def _generate_stable_css_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
        page_context: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate stable CSS selector locator."""
        if not component.css_selector:
            return None
        
        # Check if CSS selector looks stable
        if self._is_stable_css(component.css_selector):
            locator = f"locator('{component.css_selector}')"
            
            return LocatorCandidate(
                strategy="stable_css",
                locator=locator,
                confidence=strategy["confidence_base"],
                stability_score=strategy["stability_base"],
                uniqueness_score=strategy["uniqueness_base"],
                evidence=["Stable CSS selector present"],
                generation_method="css_selector",
            )
        
        return None
    
    def _generate_text_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate text-based locator."""
        if not component.text_content:
            return None
        
        # Use exact text match
        locator = f"get_by_text('{component.text_content}')"
        
        return LocatorCandidate(
            strategy="text",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["Text content present"],
            generation_method="text",
        )
    
    def _generate_xpath_locator(
        self,
        component: SemanticComponent,
        strategy: Dict[str, Any],
    ) -> Optional[LocatorCandidate]:
        """Generate XPath locator (last resort)."""
        if not component.xpath:
            return None
        
        locator = f"locator('xpath={component.xpath}')"
        
        return LocatorCandidate(
            strategy="xpath",
            locator=locator,
            confidence=strategy["confidence_base"],
            stability_score=strategy["stability_base"],
            uniqueness_score=strategy["uniqueness_base"],
            evidence=["XPath available (last resort)"],
            generation_method="xpath",
        )
    
    def _is_stable_id(self, element_id: str) -> bool:
        """Check if an ID is likely to be stable."""
        # Unstable patterns
        unstable_patterns = [
            r"^\d+$",  # Pure numbers
            r"^[a-f0-9]{32,}$",  # Hash-like strings
            r"auto.*",  # Auto-generated
            r"random.*",  # Random
            r"temp.*",  # Temporary
            r".*\d{10,}.*",  # Contains long numbers (timestamps)
        ]
        
        element_id_lower = element_id.lower()
        
        for pattern in unstable_patterns:
            if re.match(pattern, element_id_lower):
                return False
        
        return True
    
    def _is_stable_css(self, css_selector: str) -> bool:
        """Check if a CSS selector is likely to be stable."""
        # Unstable patterns
        unstable_patterns = [
            r":nth-child\(\d+\)",  # Positional selectors
            r":nth-of-type\(\d+\)",  # Positional selectors
            r">\s*\d+",  # Direct child with number
            r"\[class.*\d+.*\]",  # Classes with numbers
        ]
        
        for pattern in unstable_patterns:
            if re.search(pattern, css_selector):
                return False
        
        return True
    
    def select_best_locator(
        self,
        candidates: List[LocatorCandidate],
        min_confidence: float = 0.7,
    ) -> Optional[LocatorCandidate]:
        """Select the best locator from candidates.
        
        Args:
            candidates: List of locator candidates
            min_confidence: Minimum confidence threshold
            
        Returns:
            Best locator candidate or None
        """
        if not candidates:
            return None
        
        # Filter by confidence
        qualified = [c for c in candidates if c.confidence >= min_confidence]
        
        if not qualified:
            # Fall back to highest confidence even if below threshold
            qualified = candidates[:1]
        
        # Select by combined score (confidence + stability + uniqueness)
        best = max(qualified, key=lambda c: (c.confidence + c.stability_score + c.uniqueness_score) / 3)
        
        logger.info(f"[LOCATOR INTELLIGENCE] Selected best locator: {best.strategy} (confidence: {best.confidence:.2f})")
        
        return best