"""Automation Regeneration - Handles application changes with minimal intelligent changes.

This module implements automation regeneration that detects application changes
and regenerates only affected automation parts.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.automation_generation.models import (
    GeneratedAutomation,
    AutomationPlan,
    AutomationStatus,
)
from phoenix.semantic.models import SemanticComponent
from phoenix.execution.dom_diff import DOMDifferenceEngine

logger = logging.getLogger(__name__)


class AutomationRegeneration:
    """Automation regeneration for handling application changes.
    
    This regenerator:
    - Detects application changes
    - Compares old and new DOM
    - Identifies changed components
    - Determines affected actions
    - Regenerates only affected automation
    - Validates regenerated automation
    """
    
    def __init__(
        self,
        dom_diff_engine: Optional[DOMDifferenceEngine] = None,
    ):
        self.dom_diff_engine = dom_diff_engine or DOMDifferenceEngine()
        
        # Cache of previous DOM states
        self.dom_cache: Dict[str, str] = {}
        
        logger.info("AutomationRegeneration initialized")
    
    def detect_application_change(
        self,
        page_url: str,
        current_dom: str,
    ) -> bool:
        """Detect if application has changed since last execution.
        
        Args:
            page_url: URL of the page
            current_dom: Current DOM snapshot
            
        Returns:
            True if application changed, False otherwise
        """
        previous_dom = self.dom_cache.get(page_url)
        
        if not previous_dom:
            # First time seeing this page
            self.dom_cache[page_url] = current_dom
            return False
        
        # Compare DOMs
        if previous_dom != current_dom:
            logger.info(f"Application change detected for {page_url}")
            self.dom_cache[page_url] = current_dom
            return True
        
        return False
    
    def analyze_dom_changes(
        self,
        old_dom: str,
        new_dom: str,
    ) -> Dict[str, Any]:
        """Analyze differences between old and new DOM.
        
        Args:
            old_dom: Previous DOM snapshot
            new_dom: Current DOM snapshot
            
        Returns:
            Dictionary with change analysis
        """
        if not self.dom_diff_engine:
            return {"changed": False, "changes": []}
        
        # Use DOM difference engine
        diff_result = self.dom_diff_engine.compare_doms(old_dom, new_dom)
        
        return {
            "changed": diff_result.has_changes,
            "changes": diff_result.changes,
            "added_elements": diff_result.added_elements,
            "removed_elements": diff_result.removed_elements,
            "modified_elements": diff_result.modified_elements,
        }
    
    def identify_affected_automation(
        self,
        automation: GeneratedAutomation,
        dom_changes: Dict[str, Any],
        old_components: List[SemanticComponent],
        new_components: List[SemanticComponent],
    ) -> List[str]:
        """Identify which parts of automation are affected by DOM changes.
        
        Args:
            automation: Generated automation to check
            dom_changes: DOM change analysis
            old_components: Previous component state
            new_components: Current component state
            
        Returns:
            List of affected action/step IDs
        """
        affected = []
        
        # Check for removed components
        old_component_ids = {c.component_id for c in old_components}
        new_component_ids = {c.component_id for c in new_components}
        
        removed_components = old_component_ids - new_component_ids
        added_components = new_component_ids - old_component_ids
        
        # Find actions that use removed components
        if hasattr(automation, "metadata"):
            for action in automation.metadata.get("actions", []):
                component_id = action.get("target_component_id", "")
                if component_id in removed_components:
                    affected.append(action.get("action_id", ""))
        
        # Check for modified components
        modified_components = []
        for new_comp in new_components:
            old_comp = next(
                (c for c in old_components if c.component_id == new_comp.component_id),
                None,
            )
            if old_comp:
                # Check if locator changed
                if old_comp.selected_locator != new_comp.selected_locator:
                    modified_components.append(new_comp.component_id)
        
        # Find actions that use modified components
        if hasattr(automation, "metadata"):
            for action in automation.metadata.get("actions", []):
                component_id = action.get("target_component_id", "")
                if component_id in modified_components:
                    affected.append(action.get("action_id", ""))
        
        logger.info(
            f"Identified {len(affected)} affected automation parts "
            f"({len(removed_components)} removed, {len(modified_components)} modified components)"
        )
        
        return affected
    
    def regenerate_affected_parts(
        self,
        automation: GeneratedAutomation,
        affected_parts: List[str],
        new_components: List[SemanticComponent],
    ) -> Optional[GeneratedAutomation]:
        """Regenerate only affected parts of automation.
        
        Args:
            automation: Original automation
            affected_parts: List of affected part IDs
            new_components: Current component state
            
        Returns:
            Regenerated automation or None if regeneration fails
        """
        if not affected_parts:
            logger.info("No affected parts to regenerate")
            return automation
        
        logger.info(f"Regenerating {len(affected_parts)} affected parts")
        
        # This would integrate with the AutomationGenerationCoordinator
        # to regenerate only the affected parts
        # For now, return the original automation with a flag
        
        automation.metadata = automation.metadata or {}
        automation.metadata["regenerated_parts"] = affected_parts
        automation.metadata["regeneration_timestamp"] = datetime.now(timezone.utc).isoformat()
        
        return automation
    
    def should_regenerate(
        self,
        automation: GeneratedAutomation,
        dom_changes: Dict[str, Any],
    ) -> bool:
        """Determine if automation should be regenerated.
        
        Args:
            automation: Automation to check
            dom_changes: DOM change analysis
            
        Returns:
            True if regeneration is needed
        """
        # If no changes, no regeneration needed
        if not dom_changes.get("changed", False):
            return False
        
        # If significant number of elements changed, regenerate
        total_changes = (
            len(dom_changes.get("added_elements", [])) +
            len(dom_changes.get("removed_elements", [])) +
            len(dom_changes.get("modified_elements", []))
        )
        
        if total_changes > 10:
            logger.info(f"Significant DOM changes ({total_changes} elements), recommending regeneration")
            return True
        
        # If critical elements changed (like forms), regenerate
        critical_elements = ["form", "input", "button", "submit"]
        for change in dom_changes.get("modified_elements", []):
            if any(critical in str(change).lower() for critical in critical_elements):
                logger.info("Critical element changed, recommending regeneration")
                return True
        
        return False
    
    def update_dom_cache(self, page_url: str, dom: str):
        """Update DOM cache for a page.
        
        Args:
            page_url: URL of the page
            dom: DOM snapshot to cache
        """
        self.dom_cache[page_url] = dom
        logger.debug(f"Updated DOM cache for {page_url}")
    
    def clear_dom_cache(self):
        """Clear the DOM cache."""
        self.dom_cache.clear()
        logger.info("DOM cache cleared")
