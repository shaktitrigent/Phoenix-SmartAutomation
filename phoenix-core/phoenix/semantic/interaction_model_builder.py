"""Interaction Model Builder - Generic Component Interaction Intelligence (Priority 22).

This module builds detailed interaction models for components, defining
how each component type can be interacted with and what to expect.

This is completely generic and works for ANY web application without product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from phoenix.semantic.models import (
    ComponentType,
    InteractionModel,
)

logger = logging.getLogger(__name__)


class InteractionModelBuilder:
    """Generic interaction model builder for UI components.
    
    This builder creates interaction models that define:
    - Supported actions for each component type
    - Parameters for each action
    - Expected outcomes
    - Potential side effects
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the interaction model builder."""
        self.interaction_templates = self._initialize_interaction_templates()
        logger.info(f"[INTERACTION MODEL BUILDER] Initialized with {len(self.interaction_templates)} component templates")
    
    def _initialize_interaction_templates(self) -> Dict[ComponentType, Dict[str, Any]]:
        """Initialize generic interaction templates for each component type."""
        templates = {}
        
        # Text Field
        templates[ComponentType.TEXT_FIELD] = {
            "supported_actions": ["fill", "clear", "type", "validate", "focus", "blur"],
            "action_parameters": {
                "fill": {"value": "required", "clear_first": "optional"},
                "clear": {},
                "type": {"text": "required", "delay": "optional"},
                "validate": {},
                "focus": {},
                "blur": {},
            },
            "expected_outcomes": ["value_entered", "field_updated", "validation_triggered"],
            "side_effects": ["form_validation", "ui_update", "error_message"],
            "interaction_confidence": 0.9,
        }
        
        # Password Field (inherits from text field with additional considerations)
        templates[ComponentType.TEXT_FIELD] = templates[ComponentType.TEXT_FIELD]  # Will add password-specific handling
        
        # Dropdown
        templates[ComponentType.DROPDOWN] = {
            "supported_actions": ["select", "open", "close", "get_options"],
            "action_parameters": {
                "select": {"value": "required", "index": "optional", "text": "optional"},
                "open": {},
                "close": {},
                "get_options": {},
            },
            "expected_outcomes": ["option_selected", "dropdown_closed", "value_updated"],
            "side_effects": ["form_validation", "dependent_field_update", "ui_update"],
            "interaction_confidence": 0.85,
        }
        
        # Checkbox
        templates[ComponentType.CHECKBOX] = {
            "supported_actions": ["check", "uncheck", "toggle", "verify_checked"],
            "action_parameters": {
                "check": {},
                "uncheck": {},
                "toggle": {},
                "verify_checked": {},
            },
            "expected_outcomes": ["state_changed", "checked", "unchecked"],
            "side_effects": ["form_validation", "dependent_field_visibility", "ui_update"],
            "interaction_confidence": 0.95,
        }
        
        # Radio Button
        templates[ComponentType.RADIO_BUTTON] = {
            "supported_actions": ["select", "verify_selected"],
            "action_parameters": {
                "select": {},
                "verify_selected": {},
            },
            "expected_outcomes": ["radio_selected", "other_radios_deselected", "value_updated"],
            "side_effects": ["form_validation", "dependent_field_update", "ui_update"],
            "interaction_confidence": 0.95,
        }
        
        # Button
        templates[ComponentType.BUTTON] = {
            "supported_actions": ["click", "double_click", "right_click", "hover", "verify_enabled"],
            "action_parameters": {
                "click": {},
                "double_click": {},
                "right_click": {},
                "hover": {},
                "verify_enabled": {},
            },
            "expected_outcomes": ["action_triggered", "page_transition", "modal_opened", "form_submitted"],
            "side_effects": ["navigation", "data_submission", "modal_open", "toast_displayed", "state_change"],
            "interaction_confidence": 0.95,
        }
        
        # Link
        templates[ComponentType.LINK] = {
            "supported_actions": ["click", "hover", "verify_url", "navigate"],
            "action_parameters": {
                "click": {},
                "hover": {},
                "verify_url": {},
                "navigate": {},
            },
            "expected_outcomes": ["navigation", "page_transition", "download_started"],
            "side_effects": ["navigation", "new_tab_opened", "download_started"],
            "interaction_confidence": 0.9,
        }
        
        # Table
        templates[ComponentType.TABLE] = {
            "supported_actions": ["select_row", "get_row_count", "get_cell_text", "sort", "filter", "paginate"],
            "action_parameters": {
                "select_row": {"row_index": "required", "by_text": "optional"},
                "get_row_count": {},
                "get_cell_text": {"row": "required", "column": "required"},
                "sort": {"column": "required", "direction": "optional"},
                "filter": {"column": "required", "value": "required"},
                "paginate": {"direction": "required", "page": "optional"},
            },
            "expected_outcomes": ["row_selected", "data_retrieved", "table_sorted", "table_filtered", "page_changed"],
            "side_effects": ["row_highlighted", "details_panel_opened", "form_populated", "navigation"],
            "interaction_confidence": 0.8,
        }
        
        # Card
        templates[ComponentType.CARD] = {
            "supported_actions": ["click", "expand", "collapse", "get_content"],
            "action_parameters": {
                "click": {},
                "expand": {},
                "collapse": {},
                "get_content": {},
            },
            "expected_outcomes": ["card_selected", "card_expanded", "details_shown"],
            "side_effects": ["navigation", "modal_opened", "details_panel_opened"],
            "interaction_confidence": 0.75,
        }
        
        # Modal
        templates[ComponentType.MODAL] = {
            "supported_actions": ["open", "close", "submit", "cancel", "verify_visible"],
            "action_parameters": {
                "open": {"trigger": "optional"},
                "close": {},
                "submit": {},
                "cancel": {},
                "verify_visible": {},
            },
            "expected_outcomes": ["modal_opened", "modal_closed", "form_submitted", "action_cancelled"],
            "side_effects": ["overlay_displayed", "background_disabled", "form_reset", "page_refresh"],
            "interaction_confidence": 0.85,
        }
        
        # Calendar
        templates[ComponentType.CALENDAR] = {
            "supported_actions": ["select_date", "open", "close", "navigate_month", "navigate_year"],
            "action_parameters": {
                "select_date": {"date": "required"},
                "open": {},
                "close": {},
                "navigate_month": {"direction": "required"},
                "navigate_year": {"year": "required"},
            },
            "expected_outcomes": ["date_selected", "calendar_closed", "value_updated"],
            "side_effects": ["form_validation", "dependent_field_update", "ui_update"],
            "interaction_confidence": 0.8,
        }
        
        # File Upload
        templates[ComponentType.FILE_UPLOAD] = {
            "supported_actions": ["upload", "select_file", "verify_uploaded", "remove_file"],
            "action_parameters": {
                "upload": {"file_path": "required"},
                "select_file": {"file_path": "required"},
                "verify_uploaded": {},
                "remove_file": {},
            },
            "expected_outcomes": ["file_selected", "upload_started", "upload_completed", "file_displayed"],
            "side_effects": ["progress_bar_shown", "success_message", "error_message", "preview_displayed"],
            "interaction_confidence": 0.75,
        }
        
        # Tree
        templates[ComponentType.TREE] = {
            "supported_actions": ["expand_node", "collapse_node", "select_node", "get_selected"],
            "action_parameters": {
                "expand_node": {"node_path": "required"},
                "collapse_node": {"node_path": "required"},
                "select_node": {"node_path": "required"},
                "get_selected": {},
            },
            "expected_outcomes": ["node_expanded", "node_collapsed", "node_selected", "children_loaded"],
            "side_effects": ["lazy_load", "ui_update", "form_population"],
            "interaction_confidence": 0.7,
        }
        
        # Menu
        templates[ComponentType.MENU] = {
            "supported_actions": ["open", "close", "select_item", "navigate"],
            "action_parameters": {
                "open": {},
                "close": {},
                "select_item": {"item_path": "required"},
                "navigate": {"direction": "required"},
            },
            "expected_outcomes": ["menu_opened", "menu_closed", "item_selected", "submenu_opened"],
            "side_effects": ["navigation", "submenu_displayed", "action_triggered"],
            "interaction_confidence": 0.85,
        }
        
        # Tab
        templates[ComponentType.TAB] = {
            "supported_actions": ["select", "get_active", "verify_content"],
            "action_parameters": {
                "select": {"tab_index": "required", "tab_label": "optional"},
                "get_active": {},
                "verify_content": {},
            },
            "expected_outcomes": ["tab_selected", "content_changed", "tab_highlighted"],
            "side_effects": ["content_loaded", "url_changed", "lazy_load"],
            "interaction_confidence": 0.9,
        }
        
        # Pagination
        templates[ComponentType.PAGINATION] = {
            "supported_actions": ["next_page", "previous_page", "go_to_page", "get_page_info"],
            "action_parameters": {
                "next_page": {},
                "previous_page": {},
                "go_to_page": {"page_number": "required"},
                "get_page_info": {},
            },
            "expected_outcomes": ["page_changed", "content_updated", "url_changed"],
            "side_effects": ["content_loaded", "scroll_to_top", "loading_indicator"],
            "interaction_confidence": 0.85,
        }
        
        # Toast/Alert
        templates[ComponentType.TOAST] = {
            "supported_actions": ["wait_for_visible", "wait_for_hidden", "get_message", "dismiss"],
            "action_parameters": {
                "wait_for_visible": {"timeout": "optional"},
                "wait_for_hidden": {"timeout": "optional"},
                "get_message": {},
                "dismiss": {},
            },
            "expected_outcomes": ["message_retrieved", "toast_dismissed", "toast_auto_dismissed"],
            "side_effects": ["auto_dismiss", "queue_cleared"],
            "interaction_confidence": 0.8,
        }
        
        templates[ComponentType.ALERT] = templates[ComponentType.TOAST]
        
        # Accordion
        templates[ComponentType.ACCORDION] = {
            "supported_actions": ["expand", "collapse", "toggle", "verify_expanded"],
            "action_parameters": {
                "expand": {"panel_index": "required"},
                "collapse": {"panel_index": "required"},
                "toggle": {"panel_index": "required"},
                "verify_expanded": {"panel_index": "required"},
            },
            "expected_outcomes": ["panel_expanded", "panel_collapsed", "content_visible"],
            "side_effects": ["other_panels_collapsed", "scroll_to_panel"],
            "interaction_confidence": 0.85,
        }
        
        return templates
    
    def build_interaction_model(
        self,
        component_type: ComponentType,
        custom_actions: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> InteractionModel:
        """Build an interaction model for a component.
        
        Args:
            component_type: Type of component
            custom_actions: Optional custom actions to add
            context: Additional context for customization
            
        Returns:
            Interaction model for the component
        """
        context = context or {}
        
        # Get base template
        template = self.interaction_templates.get(
            component_type,
            self._get_default_template()
        )
        
        # Build interaction model
        supported_actions = template["supported_actions"].copy()
        if custom_actions:
            supported_actions.extend(custom_actions)
        
        action_parameters = template["action_parameters"].copy()
        expected_outcomes = template["expected_outcomes"].copy()
        side_effects = template["side_effects"].copy()
        interaction_confidence = template["interaction_confidence"]
        
        # Customize based on context
        if context.get("is_password_field"):
            action_parameters["fill"]["secure"] = "optional"
            side_effects.append("masking_applied")
        
        if context.get("is_required"):
            expected_outcomes.append("validation_required")
        
        if context.get("has_validation"):
            action_parameters["validate"] = {}
            expected_outcomes.append("validation_performed")
        
        return InteractionModel(
            component_type=component_type,
            supported_actions=supported_actions,
            action_parameters=action_parameters,
            expected_outcomes=expected_outcomes,
            side_effects=side_effects,
            interaction_confidence=interaction_confidence,
        )
    
    def _get_default_template(self) -> Dict[str, Any]:
        """Get default template for unknown component types."""
        return {
            "supported_actions": ["click", "hover", "get_text"],
            "action_parameters": {
                "click": {},
                "hover": {},
                "get_text": {},
            },
            "expected_outcomes": ["action_triggered"],
            "side_effects": ["ui_update"],
            "interaction_confidence": 0.5,
        }