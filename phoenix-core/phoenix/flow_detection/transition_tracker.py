"""Page Transition Tracker - Track semantic page transitions.

This module tracks transitions between semantic pages, building the foundation
for business flow discovery. It maintains transition history and computes
transition confidence based on observed patterns.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from phoenix.flow_detection.models import (
    PageTransition,
    SemanticAction,
    ActionType,
)

logger = logging.getLogger(__name__)


class PageTransitionTracker:
    """Tracks semantic page transitions for flow discovery.
    
    This tracker:
    - Records transitions between semantic pages
    - Infers actions from DOM changes and user interactions
    - Maintains transition history with confidence scores
    - Supports both real-time and batch analysis
    """
    
    def __init__(
        self,
        base_dir: str = "phoenix_runtime",
        enable_persistence: bool = True,
    ):
        """Initialize the page transition tracker.
        
        Args:
            base_dir: Base directory for storage
            enable_persistence: Enable transition persistence
        """
        self.base_dir = Path(base_dir)
        self.transition_storage_dir = self.base_dir / "transitions"
        self.transition_storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_persistence = enable_persistence
        
        # In-memory transition history
        self.transitions: List[PageTransition] = []
        
        # Current state tracking
        self.current_page_type: Optional[str] = None
        self.current_url: Optional[str] = None
        self.current_dom_hash: Optional[str] = None
        self.current_semantic_page: Optional[Any] = None
        
        logger.info(f"[TRANSITION TRACKER] Initialized with storage: {self.transition_storage_dir}")
        logger.info(f"[TRANSITION TRACKER] Persistence enabled: {enable_persistence}")
    
    def _compute_dom_hash(self, dom_content: str) -> str:
        """Compute SHA256 hash of DOM content."""
        return hashlib.sha256(dom_content.encode('utf-8')).hexdigest()
    
    def set_current_page(
        self,
        page_type: str,
        url: str,
        dom_content: str,
        semantic_page: Any = None,
    ) -> None:
        """Set the current page state.
        
        Args:
            page_type: Semantic page type
            url: Page URL
            dom_content: DOM content
            semantic_page: Full semantic page object
        """
        self.current_page_type = page_type
        self.current_url = url
        self.current_dom_hash = self._compute_dom_hash(dom_content)
        self.current_semantic_page = semantic_page
        
        logger.debug(f"[TRANSITION TRACKER] Current page set: {page_type} at {url}")
    
    def infer_action_from_dom_change(
        self,
        previous_dom: str,
        current_dom: str,
        element_info: Dict[str, Any],
    ) -> SemanticAction:
        """Infer semantic action from DOM changes.
        
        Args:
            previous_dom: Previous DOM content
            current_dom: Current DOM content
            element_info: Information about the element that changed
            
        Returns:
            Inferred semantic action
        """
        # Extract element information
        role = element_info.get("role", "")
        text = element_info.get("text", "")
        label = element_info.get("label", "")
        xpath = element_info.get("xpath", "")
        
        # Infer action type based on element properties
        action_type = self._classify_action(role, text, label)
        
        # Build evidence
        evidence = []
        if role:
            evidence.append(f"Element role: {role}")
        if text:
            evidence.append(f"Element text: {text}")
        if label:
            evidence.append(f"Element label: {label}")
        
        # Create semantic action
        action = SemanticAction(
            action_type=action_type,
            confidence=0.7,  # Base confidence for DOM-inferred actions
            element_role=role,
            element_text=text,
            element_label=label,
            element_xpath=xpath,
            page_type=self.current_page_type or "unknown",
            page_url=self.current_url or "",
            evidence=evidence,
            detection_method="dom_change",
        )
        
        logger.debug(f"[TRANSITION TRACKER] Inferred action: {action_type.value} (confidence: 0.7)")
        
        return action
    
    def _classify_action(self, role: str, text: str, label: str) -> ActionType:
        """Classify action type from element properties.
        
        Args:
            role: ARIA role
            text: Element text
            label: Element label
            
        Returns:
            Classified action type
        """
        # Combine text sources
        combined_text = f"{text} {label}".lower()
        
        # Classification rules (generic, application-agnostic)
        if role == "button":
            if any(word in combined_text for word in ["submit", "save", "confirm", "continue"]):
                return ActionType.SUBMIT
            elif any(word in combined_text for word in ["cancel", "close", "back"]):
                return ActionType.CANCEL
            elif any(word in combined_text for word in ["next", "forward"]):
                return ActionType.NEXT
            elif any(word in combined_text for word in ["create", "add", "new"]):
                return ActionType.CREATE
            elif any(word in combined_text for word in ["edit", "update", "modify"]):
                return ActionType.EDIT
            elif any(word in combined_text for word in ["delete", "remove"]):
                return ActionType.DELETE
            elif any(word in combined_text for word in ["approve", "accept"]):
                return ActionType.APPROVE
            elif any(word in combined_text for word in ["search", "find"]):
                return ActionType.SEARCH
            elif any(word in combined_text for word in ["upload", "attach"]):
                return ActionType.UPLOAD
            elif any(word in combined_text for word in ["download", "export"]):
                return ActionType.DOWNLOAD
            else:
                return ActionType.CLICK
        
        elif role == "link":
            if any(word in combined_text for word in ["back", "return"]):
                return ActionType.BACK
            elif any(word in combined_text for word in ["next", "continue"]):
                return ActionType.NEXT
            else:
                return ActionType.NAVIGATE
        
        elif role == "textbox" or role == "searchbox":
            if "search" in combined_text or "find" in combined_text:
                return ActionType.SEARCH
            else:
                return ActionType.FILL
        
        elif role == "combobox" or role == "listbox":
            return ActionType.SELECT
        
        elif role == "checkbox":
            return ActionType.SELECT
        
        elif role == "file":
            return ActionType.UPLOAD
        
        else:
            return ActionType.UNKNOWN
    
    def record_transition(
        self,
        target_page_type: str,
        target_url: str,
        target_dom_content: str,
        action: SemanticAction,
        execution_id: str = "",
        test_id: str = "",
        project_name: str = "",
    ) -> PageTransition:
        """Record a page transition.
        
        Args:
            target_page_type: Semantic type of target page
            target_url: URL of target page
            target_dom_content: DOM content of target page
            action: Action that caused the transition
            execution_id: Execution ID
            test_id: Test ID
            project_name: Project name
            
        Returns:
            Recorded page transition
        """
        # Create transition
        transition = PageTransition(
            source_page_type=self.current_page_type or "unknown",
            source_url=self.current_url or "",
            source_dom_hash=self.current_dom_hash or "",
            target_page_type=target_page_type,
            target_url=target_url,
            target_dom_hash=self._compute_dom_hash(target_dom_content),
            action=action,
            transition_type=self._infer_transition_type(
                self.current_page_type or "unknown",
                target_page_type,
                action.action_type
            ),
            confidence=0.8,  # Base confidence for observed transitions
            execution_id=execution_id,
            test_id=test_id,
            project_name=project_name,
            dom_change_detected=(self.current_dom_hash != self._compute_dom_hash(target_dom_content)),
            evidence=[f"Action: {action.action_type.value}"],
        )
        
        # Add to history
        self.transitions.append(transition)
        
        # Update current state
        self.current_page_type = target_page_type
        self.current_url = target_url
        self.current_dom_hash = transition.target_dom_hash
        
        # Persist if enabled
        if self.enable_persistence:
            self._persist_transition(transition)
        
        logger.info(f"[TRANSITION TRACKER] Recorded transition: {transition.source_page_type} -> {transition.target_page_type}")
        logger.info(f"[TRANSITION TRACKER] Action: {action.action_type.value}")
        
        return transition
    
    def _infer_transition_type(self, source: str, target: str, action: ActionType) -> str:
        """Infer transition type from source, target, and action.
        
        Args:
            source: Source page type
            target: Target page type
            action: Action type
            
        Returns:
            Inferred transition type
        """
        # Generic transition type inference
        if source == "authentication_screen" and target == "dashboard":
            return "authentication_success"
        elif source == "dashboard" and target == "crud_form":
            return "navigate_to_create"
        elif source == "crud_form" and target == "dashboard":
            if action == ActionType.SUBMIT:
                return "form_submission_success"
            elif action == ActionType.CANCEL:
                return "form_cancellation"
        elif source == "table_view" and target == "crud_form":
            return "navigate_to_edit"
        elif source == "search_screen" and target == "table_view":
            return "search_results"
        else:
            return "generic_navigation"
    
    def _persist_transition(self, transition: PageTransition) -> None:
        """Persist a transition to storage.
        
        Args:
            transition: Transition to persist
        """
        try:
            # Create project-specific storage
            project_dir = self.transition_storage_dir / transition.project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # Create execution-specific file
            execution_file = project_dir / f"transitions_{transition.execution_id}.jsonl"
            
            # Append transition
            with open(execution_file, "a", encoding="utf-8") as f:
                f.write(transition.model_dump_json() + "\n")
            
            logger.debug(f"[TRANSITION TRACKER] Persisted transition to {execution_file}")
        except Exception as e:
            logger.warning(f"[TRANSITION TRACKER] Failed to persist transition: {e}")
    
    def get_transitions(
        self,
        project_name: str = "",
        execution_id: str = "",
        limit: int = 100,
    ) -> List[PageTransition]:
        """Get transitions from history.
        
        Args:
            project_name: Filter by project name
            execution_id: Filter by execution ID
            limit: Maximum number of transitions to return
            
        Returns:
            List of transitions
        """
        filtered = self.transitions
        
        if project_name:
            filtered = [t for t in filtered if t.project_name == project_name]
        
        if execution_id:
            filtered = [t for t in filtered if t.execution_id == execution_id]
        
        # Return most recent first
        return sorted(filtered, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    def get_transition_patterns(
        self,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Analyze transition patterns.
        
        Args:
            project_name: Filter by project name
            
        Returns:
            Transition pattern analysis
        """
        transitions = self.get_transitions(project_name=project_name, limit=1000)
        
        patterns = {
            "total_transitions": len(transitions),
            "unique_page_types": set(),
            "unique_actions": set(),
            "transition_frequency": {},
            "action_frequency": {},
        }
        
        for transition in transitions:
            patterns["unique_page_types"].add(transition.source_page_type)
            patterns["unique_page_types"].add(transition.target_page_type)
            patterns["unique_actions"].add(transition.action.action_type.value)
            
            # Count transition pairs
            pair = f"{transition.source_page_type} -> {transition.target_page_type}"
            patterns["transition_frequency"][pair] = patterns["transition_frequency"].get(pair, 0) + 1
            
            # Count actions
            action = transition.action.action_type.value
            patterns["action_frequency"][action] = patterns["action_frequency"].get(action, 0) + 1
        
        patterns["unique_page_types"] = list(patterns["unique_page_types"])
        patterns["unique_actions"] = list(patterns["unique_actions"])
        
        return patterns
    
    def clear_history(self) -> None:
        """Clear transition history."""
        self.transitions.clear()
        logger.info("[TRANSITION TRACKER] Transition history cleared")
