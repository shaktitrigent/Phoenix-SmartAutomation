"""Autonomous Decision Engine - Priority 28.

This module implements the decision-making logic for the autonomous agent.
The decision engine determines what actions to take during exploration based on
evidence, semantic understanding, and risk assessment.

Priority 28: Universal Autonomous End-to-End Agent + Real Headed Runtime Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from phoenix.autonomous.models import (
    DecisionType,
    RiskLevel,
    AutonomousDecision,
)

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Autonomous decision engine for Phoenix.
    
    This engine makes intelligent decisions about:
    - What to explore next
    - What components to interact with
    - What actions to execute
    - When to terminate exploration
    - What to skip
    """
    
    def __init__(self, confidence_threshold: float = 0.7, max_risk: RiskLevel = RiskLevel.MEDIUM):
        """Initialize the decision engine.
        
        Args:
            confidence_threshold: Minimum confidence to make a decision
            max_risk: Maximum acceptable risk level
        """
        self.confidence_threshold = confidence_threshold
        self.max_risk = max_risk
        self.decision_history: List[AutonomousDecision] = []
        
        logger.info("[DECISION ENGINE] Initialized")
        logger.info(f"[DECISION ENGINE] Confidence threshold: {confidence_threshold}")
        logger.info(f"[DECISION ENGINE] Max risk: {max_risk.value}")
    
    def should_explore_page(
        self,
        url: str,
        page_type: str,
        component_count: int,
        navigation_links: List[str],
    ) -> AutonomousDecision:
        """Decide whether to explore a page.
        
        Args:
            url: Page URL
            page_type: Type of page
            component_count: Number of components on page
            navigation_links: Navigation links found
            
        Returns:
            AutonomousDecision
        """
        evidence = {
            "url": url,
            "page_type": page_type,
            "component_count": component_count,
            "navigation_links": len(navigation_links),
        }
        
        # Decision logic
        confidence = 0.8
        reason = f"Page has {component_count} components and {len(navigation_links)} navigation links"
        risk = RiskLevel.LOW
        
        # Adjust confidence based on page type
        if page_type in ["dashboard", "form", "table", "search"]:
            confidence = 0.9
            reason = f"Page type '{page_type}' is high-value for testing"
        elif page_type in ["error", "login", "logout"]:
            confidence = 0.6
            reason = f"Page type '{page_type}' has limited testing value"
            risk = RiskLevel.MEDIUM
        
        decision = AutonomousDecision(
            decision_type=DecisionType.EXPLORE_PAGE,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            risk=risk,
        )
        
        self.decision_history.append(decision)
        logger.info(f"[DECISION] Explore page: {url} (confidence: {confidence})")
        
        return decision
    
    def should_click_element(
        self,
        element_type: str,
        element_text: str,
        element_purpose: str,
        interactive: bool,
    ) -> AutonomousDecision:
        """Decide whether to click an element.
        
        Args:
            element_type: Type of element (button, link, etc.)
            element_text: Text content of element
            element_purpose: Purpose of element
            interactive: Whether element is interactive
            
        Returns:
            AutonomousDecision
        """
        evidence = {
            "element_type": element_type,
            "element_text": element_text,
            "element_purpose": element_purpose,
            "interactive": interactive,
        }
        
        # Decision logic
        confidence = 0.5
        reason = f"Element is a {element_type}"
        risk = RiskLevel.LOW
        
        if not interactive:
            confidence = 0.2
            reason = "Element is not interactive"
            risk = RiskLevel.MEDIUM
        elif element_purpose in ["submit", "save", "confirm", "delete"]:
            confidence = 0.7
            reason = f"Element purpose '{element_purpose}' is high-value"
            risk = RiskLevel.MEDIUM
        elif element_purpose in ["navigation", "menu", "tab"]:
            confidence = 0.8
            reason = f"Element purpose '{element_purpose}' enables flow discovery"
            risk = RiskLevel.LOW
        elif element_type in ["button", "link"]:
            confidence = 0.75
            reason = f"Element type '{element_type}' is standard interactive element"
        
        decision = AutonomousDecision(
            decision_type=DecisionType.CLICK_ELEMENT,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            risk=risk,
        )
        
        self.decision_history.append(decision)
        logger.info(f"[DECISION] Click element: {element_text} (confidence: {confidence})")
        
        return decision
    
    def should_fill_input(
        self,
        input_type: str,
        input_purpose: str,
        required: bool,
        has_validation: bool,
    ) -> AutonomousDecision:
        """Decide whether to fill an input field.
        
        Args:
            input_type: Type of input (text, email, password, etc.)
            input_purpose: Purpose of input
            required: Whether input is required
            has_validation: Whether input has validation
            
        Returns:
            AutonomousDecision
        """
        evidence = {
            "input_type": input_type,
            "input_purpose": input_purpose,
            "required": required,
            "has_validation": has_validation,
        }
        
        # Decision logic
        confidence = 0.6
        reason = f"Input field of type '{input_type}'"
        risk = RiskLevel.LOW
        
        if input_type in ["password", "hidden"]:
            confidence = 0.3
            reason = f"Input type '{input_type}' is sensitive"
            risk = RiskLevel.HIGH
        elif required:
            confidence = 0.9
            reason = "Required field must be filled"
        elif has_validation:
            confidence = 0.8
            reason = "Input has validation - good for testing"
        elif input_purpose in ["search", "filter", "query"]:
            confidence = 0.85
            reason = f"Input purpose '{input_purpose}' is high-value"
        
        decision = AutonomousDecision(
            decision_type=DecisionType.FILL_INPUT,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            risk=risk,
        )
        
        self.decision_history.append(decision)
        logger.info(f"[DECISION] Fill input: {input_purpose} (confidence: {confidence})")
        
        return decision
    
    def should_submit_form(
        self,
        form_purpose: str,
        required_fields: int,
        filled_fields: int,
        validation_present: bool,
    ) -> AutonomousDecision:
        """Decide whether to submit a form.
        
        Args:
            form_purpose: Purpose of the form
            required_fields: Number of required fields
            filled_fields: Number of filled fields
            validation_present: Whether form has validation
            
        Returns:
            AutonomousDecision
        """
        evidence = {
            "form_purpose": form_purpose,
            "required_fields": required_fields,
            "filled_fields": filled_fields,
            "validation_present": validation_present,
        }
        
        # Decision logic
        confidence = 0.5
        reason = f"Form with {required_fields} required fields"
        risk = RiskLevel.MEDIUM
        
        if filled_fields < required_fields:
            confidence = 0.2
            reason = f"Not all required fields filled ({filled_fields}/{required_fields})"
            risk = RiskLevel.HIGH
        elif form_purpose in ["delete", "destroy", "remove"]:
            confidence = 0.4
            reason = f"Form purpose '{form_purpose}' is destructive"
            risk = RiskLevel.HIGH
        elif form_purpose in ["create", "save", "update", "submit"]:
            confidence = 0.8
            reason = f"Form purpose '{form_purpose}' is standard CRUD operation"
            risk = RiskLevel.MEDIUM
        elif validation_present:
            confidence = 0.75
            reason = "Form has validation - good for testing"
        
        decision = AutonomousDecision(
            decision_type=DecisionType.SUBMIT_FORM,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            risk=risk,
        )
        
        self.decision_history.append(decision)
        logger.info(f"[DECISION] Submit form: {form_purpose} (confidence: {confidence})")
        
        return decision
    
    def should_terminate_exploration(
        self,
        pages_explored: int,
        time_elapsed_seconds: int,
        unique_components: int,
        flows_discovered: int,
    ) -> AutonomousDecision:
        """Decide whether to terminate exploration.
        
        Args:
            pages_explored: Number of pages explored
            time_elapsed_seconds: Time elapsed in seconds
            unique_components: Number of unique components discovered
            flows_discovered: Number of flows discovered
            
        Returns:
            AutonomousDecision
        """
        evidence = {
            "pages_explored": pages_explored,
            "time_elapsed_seconds": time_elapsed_seconds,
            "unique_components": unique_components,
            "flows_discovered": flows_discovered,
        }
        
        # Decision logic
        confidence = 0.5
        reason = "Exploration criteria evaluation"
        risk = RiskLevel.LOW
        
        # Termination criteria
        if pages_explored >= 10:
            confidence = 0.9
            reason = f"Explored {pages_explored} pages - sufficient coverage"
        elif time_elapsed_seconds >= 300:  # 5 minutes
            confidence = 0.85
            reason = f"Time limit reached ({time_elapsed_seconds}s)"
        elif unique_components >= 50:
            confidence = 0.8
            reason = f"Discovered {unique_components} unique components - sufficient coverage"
        elif flows_discovered >= 5:
            confidence = 0.85
            reason = f"Discovered {flows_discovered} flows - sufficient coverage"
        else:
            confidence = 0.3
            reason = "More exploration needed"
        
        decision = AutonomousDecision(
            decision_type=DecisionType.TERMINATE_EXPLORATION,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            risk=risk,
        )
        
        self.decision_history.append(decision)
        logger.info(f"[DECISION] Terminate exploration: {reason} (confidence: {confidence})")
        
        return decision
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """Get summary of decisions made.
        
        Returns:
            Decision summary
        """
        decision_types = {}
        for decision in self.decision_history:
            dtype = decision.decision_type.value
            decision_types[dtype] = decision_types.get(dtype, 0) + 1
        
        return {
            "total_decisions": len(self.decision_history),
            "decision_types": decision_types,
            "average_confidence": sum(d.confidence for d in self.decision_history) / len(self.decision_history) if self.decision_history else 0,
        }
