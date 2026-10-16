"""Component Purpose Detector - Generic Component Purpose Inference (Priority 22).

This module infers the semantic purpose of components beyond basic type classification.
It analyzes context, relationships, and patterns to determine what a component is
designed to do in the business flow.

This is completely generic and works for ANY web application without product-specific rules.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    ComponentPurpose,
    PageType,
    BusinessIntentType,
)

logger = logging.getLogger(__name__)


class ComponentPurposeDetector:
    """Generic component purpose detector using semantic context.
    
    This detector infers component purpose from:
    - Component text and labels
    - Surrounding components
    - Page type context
    - Business intent context
    - DOM structure
    - ARIA attributes
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the purpose detector with generic purpose patterns."""
        self.purpose_patterns = self._initialize_purpose_patterns()
        logger.info(f"[COMPONENT PURPOSE DETECTOR] Initialized with {len(self.purpose_patterns)} purpose patterns")
    
    def _initialize_purpose_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize generic purpose patterns."""
        patterns = {}
        
        # Button purposes
        patterns["form_submit"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["submit", "save", "confirm", "continue", "done", "finish"],
            "context_requirements": ["form_fields_nearby"],
            "page_types": [PageType.CRUD_FORM, PageType.AUTHENTICATION_SCREEN],
            "intents": [BusinessIntentType.DATA_ENTRY, BusinessIntentType.AUTHENTICATION],
        }
        
        patterns["form_cancel"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["cancel", "close", "back", "discard"],
            "context_requirements": ["form_fields_nearby"],
            "page_types": [PageType.CRUD_FORM, PageType.MODAL],
            "intents": [BusinessIntentType.DATA_ENTRY],
        }
        
        patterns["search_trigger"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["search", "find", "query", "go"],
            "context_requirements": ["search_input_nearby"],
            "page_types": [PageType.SEARCH_SCREEN, PageType.TABLE_VIEW],
            "intents": [BusinessIntentType.SEARCH],
        }
        
        patterns["create_trigger"] = {
            "component_types": [ComponentType.BUTTON, ComponentType.LINK],
            "text_patterns": ["create", "add", "new", "+", "plus"],
            "context_requirements": [],
            "page_types": [PageType.TABLE_VIEW, PageType.DASHBOARD],
            "intents": [BusinessIntentType.DATA_ENTRY],
        }
        
        patterns["edit_trigger"] = {
            "component_types": [ComponentType.BUTTON, ComponentType.LINK],
            "text_patterns": ["edit", "modify", "change", "update"],
            "context_requirements": ["table_row_nearby", "card_nearby"],
            "page_types": [PageType.TABLE_VIEW],
            "intents": [BusinessIntentType.DATA_MODIFICATION],
        }
        
        patterns["delete_trigger"] = {
            "component_types": [ComponentType.BUTTON, ComponentType.LINK],
            "text_patterns": ["delete", "remove", "destroy", "trash"],
            "context_requirements": ["table_row_nearby", "card_nearby"],
            "page_types": [PageType.TABLE_VIEW],
            "intents": [BusinessIntentType.DATA_DELETION],
        }
        
        patterns["login_trigger"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["login", "sign in", "authenticate", "log on"],
            "context_requirements": ["username_field_nearby", "password_field_nearby"],
            "page_types": [PageType.AUTHENTICATION_SCREEN],
            "intents": [BusinessIntentType.AUTHENTICATION],
        }
        
        patterns["logout_trigger"] = {
            "component_types": [ComponentType.BUTTON, ComponentType.LINK],
            "text_patterns": ["logout", "sign out", "log off"],
            "context_requirements": [],
            "page_types": [PageType.DASHBOARD, PageType.SETTINGS],
            "intents": [BusinessIntentType.AUTHENTICATION],
        }
        
        patterns["navigation_trigger"] = {
            "component_types": [ComponentType.LINK, ComponentType.BUTTON],
            "text_patterns": ["next", "previous", "back", "continue", "forward"],
            "context_requirements": [],
            "page_types": [PageType.WIZARD, PageType.TABLE_VIEW],
            "intents": [BusinessIntentType.NAVIGATION],
        }
        
        patterns["approve_trigger"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["approve", "accept", "confirm", "authorize"],
            "context_requirements": [],
            "page_types": [PageType.APPROVAL_SCREEN],
            "intents": [BusinessIntentType.APPROVAL],
        }
        
        patterns["reject_trigger"] = {
            "component_types": [ComponentType.BUTTON],
            "text_patterns": ["reject", "deny", "decline"],
            "context_requirements": [],
            "page_types": [PageType.APPROVAL_SCREEN],
            "intents": [BusinessIntentType.APPROVAL],
        }
        
        # Text field purposes
        patterns["username_input"] = {
            "component_types": [ComponentType.TEXT_FIELD],
            "text_patterns": ["username", "user", "email", "login"],
            "context_requirements": [],
            "page_types": [PageType.AUTHENTICATION_SCREEN],
            "intents": [BusinessIntentType.AUTHENTICATION],
        }
        
        patterns["password_input"] = {
            "component_types": [ComponentType.TEXT_FIELD],
            "text_patterns": ["password", "pass", "pwd"],
            "context_requirements": [],
            "page_types": [PageType.AUTHENTICATION_SCREEN],
            "intents": [BusinessIntentType.AUTHENTICATION],
        }
        
        patterns["search_input"] = {
            "component_types": [ComponentType.TEXT_FIELD],
            "text_patterns": ["search", "find", "query", "filter"],
            "context_requirements": [],
            "page_types": [PageType.SEARCH_SCREEN, PageType.TABLE_VIEW],
            "intents": [BusinessIntentType.SEARCH, BusinessIntentType.FILTER],
        }
        
        patterns["data_entry_input"] = {
            "component_types": [ComponentType.TEXT_FIELD],
            "text_patterns": [],
            "context_requirements": ["form_context"],
            "page_types": [PageType.CRUD_FORM],
            "intents": [BusinessIntentType.DATA_ENTRY],
        }
        
        # Dropdown purposes
        patterns["selection_dropdown"] = {
            "component_types": [ComponentType.DROPDOWN],
            "text_patterns": [],
            "context_requirements": ["form_context"],
            "page_types": [PageType.CRUD_FORM],
            "intents": [BusinessIntentType.DATA_ENTRY],
        }
        
        patterns["filter_dropdown"] = {
            "component_types": [ComponentType.DROPDOWN],
            "text_patterns": ["filter", "sort", "group"],
            "context_requirements": [],
            "page_types": [PageType.TABLE_VIEW, PageType.SEARCH_SCREEN],
            "intents": [BusinessIntentType.FILTER, BusinessIntentType.SORT],
        }
        
        return patterns
    
    def infer_purpose(
        self,
        component: SemanticComponent,
        nearby_components: List[SemanticComponent] = None,
        page_type: PageType = PageType.UNKNOWN,
        business_intent: BusinessIntentType = BusinessIntentType.UNKNOWN,
    ) -> ComponentPurpose:
        """Infer the purpose of a component.
        
        Args:
            component: The component to analyze
            nearby_components: Nearby components for context
            page_type: Current page type
            business_intent: Current business intent
            
        Returns:
            Inferred component purpose with confidence
        """
        nearby_components = nearby_components or []
        
        # Extract component information
        component_text = f"{component.text_content} {component.label} {component.name} {component.placeholder}".lower()
        
        # Analyze context
        context_info = self._analyze_context(component, nearby_components, page_type)
        
        # Score each purpose pattern
        purpose_scores = []
        
        for purpose_name, pattern in self.purpose_patterns.items():
            if component.component_type not in pattern["component_types"]:
                continue
            
            score, evidence = self._score_pattern(
                purpose_name,
                pattern,
                component_text,
                context_info,
                page_type,
                business_intent,
            )
            
            if score > 0:
                purpose_scores.append((purpose_name, score, evidence))
        
        # Select best purpose
        if purpose_scores:
            purpose_scores.sort(key=lambda x: x[1], reverse=True)
            best_purpose, score, evidence = purpose_scores[0]
            
            return ComponentPurpose(
                purpose=best_purpose,
                confidence=min(score / 100.0, 1.0),
                evidence=evidence,
                page_type=page_type.value if page_type else "",
                nearby_components=[c.component_type.value for c in nearby_components[:5]],
                form_context=context_info.get("form_context", False),
                business_intent=business_intent.value if business_intent else "",
            )
        
        # Default purpose based on component type
        default_purpose = f"{component.component_type.value}_default"
        
        return ComponentPurpose(
            purpose=default_purpose,
            confidence=0.3,
            evidence=["Default purpose based on component type"],
            page_type=page_type.value if page_type else "",
            nearby_components=[c.component_type.value for c in nearby_components[:5]],
            form_context=context_info.get("form_context", False),
            business_intent=business_intent.value if business_intent else "",
        )
    
    def _analyze_context(
        self,
        component: SemanticComponent,
        nearby_components: List[SemanticComponent],
        page_type: PageType,
    ) -> Dict[str, Any]:
        """Analyze context around the component."""
        context = {
            "form_context": False,
            "form_fields_nearby": False,
            "search_input_nearby": False,
            "username_field_nearby": False,
            "password_field_nearby": False,
            "table_row_nearby": False,
            "card_nearby": False,
        }
        
        # Check for form context
        form_components = [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
        ]
        
        form_fields = [c for c in nearby_components if c.component_type in form_components]
        if form_fields:
            context["form_context"] = True
            context["form_fields_nearby"] = True
        
        # Check for specific nearby components
        for nearby in nearby_components:
            nearby_text = f"{nearby.text_content} {nearby.label} {nearby.name}".lower()
            
            if "search" in nearby_text or "find" in nearby_text:
                context["search_input_nearby"] = True
            
            if "username" in nearby_text or "email" in nearby_text or "user" in nearby_text:
                context["username_field_nearby"] = True
            
            if "password" in nearby_text or "pass" in nearby_text:
                context["password_field_nearby"] = True
            
            if nearby.component_type == ComponentType.TABLE:
                context["table_row_nearby"] = True
            
            if nearby.component_type == ComponentType.CARD:
                context["card_nearby"] = True
        
        return context
    
    def _score_pattern(
        self,
        purpose_name: str,
        pattern: Dict[str, Any],
        component_text: str,
        context_info: Dict[str, Any],
        page_type: PageType,
        business_intent: BusinessIntentType,
    ) -> Tuple[float, List[str]]:
        """Score a purpose pattern against the component."""
        score = 0
        evidence = []
        
        # Score text patterns
        for text_pattern in pattern.get("text_patterns", []):
            if text_pattern in component_text:
                score += 30
                evidence.append(f"Text pattern matched: '{text_pattern}'")
        
        # Score context requirements
        for requirement in pattern.get("context_requirements", []):
            if context_info.get(requirement, False):
                score += 20
                evidence.append(f"Context requirement met: {requirement}")
        
        # Score page type
        if page_type in pattern.get("page_types", []):
            score += 25
            evidence.append(f"Page type matches: {page_type.value}")
        
        # Score business intent
        if business_intent in pattern.get("intents", []):
            score += 25
            evidence.append(f"Business intent matches: {business_intent.value}")
        
        return score, evidence