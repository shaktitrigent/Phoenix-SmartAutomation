"""Semantic Page Classifier - Generic Page Type Classification.

This module provides generic page type classification that works for ANY web application.
It analyzes DOM structure, URL patterns, content, and components to classify pages
without any application-specific knowledge.

Page classification is based on semantic patterns, not product names.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from phoenix.semantic.models import (
    SemanticPage,
    PageType,
    ComponentType,
    BusinessIntentType,
    NavigationContext,
    BusinessIntent,
)

logger = logging.getLogger(__name__)


class PagePattern:
    """Represents a pattern for page type classification."""
    
    def __init__(
        self,
        page_type: PageType,
        url_patterns: List[str],
        title_patterns: List[str],
        heading_patterns: List[str],
        component_signatures: List[str],
        required_components: List[ComponentType],
        forbidden_components: List[ComponentType],
        text_indicators: List[str],
    ):
        self.page_type = page_type
        self.url_patterns = url_patterns
        self.title_patterns = title_patterns
        self.heading_patterns = heading_patterns
        self.component_signatures = component_signatures
        self.required_components = required_components
        self.forbidden_components = forbidden_components
        self.text_indicators = text_indicators


class SemanticPageClassifier:
    """Generic page type classifier using semantic patterns.
    
    This classifier analyzes pages without any application-specific knowledge,
    making it work for ANY web application.
    """
    
    def __init__(self):
        """Initialize the classifier with generic page patterns."""
        self.patterns = self._initialize_patterns()
        logger.info(f"[SEMANTIC PAGE CLASSIFIER] Initialized with {len(self.patterns)} page type patterns")
    
    def _initialize_patterns(self) -> List[PagePattern]:
        """Initialize generic page type patterns."""
        patterns = []
        
        # Authentication Screen Pattern
        patterns.append(PagePattern(
            page_type=PageType.AUTHENTICATION_SCREEN,
            url_patterns=[r".*login.*", r".*signin.*", r".*auth.*", r".*logout.*", r".*signup.*", r".*register.*"],
            title_patterns=[r".*login.*", r".*sign.?in.*", r".*authentication.*", r".*log.?on.*"],
            heading_patterns=[r".*login.*", r".*sign.?in.*", r".*authentication.*", r".*log.?on.*"],
            component_signatures=["password", "username", "email", "credential"],
            required_components=[ComponentType.TEXT_FIELD, ComponentType.BUTTON],
            forbidden_components=[],
            text_indicators=["login", "sign in", "username", "password", "email", "forgot password"],
        ))
        
        # Dashboard Pattern
        patterns.append(PagePattern(
            page_type=PageType.DASHBOARD,
            url_patterns=[r".*dashboard.*", r".*home.*", r".*overview.*", r".*summary.*"],
            title_patterns=[r".*dashboard.*", r".*home.*", r".*overview.*", r".*summary.*"],
            heading_patterns=[r".*dashboard.*", r".*overview.*", r".*summary.*"],
            component_signatures=["chart", "widget", "metric", "stat", "card"],
            required_components=[ComponentType.CARD],
            forbidden_components=[],
            text_indicators=["dashboard", "overview", "summary", "statistics", "metrics", "analytics"],
        ))
        
        # CRUD Form Pattern
        patterns.append(PagePattern(
            page_type=PageType.CRUD_FORM,
            url_patterns=[r".*create.*", r".*edit.*", r".*update.*", r".*add.*", r".*new.*"],
            title_patterns=[r".*create.*", r".*edit.*", r".*update.*", r".*add.*", r".*new.*"],
            heading_patterns=[r".*create.*", r".*edit.*", r".*update.*", r".*add.*", r".*new.*"],
            component_signatures=["form", "input", "submit", "save", "cancel"],
            required_components=[ComponentType.TEXT_FIELD, ComponentType.BUTTON],
            forbidden_components=[],
            text_indicators=["create", "edit", "update", "add", "new", "save", "cancel", "submit"],
        ))
        
        # Search Screen Pattern
        patterns.append(PagePattern(
            page_type=PageType.SEARCH_SCREEN,
            url_patterns=[r".*search.*", r".*find.*", r".*query.*"],
            title_patterns=[r".*search.*", r".*find.*", r".*query.*"],
            heading_patterns=[r".*search.*", r".*find.*", r".*query.*"],
            component_signatures=["search", "filter", "query"],
            required_components=[ComponentType.TEXT_FIELD],
            forbidden_components=[],
            text_indicators=["search", "find", "query", "filter", "results"],
        ))
        
        # Table View Pattern
        patterns.append(PagePattern(
            page_type=PageType.TABLE_VIEW,
            url_patterns=[r".*list.*", r".*view.*", r".*browse.*", r".*index.*"],
            title_patterns=[r".*list.*", r".*view.*", r".*browse.*", r".*index.*"],
            heading_patterns=[r".*list.*", r".*view.*", r".*browse.*"],
            component_signatures=["table", "grid", "row", "column"],
            required_components=[ComponentType.TABLE],
            forbidden_components=[],
            text_indicators=["list", "view", "browse", "table", "grid"],
        ))
        
        # Report Screen Pattern
        patterns.append(PagePattern(
            page_type=PageType.REPORT_SCREEN,
            url_patterns=[r".*report.*", r".*analytics.*", r".*chart.*", r".*graph.*"],
            title_patterns=[r".*report.*", r".*analytics.*", r".*chart.*", r".*graph.*"],
            heading_patterns=[r".*report.*", r".*analytics.*", r".*chart.*"],
            component_signatures=["chart", "graph", "report", "export"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["report", "analytics", "chart", "graph", "export", "print"],
        ))
        
        # Wizard Pattern
        patterns.append(PagePattern(
            page_type=PageType.WIZARD,
            url_patterns=[r".*wizard.*", r".*step.*", r".*setup.*", r".*onboard.*"],
            title_patterns=[r".*wizard.*", r".*step.*", r".*setup.*", r".*onboard.*"],
            heading_patterns=[r".*wizard.*", r".*step.*", r".*setup.*"],
            component_signatures=["step", "wizard", "next", "previous", "progress"],
            required_components=[ComponentType.STEPPER, ComponentType.BUTTON],
            forbidden_components=[],
            text_indicators=["wizard", "step", "next", "previous", "finish", "setup"],
        ))
        
        # File Upload Pattern
        patterns.append(PagePattern(
            page_type=PageType.FILE_UPLOAD,
            url_patterns=[r".*upload.*", r".*import.*", r".*attach.*"],
            title_patterns=[r".*upload.*", r".*import.*", r".*attach.*"],
            heading_patterns=[r".*upload.*", r".*import.*", r".*attach.*"],
            component_signatures=["file", "upload", "import", "attach"],
            required_components=[ComponentType.FILE_UPLOAD],
            forbidden_components=[],
            text_indicators=["upload", "import", "attach", "file", "browse"],
        ))
        
        # Calendar Pattern
        patterns.append(PagePattern(
            page_type=PageType.CALENDAR,
            url_patterns=[r".*calendar.*", r".*schedule.*", r".*event.*"],
            title_patterns=[r".*calendar.*", r".*schedule.*", r".*event.*"],
            heading_patterns=[r".*calendar.*", r".*schedule.*", r".*event.*"],
            component_signatures=["calendar", "date", "schedule", "event"],
            required_components=[ComponentType.CALENDAR],
            forbidden_components=[],
            text_indicators=["calendar", "schedule", "event", "date", "month", "year"],
        ))
        
        # Settings Pattern
        patterns.append(PagePattern(
            page_type=PageType.SETTINGS,
            url_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            title_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            heading_patterns=[r".*setting.*", r".*config.*", r".*preference.*"],
            component_signatures=["setting", "config", "preference", "option"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["setting", "config", "preference", "option", "preference"],
        ))
        
        # Profile Pattern
        patterns.append(PagePattern(
            page_type=PageType.PROFILE,
            url_patterns=[r".*profile.*", r".*account.*", r".*user.*"],
            title_patterns=[r".*profile.*", r".*account.*", r".*user.*"],
            heading_patterns=[r".*profile.*", r".*account.*", r".*user.*"],
            component_signatures=["profile", "account", "user", "avatar"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["profile", "account", "user", "avatar", "personal"],
        ))
        
        # Workflow Screen Pattern
        patterns.append(PagePattern(
            page_type=PageType.WORKFLOW_SCREEN,
            url_patterns=[r".*workflow.*", r".*process.*", r".*approval.*"],
            title_patterns=[r".*workflow.*", r".*process.*", r".*approval.*"],
            heading_patterns=[r".*workflow.*", r".*process.*", r".*approval.*"],
            component_signatures=["workflow", "process", "approval", "status"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["workflow", "process", "approval", "status", "transition"],
        ))
        
        # Analytics Pattern
        patterns.append(PagePattern(
            page_type=PageType.ANALYTICS,
            url_patterns=[r".*analytics.*", r".*insight.*", r".*metric.*"],
            title_patterns=[r".*analytics.*", r".*insight.*", r".*metric.*"],
            heading_patterns=[r".*analytics.*", r".*insight.*", r".*metric.*"],
            component_signatures=["analytics", "insight", "metric", "chart", "graph"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["analytics", "insight", "metric", "chart", "graph", "trend"],
        ))
        
        # Landing Page Pattern
        patterns.append(PagePattern(
            page_type=PageType.LANDING_PAGE,
            url_patterns=[r"^/$", r".*home.*", r".*landing.*"],
            title_patterns=[r".*home.*", r".*welcome.*", r".*landing.*"],
            heading_patterns=[r".*welcome.*", r".*landing.*"],
            component_signatures=["hero", "landing", "cta", "banner"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["welcome", "landing", "get started", "learn more", "sign up"],
        ))
        
        # Error Page Pattern
        patterns.append(PagePattern(
            page_type=PageType.ERROR_PAGE,
            url_patterns=[r".*error.*", r".*404.*", r".*500.*"],
            title_patterns=[r".*error.*", r".*not found.*", r".*server error.*"],
            heading_patterns=[r".*error.*", r".*not found.*", r".*server error.*"],
            component_signatures=["error", "404", "500", "not found"],
            required_components=[],
            forbidden_components=[],
            text_indicators=["error", "not found", "server error", "404", "500", "oops"],
        ))
        
        return patterns
    
    def classify(
        self,
        url: str,
        title: str,
        heading: str,
        dom_content: str,
        components: List[Any],
        text_content: str
    ) -> Tuple[PageType, float, List[str]]:
        """Classify a page using semantic patterns.
        
        Args:
            url: Page URL
            title: Page title
            heading: Main heading
            dom_content: DOM content
            components: List of components
            text_content: Page text content
            
        Returns:
            Tuple of (page_type, confidence, evidence)
        """
        logger.info(f"[SEMANTIC PAGE CLASSIFIER] Classifying page: {url}")
        
        scores = {}
        evidence = {}
        
        for pattern in self.patterns:
            score, pattern_evidence = self._score_pattern(
                pattern, url, title, heading, dom_content, components, text_content
            )
            scores[pattern.page_type] = score
            evidence[pattern.page_type] = pattern_evidence
        
        # Find highest scoring pattern
        best_page_type = PageType.UNKNOWN
        best_score = 0.0
        best_evidence = []
        
        for page_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_page_type = page_type
                best_evidence = evidence[page_type]
        
        # Normalize confidence
        confidence = min(best_score, 1.0)
        
        logger.info(f"[SEMANTIC PAGE CLASSIFIER] Classified as: {best_page_type.value} (confidence: {confidence:.2f})")
        logger.info(f"[SEMANTIC PAGE CLASSIFIER] Evidence: {best_evidence}")
        
        return best_page_type, confidence, best_evidence
    
    def _score_pattern(
        self,
        pattern: PagePattern,
        url: str,
        title: str,
        heading: str,
        dom_content: str,
        components: List[Any],
        text_content: str
    ) -> Tuple[float, List[str]]:
        """Score a pattern against page features.
        
        Returns:
            Tuple of (score, evidence)
        """
        score = 0.0
        evidence = []
        
        # URL pattern matching (weight: 0.25)
        url_score = self._match_patterns(pattern.url_patterns, url.lower())
        if url_score > 0:
            score += url_score * 0.25
            evidence.append(f"URL pattern match: {url_score:.2f}")
        
        # Title pattern matching (weight: 0.20)
        title_score = self._match_patterns(pattern.title_patterns, title.lower())
        if title_score > 0:
            score += title_score * 0.20
            evidence.append(f"Title pattern match: {title_score:.2f}")
        
        # Heading pattern matching (weight: 0.20)
        heading_score = self._match_patterns(pattern.heading_patterns, heading.lower())
        if heading_score > 0:
            score += heading_score * 0.20
            evidence.append(f"Heading pattern match: {heading_score:.2f}")
        
        # Component signature matching (weight: 0.15)
        component_score = self._match_component_signatures(
            pattern.component_signatures, dom_content.lower()
        )
        if component_score > 0:
            score += component_score * 0.15
            evidence.append(f"Component signature match: {component_score:.2f}")
        
        # Required components check (weight: 0.10)
        required_score = self._check_required_components(
            pattern.required_components, components
        )
        if required_score > 0:
            score += required_score * 0.10
            evidence.append(f"Required components: {required_score:.2f}")
        
        # Text indicator matching (weight: 0.10)
        text_score = self._match_text_indicators(
            pattern.text_indicators, text_content.lower()
        )
        if text_score > 0:
            score += text_score * 0.10
            evidence.append(f"Text indicator match: {text_score:.2f}")
        
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
    
    def _match_component_signatures(self, signatures: List[str], dom_content: str) -> float:
        """Match component signatures in DOM content."""
        if not signatures:
            return 0.0
        
        matches = 0
        for signature in signatures:
            if signature.lower() in dom_content:
                matches += 1
        
        return matches / len(signatures) if signatures else 0.0
    
    def _check_required_components(
        self,
        required_components: List[ComponentType],
        components: List[Any]
    ) -> float:
        """Check if required components are present."""
        if not required_components:
            return 0.0
        
        # Extract component types from components
        available_types = set()
        for component in components:
            if hasattr(component, 'component_type'):
                available_types.add(component.component_type)
        
        matches = 0
        for required_type in required_components:
            if required_type in available_types:
                matches += 1
        
        return matches / len(required_components) if required_components else 0.0
    
    def _match_text_indicators(self, indicators: List[str], text_content: str) -> float:
        """Match text indicators in page content."""
        if not indicators:
            return 0.0
        
        matches = 0
        for indicator in indicators:
            if indicator.lower() in text_content:
                matches += 1
        
        return matches / len(indicators) if indicators else 0.0
