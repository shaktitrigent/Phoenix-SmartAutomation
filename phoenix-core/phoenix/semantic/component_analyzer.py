"""UI Component Analyzer - Generic UI Component Classification.

This module provides generic UI component classification that works for ANY web application.
It analyzes DOM elements, attributes, ARIA roles, and visual patterns to classify components
without any application-specific knowledge.

Component classification is based on semantic patterns, not product-specific selectors.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
)

logger = logging.getLogger(__name__)


@dataclass
class ComponentPattern:
    """Represents a pattern for component type classification."""
    
    component_type: ComponentType
    tag_patterns: List[str]
    attribute_patterns: Dict[str, List[str]]
    class_patterns: List[str]
    id_patterns: List[str]
    aria_role_patterns: List[str]
    text_patterns: List[str]
    position_patterns: List[str]
    structure_patterns: List[str]


class UIComponentAnalyzer:
    """Generic UI component analyzer using semantic patterns.
    
    This analyzer classifies UI components without any application-specific knowledge,
    making it work for ANY web application.
    """
    
    def __init__(self):
        """Initialize the analyzer with generic component patterns."""
        self.patterns = self._initialize_patterns()
        logger.info(f"[UI COMPONENT ANALYZER] Initialized with {len(self.patterns)} component type patterns")
    
    def _initialize_patterns(self) -> List[ComponentPattern]:
        """Initialize generic component type patterns."""
        patterns = []
        
        # Text Field Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.TEXT_FIELD,
            tag_patterns=["input", "textarea"],
            attribute_patterns={
                "type": ["text", "email", "tel", "url", "search"],
                "role": ["textbox", "searchbox"],
            },
            class_patterns=["input", "textfield", "text-field", "form-control"],
            id_patterns=["username", "email", "phone", "address", "name"],
            aria_role_patterns=["textbox", "searchbox"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["label"],
        ))
        
        # Dropdown Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.DROPDOWN,
            tag_patterns=["select", "option"],
            attribute_patterns={
                "type": ["select-one", "select-multiple"],
                "role": ["combobox", "listbox"],
            },
            class_patterns=["select", "dropdown", "combo-box", "form-control"],
            id_patterns=["select", "dropdown", "combo"],
            aria_role_patterns=["combobox", "listbox"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["option"],
        ))
        
        # Checkbox Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.CHECKBOX,
            tag_patterns=["input"],
            attribute_patterns={
                "type": ["checkbox"],
                "role": ["checkbox"],
            },
            class_patterns=["checkbox", "check-box"],
            id_patterns=["check", "checkbox"],
            aria_role_patterns=["checkbox"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["label"],
        ))
        
        # Radio Button Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.RADIO_BUTTON,
            tag_patterns=["input"],
            attribute_patterns={
                "type": ["radio"],
                "role": ["radio"],
            },
            class_patterns=["radio", "radio-button"],
            id_patterns=["radio", "option"],
            aria_role_patterns=["radio"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["label"],
        ))
        
        # Button Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.BUTTON,
            tag_patterns=["button", "input"],
            attribute_patterns={
                "type": ["button", "submit", "reset"],
                "role": ["button"],
            },
            class_patterns=["btn", "button", "action", "submit"],
            id_patterns=["submit", "cancel", "save", "delete", "button"],
            aria_role_patterns=["button"],
            text_patterns=["submit", "save", "cancel", "delete", "ok", "yes", "no"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Link Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.LINK,
            tag_patterns=["a"],
            attribute_patterns={
                "href": [".*"],
                "role": ["link"],
            },
            class_patterns=["link", "anchor", "hyperlink"],
            id_patterns=["link", "anchor"],
            aria_role_patterns=["link"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Table Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.TABLE,
            tag_patterns=["table"],
            attribute_patterns={
                "role": ["table", "grid"],
            },
            class_patterns=["table", "grid", "data-table"],
            id_patterns=["table", "grid"],
            aria_role_patterns=["table", "grid"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["thead", "tbody", "tr", "td"],
        ))
        
        # Card Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.CARD,
            tag_patterns=["div", "section", "article"],
            attribute_patterns={
                "role": ["article", "region"],
            },
            class_patterns=["card", "panel", "box", "container"],
            id_patterns=["card", "panel", "box"],
            aria_role_patterns=["article", "region"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Modal Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.MODAL,
            tag_patterns=["div", "dialog"],
            attribute_patterns={
                "role": ["dialog", "alertdialog"],
                "aria-modal": ["true"],
            },
            class_patterns=["modal", "dialog", "popup", "overlay"],
            id_patterns=["modal", "dialog", "popup"],
            aria_role_patterns=["dialog", "alertdialog"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Wizard Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.WIZARD,
            tag_patterns=["div", "section"],
            attribute_patterns={
                "role": ["wizard", "stepper"],
            },
            class_patterns=["wizard", "stepper", "step", "wizard-step"],
            id_patterns=["wizard", "stepper", "step"],
            aria_role_patterns=["wizard", "stepper"],
            text_patterns=["step", "next", "previous", "finish"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Calendar Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.CALENDAR,
            tag_patterns=["input", "div"],
            attribute_patterns={
                "type": ["date", "datetime", "datetime-local"],
                "role": ["calendar", "datebox"],
            },
            class_patterns=["calendar", "date-picker", "datepicker"],
            id_patterns=["calendar", "date", "datepicker"],
            aria_role_patterns=["calendar", "datebox"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # File Upload Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.FILE_UPLOAD,
            tag_patterns=["input"],
            attribute_patterns={
                "type": ["file"],
                "role": ["button"],
            },
            class_patterns=["file-upload", "upload", "file-input"],
            id_patterns=["file", "upload", "attachment"],
            aria_role_patterns=["button"],
            text_patterns=["upload", "browse", "choose file"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Tree Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.TREE,
            tag_patterns=["ul", "ol", "div"],
            attribute_patterns={
                "role": ["tree", "treegrid"],
            },
            class_patterns=["tree", "tree-view", "treeview"],
            id_patterns=["tree", "treeview"],
            aria_role_patterns=["tree", "treegrid"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["li"],
        ))
        
        # Grid Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.GRID,
            tag_patterns=["div", "section"],
            attribute_patterns={
                "role": ["grid"],
            },
            class_patterns=["grid", "grid-layout", "datagrid"],
            id_patterns=["grid"],
            aria_role_patterns=["grid"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Menu Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.MENU,
            tag_patterns=["nav", "ul", "ol", "div"],
            attribute_patterns={
                "role": ["menu", "menubar", "navigation"],
            },
            class_patterns=["menu", "nav", "navigation", "navbar"],
            id_patterns=["menu", "nav", "navigation"],
            aria_role_patterns=["menu", "menubar", "navigation"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["li"],
        ))
        
        # Toast Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.TOAST,
            tag_patterns=["div"],
            attribute_patterns={
                "role": ["alert", "status", "log"],
            },
            class_patterns=["toast", "notification", "alert", "message"],
            id_patterns=["toast", "notification", "alert"],
            aria_role_patterns=["alert", "status", "log"],
            text_patterns=["success", "error", "warning", "info"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Alert Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.ALERT,
            tag_patterns=["div"],
            attribute_patterns={
                "role": ["alert", "alertdialog"],
            },
            class_patterns=["alert", "warning", "error", "danger"],
            id_patterns=["alert", "warning", "error"],
            aria_role_patterns=["alert", "alertdialog"],
            text_patterns=["alert", "warning", "error", "danger"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Tab Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.TAB,
            tag_patterns=["div", "button", "li"],
            attribute_patterns={
                "role": ["tab", "tablist", "tabpanel"],
            },
            class_patterns=["tab", "tablist", "tabpanel"],
            id_patterns=["tab"],
            aria_role_patterns=["tab", "tablist", "tabpanel"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Accordion Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.ACCORDION,
            tag_patterns=["div", "section"],
            attribute_patterns={
                "role": ["accordion"],
            },
            class_patterns=["accordion", "collapse", "expand"],
            id_patterns=["accordion"],
            aria_role_patterns=["accordion"],
            text_patterns=["expand", "collapse"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Progress Bar Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.PROGRESS_BAR,
            tag_patterns=["progress", "div"],
            attribute_patterns={
                "role": ["progressbar"],
            },
            class_patterns=["progress", "progress-bar", "loading"],
            id_patterns=["progress"],
            aria_role_patterns=["progressbar"],
            text_patterns=["progress", "loading", "percent"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Stepper Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.STEPPER,
            tag_patterns=["div", "ol"],
            attribute_patterns={
                "role": ["stepper", "steps"],
            },
            class_patterns=["stepper", "steps", "step-indicator"],
            id_patterns=["stepper", "steps"],
            aria_role_patterns=["stepper", "steps"],
            text_patterns=["step", "of"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Breadcrumb Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.BREADCRUMB,
            tag_patterns=["nav", "ol", "ul"],
            attribute_patterns={
                "role": ["navigation", "breadcrumb"],
            },
            class_patterns=["breadcrumb", "breadcrumbs", "breadcrumb-nav"],
            id_patterns=["breadcrumb"],
            aria_role_patterns=["navigation", "breadcrumb"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=["li"],
        ))
        
        # Pagination Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.PAGINATION,
            tag_patterns=["nav", "div"],
            attribute_patterns={
                "role": ["navigation"],
            },
            class_patterns=["pagination", "pager", "page-nav"],
            id_patterns=["pagination", "pager"],
            aria_role_patterns=["navigation"],
            text_patterns=["next", "previous", "page", "of"],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Sidebar Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.SIDEBAR,
            tag_patterns=["aside", "div", "nav"],
            attribute_patterns={
                "role": ["complementary", "navigation"],
            },
            class_patterns=["sidebar", "side-nav", "aside"],
            id_patterns=["sidebar", "aside"],
            aria_role_patterns=["complementary", "navigation"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Header Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.HEADER,
            tag_patterns=["header", "div"],
            attribute_patterns={
                "role": ["banner"],
            },
            class_patterns=["header", "page-header", "top-bar"],
            id_patterns=["header"],
            aria_role_patterns=["banner"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        # Footer Pattern
        patterns.append(ComponentPattern(
            component_type=ComponentType.FOOTER,
            tag_patterns=["footer", "div"],
            attribute_patterns={
                "role": ["contentinfo"],
            },
            class_patterns=["footer", "page-footer"],
            id_patterns=["footer"],
            aria_role_patterns=["contentinfo"],
            text_patterns=[],
            position_patterns=[],
            structure_patterns=[],
        ))
        
        return patterns
    
    def analyze_element(
        self,
        element: Dict[str, Any],
        dom_context: str = ""
    ) -> SemanticComponent:
        """Analyze a DOM element and classify it as a semantic component.
        
        Args:
            element: DOM element dictionary with tag, attributes, text, etc.
            dom_context: Surrounding DOM context for analysis
            
        Returns:
            SemanticComponent with classification
        """
        tag = element.get("tag", "").lower()
        attributes = element.get("attributes", {})
        class_list = attributes.get("class", "").lower()
        id_value = attributes.get("id", "").lower()
        text_content = element.get("text", "").lower()
        aria_role = attributes.get("role", "").lower()
        aria_label = attributes.get("aria-label", "").lower()
        
        # Classify component type
        component_type, confidence = self._classify_component(
            tag, attributes, class_list, id_value, aria_role, text_content, dom_context
        )
        
        # Determine interactivity
        is_interactive = self._is_interactive_element(tag, attributes, component_type)
        
        # Determine if required
        is_required = self._is_required_element(attributes, text_content)
        
        # Determine if disabled
        is_disabled = self._is_disabled_element(attributes)
        
        # Extract label
        label = self._extract_label(element, dom_context)
        
        # Extract placeholder
        placeholder = attributes.get("placeholder", "")
        
        # Extract name
        name = attributes.get("name", "")
        
        # Create semantic component
        component = SemanticComponent(
            component_type=component_type,
            element_id=id_value,
            element_class=class_list,
            xpath=element.get("xpath", ""),
            css_selector=element.get("css_selector", ""),
            text_content=text_content,
            label=label,
            placeholder=placeholder,
            name=name,
            aria_role=aria_role,
            aria_label=aria_label,
            confidence=confidence,
            is_interactive=is_interactive,
            is_required=is_required,
            is_disabled=is_disabled,
            is_visible=element.get("visible", True),
            position=element.get("position", {}),
            layout_info=element.get("layout", {}),
            attributes=attributes,
            detection_method="semantic_pattern_matching",
        )
        
        logger.debug(f"[UI COMPONENT ANALYZER] Classified as: {component_type.value} (confidence: {confidence:.2f})")
        
        return component
    
    def _classify_component(
        self,
        tag: str,
        attributes: Dict[str, str],
        class_list: str,
        id_value: str,
        aria_role: str,
        text_content: str,
        dom_context: str
    ) -> Tuple[ComponentType, float]:
        """Classify component type using semantic patterns."""
        scores = {}
        
        for pattern in self.patterns:
            score = self._score_component_pattern(
                pattern, tag, attributes, class_list, id_value, aria_role, text_content, dom_context
            )
            scores[pattern.component_type] = score
        
        # Find highest scoring pattern
        best_component_type = ComponentType.UNKNOWN
        best_score = 0.0
        
        for component_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_component_type = component_type
        
        # Normalize confidence
        confidence = min(best_score, 1.0)
        
        return best_component_type, confidence
    
    def _score_component_pattern(
        self,
        pattern: ComponentPattern,
        tag: str,
        attributes: Dict[str, str],
        class_list: str,
        id_value: str,
        aria_role: str,
        text_content: str,
        dom_context: str
    ) -> float:
        """Score a component pattern against element features."""
        score = 0.0
        
        # Tag pattern matching (weight: 0.30)
        if tag in pattern.tag_patterns:
            score += 0.30
        
        # Attribute pattern matching (weight: 0.25)
        attr_score = self._match_attribute_patterns(pattern.attribute_patterns, attributes)
        score += attr_score * 0.25
        
        # Class pattern matching (weight: 0.15)
        class_score = self._match_string_patterns(pattern.class_patterns, class_list)
        score += class_score * 0.15
        
        # ID pattern matching (weight: 0.10)
        id_score = self._match_string_patterns(pattern.id_patterns, id_value)
        score += id_score * 0.10
        
        # ARIA role matching (weight: 0.10)
        if aria_role and aria_role in pattern.aria_role_patterns:
            score += 0.10
        
        # Text pattern matching (weight: 0.10)
        text_score = self._match_string_patterns(pattern.text_patterns, text_content)
        score += text_score * 0.10
        
        return score
    
    def _match_attribute_patterns(
        self,
        attribute_patterns: Dict[str, List[str]],
        attributes: Dict[str, str]
    ) -> float:
        """Match attribute patterns."""
        if not attribute_patterns:
            return 0.0
        
        matches = 0
        total = 0
        
        for attr_name, patterns in attribute_patterns.items():
            attr_value = attributes.get(attr_name, "").lower()
            total += 1
            for pattern in patterns:
                if re.search(pattern, attr_value, re.IGNORECASE):
                    matches += 1
                    break
        
        return matches / total if total > 0 else 0.0
    
    def _match_string_patterns(self, patterns: List[str], text: str) -> float:
        """Match string patterns against text."""
        if not patterns:
            return 0.0
        
        matches = 0
        for pattern in patterns:
            if pattern.lower() in text:
                matches += 1
        
        return matches / len(patterns) if patterns else 0.0
    
    def _is_interactive_element(
        self,
        tag: str,
        attributes: Dict[str, str],
        component_type: ComponentType
    ) -> bool:
        """Determine if element is interactive."""
        interactive_tags = {"button", "input", "select", "textarea", "a"}
        interactive_roles = {"button", "link", "checkbox", "radio", "combobox", "textbox"}
        
        if tag in interactive_tags:
            return True
        
        if attributes.get("role", "").lower() in interactive_roles:
            return True
        
        if attributes.get("onclick") or attributes.get("onchange"):
            return True
        
        # Check component type
        interactive_components = {
            ComponentType.BUTTON,
            ComponentType.LINK,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.TEXT_FIELD,
            ComponentType.FILE_UPLOAD,
            ComponentType.MENU,
            ComponentType.TAB,
        }
        
        return component_type in interactive_components
    
    def _is_required_element(self, attributes: Dict[str, str], text_content: str) -> bool:
        """Determine if element is required."""
        if attributes.get("required"):
            return True
        
        if attributes.get("aria-required") == "true":
            return True
        
        if "required" in text_content.lower():
            return True
        
        return False
    
    def _is_disabled_element(self, attributes: Dict[str, str]) -> bool:
        """Determine if element is disabled."""
        if attributes.get("disabled"):
            return True
        
        if attributes.get("aria-disabled") == "true":
            return True
        
        return False
    
    def _extract_label(self, element: Dict[str, Any], dom_context: str) -> str:
        """Extract label for element from DOM context."""
        # Try aria-label first
        aria_label = element.get("attributes", {}).get("aria-label", "")
        if aria_label:
            return aria_label
        
        # Try associated label in context
        label_match = re.search(r'<label[^>]*>([^<]+)</label>', dom_context)
        if label_match:
            return label_match.group(1).strip()
        
        # Try placeholder
        placeholder = element.get("attributes", {}).get("placeholder", "")
        if placeholder:
            return placeholder
        
        return ""
    
    def analyze_dom(
        self,
        dom_elements: List[Dict[str, Any]],
        dom_content: str = ""
    ) -> List[SemanticComponent]:
        """Analyze all DOM elements and classify them.
        
        Args:
            dom_elements: List of DOM element dictionaries
            dom_content: Full DOM content for context
            
        Returns:
            List of SemanticComponent objects
        """
        components = []
        
        for element in dom_elements:
            try:
                component = self.analyze_element(element, dom_content)
                components.append(component)
            except Exception as e:
                logger.warning(f"[UI COMPONENT ANALYZER] Failed to analyze element: {e}")
        
        logger.info(f"[UI COMPONENT ANALYZER] Analyzed {len(components)} components")
        
        return components
