"""Navigation Structure Analyzer - Generic Navigation Analysis.

This module provides generic navigation structure analysis that works for ANY web application.
It analyzes navigation menus, breadcrumbs, tabs, sidebars, and other navigation elements
without any application-specific knowledge.

Navigation analysis is based on semantic patterns, not product-specific navigation structures.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from phoenix.semantic.models import (
    NavigationContext,
    SemanticComponent,
    ComponentType,
)

logger = logging.getLogger(__name__)


class NavigationPattern:
    """Represents a pattern for navigation element detection."""
    
    def __init__(
        self,
        navigation_type: str,
        tag_patterns: List[str],
        class_patterns: List[str],
        id_patterns: List[str],
        aria_role_patterns: List[str],
        structure_patterns: List[str],
        text_indicators: List[str],
    ):
        self.navigation_type = navigation_type
        self.tag_patterns = tag_patterns
        self.class_patterns = class_patterns
        self.id_patterns = id_patterns
        self.aria_role_patterns = aria_role_patterns
        self.structure_patterns = structure_patterns
        self.text_indicators = text_indicators


class NavigationStructureAnalyzer:
    """Generic navigation structure analyzer using semantic patterns.
    
    This analyzer analyzes navigation without any application-specific knowledge,
    making it work for ANY web application.
    """
    
    def __init__(self):
        """Initialize the analyzer with generic navigation patterns."""
        self.patterns = self._initialize_patterns()
        logger.info(f"[NAVIGATION ANALYZER] Initialized with {len(self.patterns)} navigation patterns")
    
    def _initialize_patterns(self) -> List[NavigationPattern]:
        """Initialize generic navigation patterns."""
        patterns = []
        
        # Navigation Menu Pattern
        patterns.append(NavigationPattern(
            navigation_type="menu",
            tag_patterns=["nav", "ul", "ol", "div"],
            class_patterns=["menu", "nav", "navigation", "navbar", "sidebar"],
            id_patterns=["menu", "nav", "navigation", "navbar"],
            aria_role_patterns=["navigation", "menu", "menubar"],
            structure_patterns=["li", "a"],
            text_indicators=["menu", "navigation", "home", "dashboard"],
        ))
        
        # Breadcrumb Pattern
        patterns.append(NavigationPattern(
            navigation_type="breadcrumb",
            tag_patterns=["nav", "ol", "ul", "div"],
            class_patterns=["breadcrumb", "breadcrumbs", "breadcrumb-nav", "trail"],
            id_patterns=["breadcrumb", "breadcrumbs"],
            aria_role_patterns=["navigation", "breadcrumb"],
            structure_patterns=["li"],
            text_indicators=["breadcrumb", "trail", "you are here"],
        ))
        
        # Tab Pattern
        patterns.append(NavigationPattern(
            navigation_type="tab",
            tag_patterns=["div", "button", "li"],
            class_patterns=["tab", "tablist", "tabpanel", "tabs"],
            id_patterns=["tab", "tabs"],
            aria_role_patterns=["tab", "tablist", "tabpanel"],
            structure_patterns=[],
            text_indicators=["tab"],
        ))
        
        # Sidebar Pattern
        patterns.append(NavigationPattern(
            navigation_type="sidebar",
            tag_patterns=["aside", "div", "nav"],
            class_patterns=["sidebar", "side-nav", "aside", "side-menu"],
            id_patterns=["sidebar", "aside"],
            aria_role_patterns=["complementary", "navigation"],
            structure_patterns=[],
            text_indicators=["sidebar", "menu"],
        ))
        
        # Header Pattern
        patterns.append(NavigationPattern(
            navigation_type="header",
            tag_patterns=["header", "div"],
            class_patterns=["header", "page-header", "top-bar", "site-header"],
            id_patterns=["header"],
            aria_role_patterns=["banner"],
            structure_patterns=[],
            text_indicators=["header", "logo", "brand"],
        ))
        
        # Footer Pattern
        patterns.append(NavigationPattern(
            navigation_type="footer",
            tag_patterns=["footer", "div"],
            class_patterns=["footer", "page-footer", "site-footer"],
            id_patterns=["footer"],
            aria_role_patterns=["contentinfo"],
            structure_patterns=[],
            text_indicators=["footer", "copyright"],
        ))
        
        # Pagination Pattern
        patterns.append(NavigationPattern(
            navigation_type="pagination",
            tag_patterns=["nav", "div"],
            class_patterns=["pagination", "pager", "page-nav", "paging"],
            id_patterns=["pagination", "pager"],
            aria_role_patterns=["navigation"],
            structure_patterns=[],
            text_indicators=["next", "previous", "page", "of"],
        ))
        
        # Stepper Pattern
        patterns.append(NavigationPattern(
            navigation_type="stepper",
            tag_patterns=["div", "ol"],
            class_patterns=["stepper", "steps", "step-indicator", "progress-steps"],
            id_patterns=["stepper", "steps"],
            aria_role_patterns=["stepper", "steps"],
            structure_patterns=["li"],
            text_indicators=["step", "of"],
        ))
        
        return patterns
    
    def analyze_navigation(
        self,
        components: List[SemanticComponent],
        dom_content: str,
        url: str
    ) -> NavigationContext:
        """Analyze navigation structure from components and DOM.
        
        Args:
            components: List of semantic components
            dom_content: Full DOM content
            url: Current page URL
            
        Returns:
            NavigationContext with navigation analysis
        """
        logger.info(f"[NAVIGATION ANALYZER] Analyzing navigation for: {url}")
        
        context = NavigationContext()
        
        # Detect navigation elements
        context.has_navigation_menu = self._detect_navigation_menu(components, dom_content)
        context.has_breadcrumbs = self._detect_breadcrumbs(components, dom_content)
        context.has_tabs = self._detect_tabs(components, dom_content)
        context.has_sidebar = self._detect_sidebar(components, dom_content)
        context.has_header = self._detect_header(components, dom_content)
        context.has_footer = self._detect_footer(components, dom_content)
        
        # Determine navigation type
        context.navigation_type = self._determine_navigation_type(context)
        
        # Extract navigation links
        context.navigation_links = self._extract_navigation_links(components)
        
        # Extract breadcrumb trail
        context.breadcrumb_trail = self._extract_breadcrumb_trail(components, dom_content)
        
        # Extract active menu item
        context.active_menu_item = self._extract_active_menu_item(components, url)
        
        # Build menu hierarchy
        context.menu_hierarchy = self._build_menu_hierarchy(components, dom_content)
        
        # Determine navigation availability
        context.back_available = self._check_back_navigation(components, dom_content)
        context.forward_available = self._check_forward_navigation(components, dom_content)
        
        # Calculate confidence
        context.confidence = self._calculate_navigation_confidence(context)
        
        logger.info(f"[NAVIGATION ANALYZER] Navigation type: {context.navigation_type}")
        logger.info(f"[NAVIGATION ANALYZER] Confidence: {context.confidence:.2f}")
        
        return context
    
    def _detect_navigation_menu(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has navigation menu."""
        # Check for navigation components
        menu_components = [
            c for c in components
            if c.component_type == ComponentType.MENU or
            "menu" in c.element_class or
            "nav" in c.element_class or
            c.aria_role in ["navigation", "menu", "menubar"]
        ]
        
        if menu_components:
            return True
        
        # Check DOM for navigation patterns
        nav_patterns = [
            r'<nav[^>]*>',
            r'class="[^"]*menu[^"]*"',
            r'class="[^"]*nav[^"]*"',
            r'role="navigation"',
        ]
        
        for pattern in nav_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_breadcrumbs(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has breadcrumbs."""
        # Check for breadcrumb components
        breadcrumb_components = [
            c for c in components
            if "breadcrumb" in c.element_class or
            "breadcrumb" in c.element_id or
            c.aria_role == "breadcrumb"
        ]
        
        if breadcrumb_components:
            return True
        
        # Check DOM for breadcrumb patterns
        breadcrumb_patterns = [
            r'class="[^"]*breadcrumb[^"]*"',
            r'aria-label="breadcrumb"',
            r'role="breadcrumb"',
        ]
        
        for pattern in breadcrumb_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_tabs(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has tabs."""
        # Check for tab components
        tab_components = [
            c for c in components
            if c.component_type == ComponentType.TAB or
            "tab" in c.element_class or
            c.aria_role in ["tab", "tablist", "tabpanel"]
        ]
        
        if tab_components:
            return True
        
        # Check DOM for tab patterns
        tab_patterns = [
            r'class="[^"]*tab[^"]*"',
            r'role="tab"',
            r'role="tablist"',
        ]
        
        for pattern in tab_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_sidebar(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has sidebar."""
        # Check for sidebar components
        sidebar_components = [
            c for c in components
            if c.component_type == ComponentType.SIDEBAR or
            "sidebar" in c.element_class or
            "aside" in c.element_class or
            c.aria_role == "complementary"
        ]
        
        if sidebar_components:
            return True
        
        # Check DOM for sidebar patterns
        sidebar_patterns = [
            r'<aside[^>]*>',
            r'class="[^"]*sidebar[^"]*"',
            r'class="[^"]*aside[^"]*"',
            r'role="complementary"',
        ]
        
        for pattern in sidebar_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_header(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has header."""
        # Check for header components
        header_components = [
            c for c in components
            if c.component_type == ComponentType.HEADER or
            "header" in c.element_class or
            c.aria_role == "banner"
        ]
        
        if header_components:
            return True
        
        # Check DOM for header patterns
        header_patterns = [
            r'<header[^>]*>',
            r'class="[^"]*header[^"]*"',
            r'role="banner"',
        ]
        
        for pattern in header_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_footer(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Detect if page has footer."""
        # Check for footer components
        footer_components = [
            c for c in components
            if c.component_type == ComponentType.FOOTER or
            "footer" in c.element_class or
            c.aria_role == "contentinfo"
        ]
        
        if footer_components:
            return True
        
        # Check DOM for footer patterns
        footer_patterns = [
            r'<footer[^>]*>',
            r'class="[^"]*footer[^"]*"',
            r'role="contentinfo"',
        ]
        
        for pattern in footer_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _determine_navigation_type(self, context: NavigationContext) -> str:
        """Determine the primary navigation type."""
        if context.has_sidebar:
            return "sidebar"
        elif context.has_navigation_menu:
            return "top_menu"
        elif context.has_tabs:
            return "tabs"
        elif context.has_breadcrumbs:
            return "breadcrumbs"
        else:
            return "minimal"
    
    def _extract_navigation_links(
        self,
        components: List[SemanticComponent]
    ) -> List[Dict[str, str]]:
        """Extract navigation links from components."""
        links = []
        
        for component in components:
            if component.component_type == ComponentType.LINK:
                link_info = {
                    "text": component.text_content,
                    "href": component.attributes.get("href", ""),
                    "element_id": component.element_id,
                    "element_class": component.element_class,
                }
                links.append(link_info)
        
        return links
    
    def _extract_breadcrumb_trail(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> List[str]:
        """Extract breadcrumb trail from components and DOM."""
        trail = []
        
        # Try to extract from breadcrumb components
        breadcrumb_components = [
            c for c in components
            if "breadcrumb" in c.element_class or
            "breadcrumb" in c.element_id
        ]
        
        if breadcrumb_components:
            # Extract text from breadcrumb area
            for component in breadcrumb_components:
                if component.text_content:
                    # Split by common separators
                    separators = [">", "/", "|", "-", "»"]
                    for sep in separators:
                        if sep in component.text_content:
                            trail.extend([t.strip() for t in component.text_content.split(sep)])
                            break
        
        # If no trail found, try DOM parsing
        if not trail:
            breadcrumb_match = re.search(
                r'<nav[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>(.*?)</nav>',
                dom_content,
                re.IGNORECASE | re.DOTALL
            )
            if breadcrumb_match:
                breadcrumb_html = breadcrumb_match.group(1)
                # Extract text from links
                link_matches = re.findall(r'<a[^>]*>([^<]+)</a>', breadcrumb_html)
                trail.extend(link_matches)
        
        return trail
    
    def _extract_active_menu_item(
        self,
        components: List[SemanticComponent],
        url: str
    ) -> str:
        """Extract the active menu item based on URL."""
        for component in components:
            if component.component_type == ComponentType.LINK:
                href = component.attributes.get("href", "")
                if href and href in url:
                    return component.text_content.strip()
            
            # Check for active class
            if "active" in component.element_class:
                return component.text_content.strip()
        
        return ""
    
    def _build_menu_hierarchy(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> Dict[str, Any]:
        """Build menu hierarchy from navigation components."""
        hierarchy = {
            "root": [],
            "items": [],
        }
        
        # Find menu components
        menu_components = [
            c for c in components
            if c.component_type == ComponentType.MENU or
            "menu" in c.element_class or
            "nav" in c.element_class
        ]
        
        for component in menu_components:
            menu_item = {
                "text": component.text_content,
                "id": component.element_id,
                "class": component.element_class,
                "href": component.attributes.get("href", ""),
                "children": [],
            }
            hierarchy["items"].append(menu_item)
        
        return hierarchy
    
    def _check_back_navigation(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Check if back navigation is available."""
        # Check for back buttons
        back_components = [
            c for c in components
            if c.component_type == ComponentType.BUTTON and
            ("back" in c.text_content.lower() or
             "previous" in c.text_content.lower() or
             "←" in c.text_content)
        ]
        
        if back_components:
            return True
        
        # Check DOM for back patterns
        back_patterns = [
            r'back',
            r'previous',
            r'←',
            r'history\.back\(\)',
        ]
        
        for pattern in back_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _check_forward_navigation(
        self,
        components: List[SemanticComponent],
        dom_content: str
    ) -> bool:
        """Check if forward navigation is available."""
        # Check for forward buttons
        forward_components = [
            c for c in components
            if c.component_type == ComponentType.BUTTON and
            ("forward" in c.text_content.lower() or
             "next" in c.text_content.lower() or
             "→" in c.text_content)
        ]
        
        if forward_components:
            return True
        
        # Check DOM for forward patterns
        forward_patterns = [
            r'forward',
            r'next',
            r'→',
            r'history\.forward\(\)',
        ]
        
        for pattern in forward_patterns:
            if re.search(pattern, dom_content, re.IGNORECASE):
                return True
        
        return False
    
    def _calculate_navigation_confidence(self, context: NavigationContext) -> float:
        """Calculate overall navigation analysis confidence."""
        confidence = 0.0
        
        # Count detected navigation elements
        detected_elements = sum([
            context.has_navigation_menu,
            context.has_breadcrumbs,
            context.has_tabs,
            context.has_sidebar,
            context.has_header,
            context.has_footer,
        ])
        
        # Base confidence on detection count
        if detected_elements > 0:
            confidence = min(detected_elements / 3.0, 1.0)  # Max confidence at 3+ elements
        
        # Boost if navigation links found
        if context.navigation_links:
            confidence = min(confidence + 0.2, 1.0)
        
        # Boost if breadcrumb trail found
        if context.breadcrumb_trail:
            confidence = min(confidence + 0.1, 1.0)
        
        return confidence
