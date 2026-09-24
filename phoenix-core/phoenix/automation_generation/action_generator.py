"""Universal Action Generator - Translates semantic actions to executable Playwright actions.

This module implements a generic action generator that converts semantic actions
from automation plans into executable Playwright code based on component intelligence.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.automation_generation.models import (
    Action,
    ActionType,
)
from phoenix.semantic.models import SemanticComponent, ComponentType

logger = logging.getLogger(__name__)


class ActionGenerator:
    """Universal action generator for converting semantic actions to Playwright code.
    
    This generator:
    - Maps semantic actions to Playwright methods
    - Determines correct action from component intelligence
    - Generates action parameters
    - Handles action-specific logic
    - Supports fallback actions
    """
    
    def __init__(self):
        self.action_mappings = self._initialize_action_mappings()
        logger.info("ActionGenerator initialized")
    
    def generate_action(
        self,
        action_type: ActionType,
        component: Optional[SemanticComponent] = None,
        parameters: Optional[Dict[str, Any]] = None,
        locator: Optional[str] = None,
    ) -> Action:
        """Generate an executable action from semantic components.
        
        Args:
            action_type: Type of action to generate
            component: Semantic component for context
            parameters: Action parameters
            locator: Target locator
            
        Returns:
            Generated Action with Playwright code
        """
        action = Action(
            action_id=f"ACT-{uuid.uuid4().hex[:8].upper()}",
            action_type=action_type,
            target_component_id=component.component_id if component else "",
            target_locator=locator or "",
            parameters=parameters or {},
            page_context=component.page_type if component else "",
            business_context=component.business_intent if component else "",
        )
        
        # Generate Playwright code for the action
        action_code = self._generate_playwright_code(action, component)
        action.parameters["playwright_code"] = action_code
        
        # Calculate confidence
        action.confidence = self._calculate_action_confidence(action, component)
        
        # Generate evidence
        action.evidence = self._generate_action_evidence(action, component)
        
        # Generate fallback locators if component available
        if component and component.locator_candidates:
            action.fallback_locators = self._generate_fallback_locators(component)
        
        logger.debug(
            f"Generated action {action.action_id} of type {str(action_type)} "
            f"with confidence {action.confidence:.2f}"
        )
        
        return action
    
    def _initialize_action_mappings(self) -> Dict[ComponentType, Dict[ActionType, str]]:
        """Initialize action mappings for component types."""
        return {
            ComponentType.TEXT_FIELD: {
                ActionType.FILL: "fill",
                ActionType.CLEAR: "clear",
                ActionType.TYPE: "type",
                ActionType.PRESS: "press",
            },
            ComponentType.DROPDOWN: {
                ActionType.SELECT: "select_option",
                ActionType.CLICK: "click",
            },
            ComponentType.CHECKBOX: {
                ActionType.CHECK: "check",
                ActionType.UNCHECK: "uncheck",
                ActionType.CLICK: "click",
            },
            ComponentType.RADIO_BUTTON: {
                ActionType.SELECT: "check",
                ActionType.CLICK: "click",
            },
            ComponentType.BUTTON: {
                ActionType.CLICK: "click",
                ActionType.HOVER: "hover",
                ActionType.DOUBLE_CLICK: "dblclick",
            },
            ComponentType.LINK: {
                ActionType.CLICK: "click",
                ActionType.HOVER: "hover",
            },
            ComponentType.TABLE: {
                ActionType.CLICK: "click",
            },
            ComponentType.FILE_UPLOAD: {
                ActionType.UPLOAD: "set_input_files",
            },
            ComponentType.MODAL: {
                ActionType.CLOSE: "close",
            },
        }
    
    def _generate_playwright_code(
        self,
        action: Action,
        component: Optional[SemanticComponent],
    ) -> str:
        """Generate Playwright code for an action."""
        locator = action.target_locator or "page"
        params = action.parameters
        
        if action.action_type == ActionType.NAVIGATE:
            url = params.get("url", "")
            return f'page.goto("{url}")'
        
        elif action.action_type == ActionType.CLICK:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.FILL:
            value = params.get("value", "")
            return f'{locator}.fill("{value}")'
        
        elif action.action_type == ActionType.SELECT:
            value = params.get("value", "")
            return f'{locator}.select_option("{value}")'
        
        elif action.action_type == ActionType.CHECK:
            return f"{locator}.check()"
        
        elif action.action_type == ActionType.UNCHECK:
            return f"{locator}.uncheck()"
        
        elif action.action_type == ActionType.UPLOAD:
            file_path = params.get("file_path", "")
            return f'{locator}.set_input_files("{file_path}")'
        
        elif action.action_type == ActionType.HOVER:
            return f"{locator}.hover()"
        
        elif action.action_type == ActionType.PRESS:
            key = params.get("key", "Enter")
            return f'{locator}.press("{key}")'
        
        elif action.action_type == ActionType.SCROLL:
            direction = params.get("direction", "down")
            if direction == "down":
                return "page.mouse.wheel(0, 500)"
            elif direction == "up":
                return "page.mouse.wheel(0, -500)"
            else:
                return "page.evaluate('window.scrollBy(0, 500)')"
        
        elif action.action_type == ActionType.SEARCH:
            query = params.get("query", "")
            return f'{locator}.fill("{query}")'
        
        elif action.action_type == ActionType.SUBMIT:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.WAIT:
            duration = params.get("duration_ms", 1000)
            return f"page.wait_for_timeout({duration})"
        
        elif action.action_type == ActionType.OPEN:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.CLOSE:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.EXPAND:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.COLLAPSE:
            return f"{locator}.click()"
        
        elif action.action_type == ActionType.SWITCH_TAB:
            tab_index = params.get("tab_index", 1)
            return f"page.context.pages()[{tab_index}].bring_to_front()"
        
        elif action.action_type == ActionType.SWITCH_FRAME:
            frame_name = params.get("frame_name", "")
            return f'page.frame(name="{frame_name}")'
        
        elif action.action_type == ActionType.TYPE:
            value = params.get("value", "")
            return f'{locator}.type("{value}")'
        
        elif action.action_type == ActionType.CLEAR:
            return f"{locator}.clear()"
        
        elif action.action_type == ActionType.DOUBLE_CLICK:
            return f"{locator}.dblclick()"
        
        elif action.action_type == ActionType.RIGHT_CLICK:
            return f"{locator}.click(button='right')"
        
        else:
            # Default fallback
            return f"{locator}.click()"
    
    def _calculate_action_confidence(
        self,
        action: Action,
        component: Optional[SemanticComponent],
    ) -> float:
        """Calculate confidence score for an action."""
        base_confidence = 0.7
        
        # Boost confidence if component supports the action
        if component:
            action_type_value = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
            if action_type_value in component.supported_actions:
                base_confidence += 0.2
            
            # Boost based on component interaction confidence
            base_confidence += component.interaction_confidence * 0.1
        
        # Boost if locator is provided
        if action.target_locator:
            base_confidence += 0.1
        
        # Boost if parameters are complete
        if action.parameters:
            base_confidence += 0.05
        
        return min(base_confidence, 1.0)
    
    def _generate_action_evidence(
        self,
        action: Action,
        component: Optional[SemanticComponent],
    ) -> List[str]:
        """Generate evidence for action decision."""
        evidence = []
        
        if component:
            component_type_value = component.component_type.value if hasattr(component.component_type, 'value') else str(component.component_type)
            evidence.append(f"Component type: {component_type_value}")
            evidence.append(f"Component purpose: {component.semantic_purpose}")
            
            action_type_value = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
            if action_type_value in component.supported_actions:
                evidence.append("Action supported by component")
            
            if component.interaction_confidence > 0.8:
                evidence.append("High component interaction confidence")
        
        if action.target_locator:
            evidence.append("Locator provided")
        
        if action.parameters:
            evidence.append("Parameters provided")
        
        return evidence
    
    def _generate_fallback_locators(
        self,
        component: SemanticComponent,
    ) -> List[str]:
        """Generate fallback locators from component candidates."""
        fallbacks = []
        
        # Sort candidates by confidence
        sorted_candidates = sorted(
            component.locator_candidates,
            key=lambda x: x.get("confidence", 0.0),
            reverse=True,
        )
        
        # Take top 3 fallbacks (excluding primary)
        for candidate in sorted_candidates[1:4]:
            locator = candidate.get("locator", "")
            if locator:
                fallbacks.append(locator)
        
        return fallbacks
    
    def determine_action_from_component(
        self,
        component: SemanticComponent,
        business_intent: str = "",
    ) -> ActionType:
        """Determine the appropriate action from component intelligence.
        
        This is the core intelligence mapping from semantic component to action.
        """
        component_type = component.component_type
        purpose = component.semantic_purpose
        
        # Map based on component purpose (Priority 22 intelligence)
        if purpose == "form_submit":
            return ActionType.SUBMIT
        elif purpose == "form_cancel":
            return ActionType.CLICK
        elif purpose == "search_trigger":
            return ActionType.CLICK
        elif purpose == "create_trigger":
            return ActionType.CLICK
        elif purpose == "edit_trigger":
            return ActionType.CLICK
        elif purpose == "delete_trigger":
            return ActionType.CLICK
        elif purpose == "login_trigger":
            return ActionType.CLICK
        elif purpose == "logout_trigger":
            return ActionType.CLICK
        elif purpose == "username_input":
            return ActionType.FILL
        elif purpose == "password_input":
            return ActionType.FILL
        elif purpose == "search_input":
            return ActionType.FILL
        elif purpose == "data_entry_input":
            return ActionType.FILL
        
        # Map based on component type
        if component_type == ComponentType.TEXT_FIELD:
            return ActionType.FILL
        elif component_type == ComponentType.DROPDOWN:
            return ActionType.SELECT
        elif component_type == ComponentType.CHECKBOX:
            return ActionType.CHECK
        elif component_type == ComponentType.RADIO_BUTTON:
            return ActionType.SELECT
        elif component_type == ComponentType.BUTTON:
            return ActionType.CLICK
        elif component_type == ComponentType.LINK:
            return ActionType.CLICK
        elif component_type == ComponentType.FILE_UPLOAD:
            return ActionType.UPLOAD
        elif component_type == ComponentType.MODAL:
            return ActionType.CLOSE
        
        # Default fallback
        return ActionType.CLICK
    
    def generate_action_from_step(
        self,
        step: str,
        component: Optional[SemanticComponent] = None,
        locator: Optional[str] = None,
    ) -> Action:
        """Generate action from a natural language step description."""
        step_lower = step.lower()
        
        # Determine action type from step
        if any(word in step_lower for word in ["navigate", "go to", "visit", "open"]):
            action_type = ActionType.NAVIGATE
        elif any(word in step_lower for word in ["click", "select", "choose", "press"]):
            action_type = ActionType.CLICK
        elif any(word in step_lower for word in ["enter", "type", "fill", "input"]):
            action_type = ActionType.FILL
        elif any(word in step_lower for word in ["select", "choose option", "pick"]):
            action_type = ActionType.SELECT
        elif any(word in step_lower for word in ["check", "tick"]):
            action_type = ActionType.CHECK
        elif any(word in step_lower for word in ["uncheck", "untick"]):
            action_type = ActionType.UNCHECK
        elif any(word in step_lower for word in ["upload", "attach"]):
            action_type = ActionType.UPLOAD
        elif any(word in step_lower for word in ["submit", "save", "confirm"]):
            action_type = ActionType.SUBMIT
        elif any(word in step_lower for word in ["wait", "pause"]):
            action_type = ActionType.WAIT
        elif any(word in step_lower for word in ["search", "find"]):
            action_type = ActionType.SEARCH
        elif any(word in step_lower for word in ["verify", "assert", "check", "ensure"]):
            action_type = ActionType.ASSERT
        else:
            # Use component intelligence if available
            if component:
                action_type = self.determine_action_from_component(component)
            else:
                action_type = ActionType.CLICK
        
        # Extract parameters from step
        parameters = self._extract_parameters_from_step(step, action_type)
        
        return self.generate_action(action_type, component, parameters, locator)
    
    def _extract_parameters_from_step(
        self,
        step: str,
        action_type: ActionType,
    ) -> Dict[str, Any]:
        """Extract parameters from step description."""
        params = {}
        step_lower = step.lower()
        
        if action_type == ActionType.NAVIGATE:
            # Look for URL patterns
            if "http" in step_lower:
                words = step.split()
                for word in words:
                    if "http" in word.lower():
                        params["url"] = word
                        break
        
        elif action_type == ActionType.FILL:
            # Look for value patterns
            if "with" in step_lower or "enter" in step_lower:
                words = step.split()
                for i, word in enumerate(words):
                    if word.lower() in ["with", "enter", "as"]:
                        if i + 1 < len(words):
                            params["value"] = words[i + 1].strip('"\'')
                            break
        
        elif action_type == ActionType.SELECT:
            # Look for option patterns
            if "option" in step_lower or "value" in step_lower:
                words = step.split()
                for i, word in enumerate(words):
                    if word.lower() in ["option", "value"]:
                        if i + 1 < len(words):
                            params["value"] = words[i + 1].strip('"\'')
                            break
        
        elif action_type == ActionType.WAIT:
            # Look for duration patterns
            if "second" in step_lower:
                import re
                match = re.search(r'(\d+)\s*second', step_lower)
                if match:
                    params["duration_ms"] = int(match.group(1)) * 1000
        
        elif action_type == ActionType.SEARCH:
            # Look for query patterns
            if "for" in step_lower:
                words = step.split()
                for i, word in enumerate(words):
                    if word.lower() == "for":
                        if i + 1 < len(words):
                            params["query"] = " ".join(words[i + 1:]).strip('"\'')
                            break
        
        return params
    
    def batch_generate_actions(
        self,
        actions_data: List[Dict[str, Any]],
        components_map: Optional[Dict[str, SemanticComponent]] = None,
    ) -> List[Action]:
        """Generate multiple actions from action data."""
        actions = []
        components_map = components_map or {}
        
        for action_data in actions_data:
            action_type = ActionType(action_data.get("action_type", "click"))
            component_id = action_data.get("target_component_id", "")
            component = components_map.get(component_id)
            locator = action_data.get("locator", "")
            parameters = action_data.get("parameters", {})
            
            action = self.generate_action(action_type, component, parameters, locator)
            actions.append(action)
        
        logger.info(f"Generated {len(actions)} actions")
        return actions
