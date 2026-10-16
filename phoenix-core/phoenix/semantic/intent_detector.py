"""Business Intent Detector - Generic Business Intent Classification.

This module provides generic business intent detection that works for ANY web application.
It analyzes page composition, component patterns, URL patterns, and content to determine
the business intent without any application-specific knowledge.

Business intent detection is based on semantic patterns, not product-specific workflows.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from phoenix.semantic.models import (
    BusinessIntent,
    BusinessIntentType,
    SemanticComponent,
    ComponentType,
    PageType,
)

logger = logging.getLogger(__name__)


class IntentPattern:
    """Represents a pattern for business intent classification."""
    
    def __init__(
        self,
        intent_type: BusinessIntentType,
        url_patterns: List[str],
        title_patterns: List[str],
        heading_patterns: List[str],
        component_signatures: List[str],
        action_button_patterns: List[str],
        text_indicators: List[str],
        required_component_types: List[ComponentType],
        forbidden_component_types: List[ComponentType],
    ):
        self.intent_type = intent_type
        self.url_patterns = url_patterns
        self.title_patterns = title_patterns
        self.heading_patterns = heading_patterns
        self.component_signatures = component_signatures
        self.action_button_patterns = action_button_patterns
        self.text_indicators = text_indicators
        self.required_component_types = required_component_types
        self.forbidden_component_types = forbidden_component_types


class BusinessIntentDetector:
    """Generic business intent detector using semantic patterns.
    
    This detector analyzes pages without any application-specific knowledge,
    making it work for ANY web application.
    """
    
    def __init__(self):
        """Initialize the detector with generic intent patterns."""
        self.patterns = self._initialize_patterns()
        logger.info(f"[BUSINESS INTENT DETECTOR] Initialized with {len(self.patterns)} intent type patterns")
    
    def _initialize_patterns(self) -> List[IntentPattern]:
        """Initialize generic business intent patterns."""
        patterns = []
        
        # Authentication Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.AUTHENTICATION,
            url_patterns=[r".*login.*", r".*signin.*", r".*auth.*", r".*logout.*", r".*signup.*"],
            title_patterns=[r".*login.*", r".*sign.?in.*", r".*authentication.*"],
            heading_patterns=[r".*login.*", r".*sign.?in.*", r".*authentication.*"],
            component_signatures=["password", "username", "credential", "login"],
            action_button_patterns=["login", "sign in", "submit", "authenticate"],
            text_indicators=["login", "sign in", "username", "password", "authenticate"],
            required_component_types=[ComponentType.TEXT_FIELD, ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Data Entry Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.DATA_ENTRY,
            url_patterns=[r".*create.*", r".*add.*", r".*new.*", r".*entry.*"],
            title_patterns=[r".*create.*", r".*add.*", r".*new.*", r".*entry.*"],
            heading_patterns=[r".*create.*", r".*add.*", r".*new.*"],
            component_signatures=["form", "input", "field", "save", "submit"],
            action_button_patterns=["save", "submit", "create", "add"],
            text_indicators=["create", "add", "new", "save", "submit", "enter"],
            required_component_types=[ComponentType.TEXT_FIELD, ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Data Retrieval Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.DATA_RETRIEVAL,
            url_patterns=[r".*view.*", r".*show.*", r".*display.*", r".*list.*"],
            title_patterns=[r".*view.*", r".*show.*", r".*display.*", r".*list.*"],
            heading_patterns=[r".*view.*", r".*show.*", r".*display.*"],
            component_signatures=["table", "list", "grid", "card", "detail"],
            action_button_patterns=["view", "show", "display", "details"],
            text_indicators=["view", "show", "display", "list", "details"],
            required_component_types=[ComponentType.TABLE, ComponentType.CARD],
            forbidden_component_types=[],
        ))
        
        # Data Modification Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.DATA_MODIFICATION,
            url_patterns=[r".*edit.*", r".*update.*", r".*modify.*", r".*change.*"],
            title_patterns=[r".*edit.*", r".*update.*", r".*modify.*", r".*change.*"],
            heading_patterns=[r".*edit.*", r".*update.*", r".*modify.*"],
            component_signatures=["form", "input", "edit", "update", "save"],
            action_button_patterns=["save", "update", "apply", "confirm"],
            text_indicators=["edit", "update", "modify", "change", "save"],
            required_component_types=[ComponentType.TEXT_FIELD, ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Data Deletion Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.DATA_DELETION,
            url_patterns=[r".*delete.*", r".*remove.*", r".*destroy.*"],
            title_patterns=[r".*delete.*", r".*remove.*", r".*destroy.*"],
            heading_patterns=[r".*delete.*", r".*remove.*"],
            component_signatures=["delete", "remove", "confirm"],
            action_button_patterns=["delete", "remove", "confirm", "yes"],
            text_indicators=["delete", "remove", "destroy", "confirm"],
            required_component_types=[ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Navigation Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.NAVIGATION,
            url_patterns=[r".*nav.*", r".*menu.*", r".*page.*"],
            title_patterns=[r".*navigation.*", r".*menu.*"],
            heading_patterns=[],
            component_signatures=["menu", "nav", "link", "breadcrumb"],
            action_button_patterns=["next", "previous", "back", "home"],
            text_indicators=["menu", "navigation", "next", "previous", "back"],
            required_component_types=[ComponentType.LINK, ComponentType.MENU],
            forbidden_component_types=[],
        ))
        
        # Reporting Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.REPORTING,
            url_patterns=[r".*report.*", r".*analytics.*", r".*chart.*", r".*graph.*"],
            title_patterns=[r".*report.*", r".*analytics.*", r".*chart.*"],
            heading_patterns=[r".*report.*", r".*analytics.*", r".*chart.*"],
            component_signatures=["chart", "graph", "report", "export", "print"],
            action_button_patterns=["export", "print", "generate", "download"],
            text_indicators=["report", "analytics", "chart", "graph", "export"],
            required_component_types=[],
            forbidden_component_types=[],
        ))
        
        # Approval Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.APPROVAL,
            url_patterns=[r".*approval.*", r".*review.*", r".*approve.*"],
            title_patterns=[r".*approval.*", r".*review.*", r".*approve.*"],
            heading_patterns=[r".*approval.*", r".*review.*"],
            component_signatures=["approve", "reject", "review", "workflow"],
            action_button_patterns=["approve", "reject", "confirm", "submit"],
            text_indicators=["approve", "reject", "review", "approval", "workflow"],
            required_component_types=[ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Configuration Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.CONFIGURATION,
            url_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            title_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            heading_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            component_signatures=["setting", "config", "option", "preference"],
            action_button_patterns=["save", "apply", "reset", "confirm"],
            text_indicators=["setting", "config", "preference", "option"],
            required_component_types=[ComponentType.TEXT_FIELD, ComponentType.DROPDOWN],
            forbidden_component_types=[],
        ))
        
        # File Management Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.FILE_MANAGEMENT,
            url_patterns=[r".*upload.*", r".*download.*", r".*file.*", r".*attachment.*"],
            title_patterns=[r".*upload.*", r".*download.*", r".*file.*"],
            heading_patterns=[r".*upload.*", r".*download.*", r".*file.*"],
            component_signatures=["file", "upload", "download", "attachment"],
            action_button_patterns=["upload", "download", "browse", "attach"],
            text_indicators=["upload", "download", "file", "attachment", "browse"],
            required_component_types=[ComponentType.FILE_UPLOAD],
            forbidden_component_types=[],
        ))
        
        # Search Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.SEARCH,
            url_patterns=[r".*search.*", r".*find.*", r".*query.*"],
            title_patterns=[r".*search.*", r".*find.*", r".*query.*"],
            heading_patterns=[r".*search.*", r".*find.*"],
            component_signatures=["search", "query", "find", "filter"],
            action_button_patterns=["search", "find", "submit", "go"],
            text_indicators=["search", "find", "query", "results"],
            required_component_types=[ComponentType.TEXT_FIELD],
            forbidden_component_types=[],
        ))
        
        # Filter Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.FILTER,
            url_patterns=[r".*filter.*", r".*refine.*"],
            title_patterns=[r".*filter.*", r".*refine.*"],
            heading_patterns=[r".*filter.*"],
            component_signatures=["filter", "refine", "narrow"],
            action_button_patterns=["filter", "apply", "reset"],
            text_indicators=["filter", "refine", "narrow", "apply"],
            required_component_types=[ComponentType.DROPDOWN, ComponentType.CHECKBOX],
            forbidden_component_types=[],
        ))
        
        # Sort Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.SORT,
            url_patterns=[r".*sort.*", r".*order.*"],
            title_patterns=[r".*sort.*", r".*order.*"],
            heading_patterns=[r".*sort.*"],
            component_signatures=["sort", "order", "arrange"],
            action_button_patterns=["sort", "order", "arrange"],
            text_indicators=["sort", "order", "ascending", "descending"],
            required_component_types=[ComponentType.DROPDOWN],
            forbidden_component_types=[],
        ))
        
        # Export Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.EXPORT,
            url_patterns=[r".*export.*", r".*download.*"],
            title_patterns=[r".*export.*", r".*download.*"],
            heading_patterns=[r".*export.*"],
            component_signatures=["export", "download", "save"],
            action_button_patterns=["export", "download", "save"],
            text_indicators=["export", "download", "save", "csv", "excel", "pdf"],
            required_component_types=[ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Import Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.IMPORT,
            url_patterns=[r".*import.*", r".*upload.*"],
            title_patterns=[r".*import.*", r".*upload.*"],
            heading_patterns=[r".*import.*"],
            component_signatures=["import", "upload", "load"],
            action_button_patterns=["import", "upload", "load"],
            text_indicators=["import", "upload", "load", "csv", "excel"],
            required_component_types=[ComponentType.FILE_UPLOAD],
            forbidden_component_types=[],
        ))
        
        # Workflow Transition Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.WORKFLOW_TRANSITION,
            url_patterns=[r".*workflow.*", r".*transition.*", r".*process.*"],
            title_patterns=[r".*workflow.*", r".*transition.*", r".*process.*"],
            heading_patterns=[r".*workflow.*", r".*transition.*"],
            component_signatures=["workflow", "transition", "process", "status"],
            action_button_patterns=["submit", "approve", "reject", "transition"],
            text_indicators=["workflow", "transition", "process", "status", "submit"],
            required_component_types=[ComponentType.BUTTON],
            forbidden_component_types=[],
        ))
        
        # Notification Intent
        patterns.append(IntentPattern(
            intent_type=BusinessIntentType.NOTIFICATION,
            url_patterns=[r".*notification.*", r".*alert.*", r".*message.*"],
            title_patterns=[r".*notification.*", r".*alert.*", r".*message.*"],
            heading_patterns=[r".*notification.*", r".*alert.*"],
            component_signatures=["notification", "alert", "message", "toast"],
            action_button_patterns=["dismiss", "close", "mark read"],
            text_indicators=["notification", "alert", "message", "toast"],
            required_component_types=[ComponentType.TOAST, ComponentType.ALERT],
            forbidden_component_types=[],
        ))
        
        return patterns
    
    def detect_intent(
        self,
        url: str,
        title: str,
        heading: str,
        components: List[SemanticComponent],
        text_content: str,
        page_type: PageType
    ) -> BusinessIntent:
        """Detect business intent using semantic patterns.
        
        Args:
            url: Page URL
            title: Page title
            heading: Main heading
            components: List of semantic components
            text_content: Page text content
            page_type: Semantic page type
            
        Returns:
            BusinessIntent with classification
        """
        logger.info(f"[BUSINESS INTENT DETECTOR] Detecting intent for: {url}")
        
        scores = {}
        evidence = {}
        
        for pattern in self.patterns:
            score, pattern_evidence = self._score_pattern(
                pattern, url, title, heading, components, text_content, page_type
            )
            scores[pattern.intent_type] = score
            evidence[pattern.intent_type] = pattern_evidence
        
        # Find highest scoring pattern
        best_intent_type = BusinessIntentType.UNKNOWN
        best_score = 0.0
        best_evidence = []
        
        for intent_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_intent_type = intent_type
                best_evidence = evidence[intent_type]
        
        # Normalize confidence
        confidence = min(best_score, 1.0)
        
        # Determine data operation capabilities
        data_capabilities = self._determine_data_capabilities(
            best_intent_type, components, text_content
        )
        
        # Determine available actions
        available_actions = self._determine_available_actions(components)
        
        # Determine primary action
        primary_action = self._determine_primary_action(components, best_intent_type)
        
        # Determine secondary intents
        secondary_intents = self._determine_secondary_intents(scores, best_intent_type)
        
        # Create business intent
        intent = BusinessIntent(
            primary_intent=best_intent_type,
            secondary_intents=secondary_intents,
            evidence=best_evidence,
            available_actions=available_actions,
            primary_action=primary_action,
            confidence=confidence,
            **data_capabilities
        )
        
        logger.info(f"[BUSINESS INTENT DETECTOR] Detected intent: {best_intent_type.value} (confidence: {confidence:.2f})")
        logger.info(f"[BUSINESS INTENT DETECTOR] Evidence: {best_evidence}")
        
        return intent
    
    def _score_pattern(
        self,
        pattern: IntentPattern,
        url: str,
        title: str,
        heading: str,
        components: List[SemanticComponent],
        text_content: str,
        page_type: PageType
    ) -> Tuple[float, List[str]]:
        """Score an intent pattern against page features.
        
        Returns:
            Tuple of (score, evidence)
        """
        score = 0.0
        evidence = []
        
        # URL pattern matching (weight: 0.20)
        url_score = self._match_patterns(pattern.url_patterns, url.lower())
        if url_score > 0:
            score += url_score * 0.20
            evidence.append(f"URL pattern match: {url_score:.2f}")
        
        # Title pattern matching (weight: 0.15)
        title_score = self._match_patterns(pattern.title_patterns, title.lower())
        if title_score > 0:
            score += title_score * 0.15
            evidence.append(f"Title pattern match: {title_score:.2f}")
        
        # Heading pattern matching (weight: 0.15)
        heading_score = self._match_patterns(pattern.heading_patterns, heading.lower())
        if heading_score > 0:
            score += heading_score * 0.15
            evidence.append(f"Heading pattern match: {heading_score:.2f}")
        
        # Component signature matching (weight: 0.15)
        component_score = self._match_component_signatures(
            pattern.component_signatures, components, text_content.lower()
        )
        if component_score > 0:
            score += component_score * 0.15
            evidence.append(f"Component signature match: {component_score:.2f}")
        
        # Action button pattern matching (weight: 0.15)
        action_score = self._match_action_button_patterns(
            pattern.action_button_patterns, components
        )
        if action_score > 0:
            score += action_score * 0.15
            evidence.append(f"Action button pattern match: {action_score:.2f}")
        
        # Text indicator matching (weight: 0.10)
        text_score = self._match_text_indicators(
            pattern.text_indicators, text_content.lower()
        )
        if text_score > 0:
            score += text_score * 0.10
            evidence.append(f"Text indicator match: {text_score:.2f}")
        
        # Required components check (weight: 0.10)
        required_score = self._check_required_components(
            pattern.required_component_types, components
        )
        if required_score > 0:
            score += required_score * 0.10
            evidence.append(f"Required components: {required_score:.2f}")
        
        return score, evidence
    
    def _match_patterns(self, patterns: List[str], text: str) -> float:
        """Match regex patterns against text."""
        if not patterns:
            return 0.0
        
        matches = 0
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    matches += 1
            except re.error:
                continue
        
        return matches / len(patterns) if patterns else 0.0
    
    def _match_component_signatures(
        self,
        signatures: List[str],
        components: List[SemanticComponent],
        text_content: str
    ) -> float:
        """Match component signatures in components and text."""
        if not signatures:
            return 0.0
        
        matches = 0
        for signature in signatures:
            # Check in text content
            if signature.lower() in text_content:
                matches += 1
                continue
            
            # Check in component attributes
            for component in components:
                if (signature.lower() in component.text_content.lower() or
                    signature.lower() in component.element_class or
                    signature.lower() in component.element_id):
                    matches += 1
                    break
        
        return matches / len(signatures) if signatures else 0.0
    
    def _match_action_button_patterns(
        self,
        patterns: List[str],
        components: List[SemanticComponent]
    ) -> float:
        """Match action button patterns in components."""
        if not patterns:
            return 0.0
        
        # Find button components
        buttons = [c for c in components if c.component_type == ComponentType.BUTTON]
        
        matches = 0
        for pattern in patterns:
            for button in buttons:
                if pattern.lower() in button.text_content.lower():
                    matches += 1
                    break
        
        return matches / len(patterns) if patterns else 0.0
    
    def _match_text_indicators(self, indicators: List[str], text_content: str) -> float:
        """Match text indicators in page content."""
        if not indicators:
            return 0.0
        
        matches = 0
        for indicator in indicators:
            if indicator.lower() in text_content:
                matches += 1
        
        return matches / len(indicators) if indicators else 0.0
    
    def _check_required_components(
        self,
        required_types: List[ComponentType],
        components: List[SemanticComponent]
    ) -> float:
        """Check if required component types are present."""
        if not required_types:
            return 0.0
        
        available_types = {c.component_type for c in components}
        
        matches = 0
        for required_type in required_types:
            if required_type in available_types:
                matches += 1
        
        return matches / len(required_types) if required_types else 0.0
    
    def _determine_data_capabilities(
        self,
        intent_type: BusinessIntentType,
        components: List[SemanticComponent],
        text_content: str
    ) -> Dict[str, bool]:
        """Determine data operation capabilities."""
        capabilities = {
            "can_create": False,
            "can_read": False,
            "can_update": False,
            "can_delete": False,
            "can_search": False,
            "can_filter": False,
            "can_sort": False,
            "can_export": False,
        }
        
        # Based on intent type
        if intent_type == BusinessIntentType.DATA_ENTRY:
            capabilities["can_create"] = True
        elif intent_type == BusinessIntentType.DATA_RETRIEVAL:
            capabilities["can_read"] = True
        elif intent_type == BusinessIntentType.DATA_MODIFICATION:
            capabilities["can_update"] = True
        elif intent_type == BusinessIntentType.DATA_DELETION:
            capabilities["can_delete"] = True
        elif intent_type == BusinessIntentType.SEARCH:
            capabilities["can_search"] = True
        elif intent_type == BusinessIntentType.FILTER:
            capabilities["can_filter"] = True
        elif intent_type == BusinessIntentType.SORT:
            capabilities["can_sort"] = True
        elif intent_type == BusinessIntentType.EXPORT:
            capabilities["can_export"] = True
        
        # Based on components
        for component in components:
            if component.component_type == ComponentType.TEXT_FIELD:
                if "search" in component.text_content.lower() or "search" in component.element_id:
                    capabilities["can_search"] = True
            elif component.component_type == ComponentType.BUTTON:
                if "create" in component.text_content.lower() or "add" in component.text_content.lower():
                    capabilities["can_create"] = True
                elif "delete" in component.text_content.lower() or "remove" in component.text_content.lower():
                    capabilities["can_delete"] = True
                elif "edit" in component.text_content.lower() or "update" in component.text_content.lower():
                    capabilities["can_update"] = True
                elif "export" in component.text_content.lower():
                    capabilities["can_export"] = True
        
        return capabilities
    
    def _determine_available_actions(self, components: List[SemanticComponent]) -> List[str]:
        """Determine available actions from components."""
        actions = []
        
        for component in components:
            if component.component_type == ComponentType.BUTTON:
                if component.text_content:
                    actions.append(component.text_content.strip())
            elif component.component_type == ComponentType.LINK:
                if component.text_content:
                    actions.append(component.text_content.strip())
        
        return actions
    
    def _determine_primary_action(
        self,
        components: List[SemanticComponent],
        intent_type: BusinessIntentType
    ) -> str:
        """Determine primary action based on intent and components."""
        # Find submit/save buttons
        for component in components:
            if component.component_type == ComponentType.BUTTON:
                text = component.text_content.lower()
                if any(action in text for action in ["submit", "save", "confirm", "login", "sign in"]):
                    return component.text_content.strip()
        
        return ""
    
    def _determine_secondary_intents(
        self,
        scores: Dict[BusinessIntentType, float],
        primary_intent: BusinessIntentType
    ) -> List[BusinessIntentType]:
        """Determine secondary intents based on scores."""
        # Sort by score
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 3 excluding primary
        secondary = []
        for intent_type, score in sorted_intents:
            if intent_type != primary_intent and score > 0.3:
                secondary.append(intent_type)
                if len(secondary) >= 2:
                    break
        
        return secondary
