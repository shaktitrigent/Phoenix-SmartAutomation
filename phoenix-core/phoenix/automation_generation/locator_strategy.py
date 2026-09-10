"""Universal Locator Strategy - Evidence-driven locator selection with fallback chain.

This module implements a generic locator strategy that uses Priority 22 Locator Intelligence
and adds a controlled fallback chain for every executable action.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

from phoenix.semantic.models import SemanticComponent, LocatorCandidate
from phoenix.execution.locator_repository import LocatorRepository, LocatorEntry

logger = logging.getLogger(__name__)


class LocatorStrategy(str, Enum):
    """Locator strategy types in priority order."""
    
    TEST_ID = "test_id"
    ROLE = "role"
    ACCESSIBLE_NAME = "accessible_name"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    NAME = "name"
    ID = "id"
    STABLE_CSS = "stable_css"
    TEXT = "text"
    XPATH = "xpath"
    UNKNOWN = "unknown"


class LocatorFallback(BaseModel):
    """Represents a single fallback locator with reasoning."""
    
    locator: str = Field(..., description="Fallback locator string")
    strategy: LocatorStrategy = Field(..., description="Locator strategy")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Locator confidence")
    reason: str = Field(..., description="Reason for this fallback")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")


class LocatorChain(BaseModel):
    """Represents a complete locator fallback chain for an action."""
    
    action_id: str = Field(..., description="Associated action ID")
    primary_locator: str = Field(..., description="Primary locator")
    primary_strategy: LocatorStrategy = Field(..., description="Primary strategy")
    primary_confidence: float = Field(..., ge=0.0, le=1.0, description="Primary confidence")
    
    fallbacks: List[LocatorFallback] = Field(default_factory=list, description="Fallback chain")
    
    # Repository integration
    repository_locator: Optional[str] = Field(default=None, description="Locator from repository")
    repository_confidence: float = Field(default=0.0, description="Repository locator confidence")
    
    # Healing candidate
    healing_candidate: Optional[str] = Field(default=None, description="Healing candidate locator")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LocatorStrategyManager:
    """Universal locator strategy manager with fallback chain.
    
    This manager:
    - Uses Priority 22 Locator Intelligence
    - Implements evidence-driven locator selection
    - Provides controlled fallback chain for every action
    - Integrates with Locator Repository
    - Maintains confidence and evidence
    - Prevents random selector trials
    """
    
    def __init__(
        self,
        locator_repository: Optional[LocatorRepository] = None,
    ):
        self.locator_repository = locator_repository
        
        # Strategy priority order (as specified in Priority 24)
        self.strategy_priority = [
            LocatorStrategy.TEST_ID,
            LocatorStrategy.ROLE,
            LocatorStrategy.ACCESSIBLE_NAME,
            LocatorStrategy.LABEL,
            LocatorStrategy.PLACEHOLDER,
            LocatorStrategy.NAME,
            LocatorStrategy.ID,
            LocatorStrategy.STABLE_CSS,
            LocatorStrategy.TEXT,
            LocatorStrategy.XPATH,
        ]
        
        # Strategy base confidence scores
        self.strategy_confidence = {
            LocatorStrategy.TEST_ID: 0.98,
            LocatorStrategy.ROLE: 0.95,
            LocatorStrategy.ACCESSIBLE_NAME: 0.90,
            LocatorStrategy.LABEL: 0.85,
            LocatorStrategy.PLACEHOLDER: 0.80,
            LocatorStrategy.NAME: 0.85,
            LocatorStrategy.ID: 0.90,
            LocatorStrategy.STABLE_CSS: 0.75,
            LocatorStrategy.TEXT: 0.70,
            LocatorStrategy.XPATH: 0.60,
        }
        
        logger.info("LocatorStrategyManager initialized")
    
    def create_locator_chain(
        self,
        action_id: str,
        component: SemanticComponent,
        project_name: str = "",
        page_name: str = "",
    ) -> LocatorChain:
        """Create a complete locator fallback chain for an action.
        
        Args:
            action_id: ID of the action
            component: Semantic component for the action
            project_name: Project name for repository lookup
            page_name: Page name for repository lookup
            
        Returns:
            Complete LocatorChain with fallbacks
        """
        # Get primary locator from component
        primary_locator, primary_strategy, primary_confidence = self._select_primary_locator(
            component
        )
        
        # Create fallback chain
        fallbacks = self._create_fallback_chain(component, primary_strategy)
        
        # Check repository for existing locator
        repository_locator, repository_confidence = self._check_repository(
            component,
            project_name,
            page_name,
        )
        
        # Generate healing candidate
        healing_candidate = self._generate_healing_candidate(component)
        
        chain = LocatorChain(
            action_id=action_id,
            primary_locator=primary_locator,
            primary_strategy=primary_strategy,
            primary_confidence=primary_confidence,
            fallbacks=fallbacks,
            repository_locator=repository_locator,
            repository_confidence=repository_confidence,
            healing_candidate=healing_candidate,
        )
        
        logger.debug(
            f"Created locator chain for {action_id}: "
            f"primary={primary_strategy.value} ({primary_confidence:.2f}), "
            f"{len(fallbacks)} fallbacks"
        )
        
        return chain
    
    def _select_primary_locator(
        self,
        component: SemanticComponent,
    ) -> Tuple[str, LocatorStrategy, float]:
        """Select primary locator using evidence-driven strategy."""
        # If component already has a selected locator with high confidence, use it
        if component.selected_locator and component.locator_confidence >= 0.8:
            strategy = self._infer_strategy_from_locator(component.selected_locator)
            return component.selected_locator, strategy, component.locator_confidence
        
        # Otherwise, select best from candidates using priority order
        if component.locator_candidates:
            for strategy in self.strategy_priority:
                for candidate in component.locator_candidates:
                    candidate_strategy = self._infer_strategy_from_locator(
                        candidate.get("locator", "")
                    )
                    if candidate_strategy == strategy:
                        confidence = candidate.get("confidence", 0.0)
                        if confidence >= 0.7:
                            return (
                                candidate.get("locator", ""),
                                strategy,
                                confidence,
                            )
        
        # Fallback to first candidate
        if component.locator_candidates:
            best = max(
                component.locator_candidates,
                key=lambda x: x.get("confidence", 0.0),
            )
            strategy = self._infer_strategy_from_locator(best.get("locator", ""))
            return best.get("locator", ""), strategy, best.get("confidence", 0.5)
        
        # Generate from component attributes
        return self._generate_locator_from_component(component)
    
    def _infer_strategy_from_locator(self, locator: str) -> LocatorStrategy:
        """Infer locator strategy from locator string."""
        locator_lower = locator.lower()
        
        if "get_by_test_id" in locator_lower or "data-testid" in locator_lower:
            return LocatorStrategy.TEST_ID
        elif "get_by_role" in locator_lower:
            return LocatorStrategy.ROLE
        elif "get_by_alt_text" in locator_lower or "accessible_name" in locator_lower:
            return LocatorStrategy.ACCESSIBLE_NAME
        elif "get_by_label" in locator_lower:
            return LocatorStrategy.LABEL
        elif "get_by_placeholder" in locator_lower:
            return LocatorStrategy.PLACEHOLDER
        elif "get_by_name" in locator_lower:
            return LocatorStrategy.NAME
        elif "get_by_id" in locator_lower or "#" in locator_lower:
            return LocatorStrategy.ID
        elif "get_by_text" in locator_lower:
            return LocatorStrategy.TEXT
        elif "xpath" in locator_lower or "//" in locator_lower:
            return LocatorStrategy.XPATH
        else:
            return LocatorStrategy.STABLE_CSS
    
    def _create_fallback_chain(
        self,
        component: SemanticComponent,
        primary_strategy: LocatorStrategy,
    ) -> List[LocatorFallback]:
        """Create controlled fallback chain."""
        fallbacks = []
        
        # Generate fallbacks for each strategy in priority order (excluding primary)
        for strategy in self.strategy_priority:
            if strategy == primary_strategy:
                continue
            
            locator = self._generate_locator_by_strategy(component, strategy)
            if locator:
                confidence = self.strategy_confidence.get(strategy, 0.5)
                
                fallback = LocatorFallback(
                    locator=locator,
                    strategy=strategy,
                    confidence=confidence,
                    reason=f"Alternative {strategy.value} strategy",
                    evidence=[f"Generated from {strategy.value} strategy"],
                )
                fallbacks.append(fallback)
        
        return fallbacks
    
    def _generate_locator_by_strategy(
        self,
        component: SemanticComponent,
        strategy: LocatorStrategy,
    ) -> Optional[str]:
        """Generate a locator using a specific strategy.
        
        CRITICAL FIX: Sanitize attribute values to prevent unrealistic test IDs
        and ensure realistic locator generation.
        """
        # Helper function to sanitize attribute values
        def sanitize_value(value: str) -> str:
            """Sanitize attribute value to prevent unrealistic test IDs."""
            if not value:
                return ""
            # Remove overly long descriptive text that's not a real attribute
            if len(value) > 50 and " " in value:
                # This is likely descriptive text, not a real attribute value
                logger.warning(f"Skipping unrealistic attribute value: {value[:50]}...")
                return ""
            # Remove quotes and special characters that could break selectors
            return value.replace('"', '').replace("'", "").strip()
        
        if strategy == LocatorStrategy.TEST_ID:
            test_id = component.attributes.get("data-testid", "")
            sanitized_test_id = sanitize_value(test_id)
            if sanitized_test_id and len(sanitized_test_id) < 50:
                return f'get_by_test_id("{sanitized_test_id}")'
        
        elif strategy == LocatorStrategy.ROLE:
            if component.aria_role:
                aria_label = sanitize_value(component.aria_label or "")
                label = sanitize_value(component.label or "")
                
                if aria_label and len(aria_label) < 50:
                    return f'get_by_role("{component.aria_role}", name="{aria_label}")'
                elif label and len(label) < 50:
                    return f'get_by_role("{component.aria_role}", name="{label}")'
                else:
                    return f'get_by_role("{component.aria_role}")'
        
        elif strategy == LocatorStrategy.ACCESSIBLE_NAME:
            aria_label = sanitize_value(component.aria_label or "")
            if aria_label and len(aria_label) < 50:
                return f'get_by_alt_text("{aria_label}")'
        
        elif strategy == LocatorStrategy.LABEL:
            label = sanitize_value(component.label or "")
            if label and len(label) < 50:
                return f'get_by_label("{label}")'
        
        elif strategy == LocatorStrategy.PLACEHOLDER:
            placeholder = sanitize_value(component.placeholder or "")
            if placeholder and len(placeholder) < 50:
                return f'get_by_placeholder("{placeholder}")'
        
        elif strategy == LocatorStrategy.NAME:
            name = sanitize_value(component.name or "")
            if name and len(name) < 50:
                return f'get_by_name("{name}")'
        
        elif strategy == LocatorStrategy.ID:
            element_id = sanitize_value(component.element_id or "")
            if element_id and len(element_id) < 50:
                return f'get_by_id("{element_id}")'
        
        elif strategy == LocatorStrategy.TEXT:
            text_content = sanitize_value(component.text_content or "")
            if text_content and len(text_content) < 30:  # Text locators should be short
                return f'get_by_text("{text_content}")'
        
        elif strategy == LocatorStrategy.STABLE_CSS:
            css_selector = sanitize_value(component.css_selector or "")
            if css_selector and len(css_selector) < 100:
                return f'locator("{css_selector}")'
        
        elif strategy == LocatorStrategy.XPATH:
            xpath = sanitize_value(component.xpath or "")
            if xpath and len(xpath) < 100:
                return f'locator("xpath={xpath}")'
        
        return None
    
    def _generate_locator_from_component(
        self,
        component: SemanticComponent,
    ) -> Tuple[str, LocatorStrategy, float]:
        """Generate locator from component attributes when no candidates exist."""
        # Try strategies in priority order
        for strategy in self.strategy_priority:
            locator = self._generate_locator_by_strategy(component, strategy)
            if locator:
                confidence = self.strategy_confidence.get(strategy, 0.5)
                return locator, strategy, confidence
        
        # Ultimate fallback
        return 'locator("body")', LocatorStrategy.XPATH, 0.3
    
    def _check_repository(
        self,
        component: SemanticComponent,
        project_name: str,
        page_name: str,
    ) -> Tuple[Optional[str], float]:
        """Check locator repository for existing locator."""
        if not self.locator_repository:
            return None, 0.0
        
        if not project_name or not page_name:
            return None, 0.0
        
        element_name = component.semantic_purpose or component.component_type.value
        entry = self.locator_repository.get_locator(
            project_name,
            page_name,
            element_name,
            min_confidence=0.7,
        )
        
        if entry:
            return entry.locator, entry.confidence
        
        return None, 0.0
    
    def _generate_healing_candidate(
        self,
        component: SemanticComponent,
    ) -> Optional[str]:
        """Generate a healing candidate locator.
        
        IMPORTANT: Do NOT use blind .first selection. Always use context-based
        approaches that identify the intended element through semantic attributes,
        parent context, or stable properties.
        """
        # Use semantic information for healing
        if component.semantic_purpose:
            # Try role + purpose combination (context-based)
            if component.aria_role:
                return f'get_by_role("{component.aria_role}").filter(has_text="{component.semantic_purpose}")'
        
        # Try accessible name + role combination (context-based)
        if component.aria_label and component.aria_role:
            return f'get_by_role("{component.aria_role}", name="{component.aria_label}")'
        
        # Try label-based approach (context-based)
        if component.label:
            return f'get_by_label("{component.label}")'
        
        # Try placeholder + role combination (context-based)
        if component.placeholder and component.aria_role:
            return f'get_by_role("{component.aria_role}").filter(has_placeholder="{component.placeholder}")'
        
        # Try name + role combination (context-based)
        if component.name and component.aria_role:
            return f'get_by_role("{component.aria_role}").filter(has_name="{component.name}")'
        
        # If text-based healing is necessary, use with additional context
        if component.text_content:
            # Use text with role or parent context, not blind .first
            if component.aria_role:
                return f'get_by_role("{component.aria_role}").filter(has_text="{component.text_content}")'
            elif component.label:
                return f'get_by_label("{component.label}").filter(has_text="{component.text_content}")'
            else:
                # Last resort: use text but warn about potential ambiguity
                logger.warning(
                    f"Using text-based locator without context for {component.semantic_purpose}. "
                    "This may be ambiguous - consider adding role or parent context."
                )
                return f'get_by_text("{component.text_content}")'
        
        return None
    
    def get_next_locator(
        self,
        chain: LocatorChain,
        failed_locator: str,
    ) -> Optional[Tuple[str, LocatorStrategy, float]]:
        """Get the next locator in the fallback chain.
        
        Args:
            chain: Locator chain to use
            failed_locator: Locator that failed
            
        Returns:
            Tuple of (locator, strategy, confidence) or None if exhausted
        """
        # If primary failed, try first fallback
        if failed_locator == chain.primary_locator and chain.fallbacks:
            fallback = chain.fallbacks[0]
            return fallback.locator, fallback.strategy, fallback.confidence
        
        # If a fallback failed, try the next one
        for i, fallback in enumerate(chain.fallbacks):
            if fallback.locator == failed_locator and i + 1 < len(chain.fallbacks):
                next_fallback = chain.fallbacks[i + 1]
                return next_fallback.locator, next_fallback.strategy, next_fallback.confidence
        
        # Try repository locator
        if chain.repository_locator and failed_locator != chain.repository_locator:
            return (
                chain.repository_locator,
                LocatorStrategy.TEST_ID,  # Repository locators are typically high quality
                chain.repository_confidence,
            )
        
        # Try healing candidate
        if chain.healing_candidate and failed_locator != chain.healing_candidate:
            return (
                chain.healing_candidate,
                LocatorStrategy.XPATH,  # Healing candidates are often XPath
                0.5,
            )
        
        # Chain exhausted
        logger.warning(f"Locator chain exhausted for action {chain.action_id}")
        return None
    
    def update_chain_from_execution(
        self,
        chain: LocatorChain,
        successful_locator: str,
    ) -> LocatorChain:
        """Update chain based on successful execution.
        
        This enables runtime learning - successful locators get promoted.
        """
        # If successful locator is not primary, consider promoting it
        if successful_locator != chain.primary_locator:
            # Find the successful fallback
            for fallback in chain.fallbacks:
                if fallback.locator == successful_locator:
                    # Boost confidence
                    fallback.confidence = min(fallback.confidence + 0.1, 1.0)
                    fallback.evidence.append("Successful in execution")
                    break
            
            # Update repository if available
            if self.locator_repository:
                # This would need more context (project, page, element name)
                # in a real implementation
                pass
        
        return chain
    
    def get_locator_statistics(self) -> Dict[str, Any]:
        """Get statistics about locator strategy usage."""
        return {
            "strategy_priority": [s.value for s in self.strategy_priority],
            "strategy_confidence": {
                s.value: c for s, c in self.strategy_confidence.items()
            },
        }
