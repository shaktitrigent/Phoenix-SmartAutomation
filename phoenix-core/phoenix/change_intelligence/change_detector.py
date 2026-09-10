"""Change Detector - Priority 29.

This module detects application changes by comparing current state with baselines.
It classifies changes semantically and provides evidence for decision making.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.change_intelligence.models import (
    ChangeType,
    ChangeSeverity,
    SemanticChange,
    Baseline,
)
from phoenix.change_intelligence.baseline_manager import BaselineManager

# Reuse existing DOM diff engine
try:
    from phoenix.execution.dom_diff import DOMDifferenceEngine, DOMChange
    DOM_DIFF_AVAILABLE = True
except ImportError:
    DOM_DIFF_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detects and classifies application changes.
    
    This detector:
    - Compares current state with baseline
    - Detects DOM changes
    - Detects component changes
    - Detects locator changes
    - Detects flow changes
    - Classifies changes semantically
    - Provides evidence for decisions
    """
    
    def __init__(self, baseline_manager: Optional[BaselineManager] = None):
        """Initialize change detector.
        
        Args:
            baseline_manager: Baseline manager instance
        """
        self.baseline_manager = baseline_manager or BaselineManager()
        
        # DOM diff engine
        self.dom_diff_engine = DOMDifferenceEngine() if DOM_DIFF_AVAILABLE else None
        
        logger.info("[CHANGE DETECTOR] Initialized")
        logger.info(f"[CHANGE DETECTOR] DOM diff engine: {'AVAILABLE' if DOM_DIFF_AVAILABLE else 'NOT AVAILABLE'}")
    
    def detect_changes(
        self,
        url: str,
        current_dom: str,
        current_page_type: str,
        current_components: List[Dict[str, Any]],
        current_locators: List[Dict[str, Any]],
        current_flows: List[Dict[str, Any]],
    ) -> List[SemanticChange]:
        """Detect changes by comparing current state with baseline.
        
        Args:
            url: Page URL
            current_dom: Current DOM snapshot
            current_page_type: Current page type
            current_components: Current components
            current_locators: Current locators
            current_flows: Current flows
            
        Returns:
            List of detected changes
        """
        logger.info(f"[CHANGE DETECTOR] Detecting changes for: {url}")
        
        # Get latest baseline
        previous_baseline = self.baseline_manager.get_latest_baseline(url)
        
        # Create current baseline
        current_baseline = self.baseline_manager.create_baseline(
            url=url,
            dom_snapshot=current_dom,
            page_type=current_page_type,
            components=current_components,
            locators=current_locators,
            flows=current_flows,
        )
        
        # If no previous baseline, this is the first run
        if not previous_baseline:
            logger.info("[CHANGE DETECTOR] No previous baseline - establishing baseline")
            return []
        
        # Compare baselines
        comparison = self.baseline_manager.compare_baselines(
            previous_baseline,
            current_baseline,
        )
        
        if not comparison["has_changes"]:
            logger.info("[CHANGE DETECTOR] No changes detected")
            return []
        
        # Detect specific changes
        changes = []
        
        # Detect DOM changes
        if comparison["dom_changed"] and self.dom_diff_engine:
            dom_changes = self._detect_dom_changes(
                previous_baseline.dom_snapshot,
                current_baseline.dom_snapshot,
            )
            changes.extend(dom_changes)
        
        # Detect page type changes
        if comparison["page_type_changed"]:
            change = self._create_page_type_change(
                previous_baseline.page_type,
                current_baseline.page_type,
            )
            changes.append(change)
        
        # Detect component changes
        if comparison["component_count_changed"]:
            component_changes = self._detect_component_changes(
                previous_baseline.components,
                current_baseline.components,
            )
            changes.extend(component_changes)
        
        # Detect locator changes
        if comparison["locator_count_changed"]:
            locator_changes = self._detect_locator_changes(
                previous_baseline.locators,
                current_baseline.locators,
            )
            changes.extend(locator_changes)
        
        # Detect flow changes
        if comparison["flow_count_changed"]:
            flow_changes = self._detect_flow_changes(
                previous_baseline.flows,
                current_baseline.flows,
            )
            changes.extend(flow_changes)
        
        logger.info(f"[CHANGE DETECTOR] Detected {len(changes)} changes")
        
        return changes
    
    def _detect_dom_changes(
        self,
        old_dom: str,
        new_dom: str,
    ) -> List[SemanticChange]:
        """Detect DOM changes using DOM diff engine.
        
        Args:
            old_dom: Previous DOM
            new_dom: Current DOM
            
        Returns:
            List of DOM changes
        """
        if not self.dom_diff_engine:
            return []
        
        try:
            diff_report = self.dom_diff_engine.compare(
                old_dom=old_dom,
                new_dom=new_dom,
            )
            
            changes = []
            for dom_change in diff_report.changes:
                change = SemanticChange(
                    change_id=f"CHANGE-{uuid4().hex[:8]}",
                    change_type=self._map_dom_change_type(dom_change.change_type),
                    previous_state={"value": dom_change.old_value},
                    current_state={"value": dom_change.new_value},
                    severity=self._assess_dom_severity(dom_change),
                    confidence=dom_change.confidence,
                    evidence={
                        "element_tag": dom_change.element_tag,
                        "element_id": dom_change.element_id,
                        "element_class": dom_change.element_class,
                        "xpath": dom_change.xpath,
                    },
                )
                changes.append(change)
            
            return changes
            
        except Exception as e:
            logger.warning(f"[CHANGE DETECTOR] DOM diff failed: {e}")
            return []
    
    def _detect_component_changes(
        self,
        old_components: List[Dict[str, Any]],
        new_components: List[Dict[str, Any]],
    ) -> List[SemanticChange]:
        """Detect component changes.
        
        Args:
            old_components: Previous components
            new_components: Current components
            
        Returns:
            List of component changes
        """
        changes = []
        
        old_ids = {c.get("id", "") for c in old_components}
        new_ids = {c.get("id", "") for c in new_components}
        
        # Detect added components
        added_ids = new_ids - old_ids
        for comp_id in added_ids:
            comp = next(c for c in new_components if c.get("id", "") == comp_id)
            change = SemanticChange(
                change_id=f"CHANGE-{uuid4().hex[:8]}",
                change_type=ChangeType.COMPONENT_ADDED,
                previous_state={},
                current_state=comp,
                severity=ChangeSeverity.MINOR,
                confidence=0.9,
                evidence={"component": comp},
            )
            changes.append(change)
        
        # Detect removed components
        removed_ids = old_ids - new_ids
        for comp_id in removed_ids:
            comp = next(c for c in old_components if c.get("id", "") == comp_id)
            change = SemanticChange(
                change_id=f"CHANGE-{uuid4().hex[:8]}",
                change_type=ChangeType.COMPONENT_REMOVED,
                previous_state=comp,
                current_state={},
                severity=ChangeSeverity.SIGNIFICANT,
                confidence=0.9,
                evidence={"component": comp},
            )
            changes.append(change)
        
        return changes
    
    def _detect_locator_changes(
        self,
        old_locators: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> List[SemanticChange]:
        """Detect locator changes.
        
        Args:
            old_locators: Previous locators
            new_locators: Current locators
            
        Returns:
            List of locator changes
        """
        changes = []
        
        # Simple comparison by selector
        old_selectors = {l.get("selector", "") for l in old_locators}
        new_selectors = {l.get("selector", "") for l in new_locators}
        
        # Detect changed locators
        changed_selectors = old_selectors & new_selectors
        for selector in changed_selectors:
            old_loc = next(l for l in old_locators if l.get("selector", "") == selector)
            new_loc = next(l for l in new_locators if l.get("selector", "") == selector)
            
            if old_loc != new_loc:
                change = SemanticChange(
                    change_id=f"CHANGE-{uuid4().hex[:8]}",
                    change_type=ChangeType.LOCATOR_CHANGED,
                    previous_state=old_loc,
                    current_state=new_loc,
                    severity=ChangeSeverity.SIGNIFICANT,
                    confidence=0.85,
                    evidence={"locator": selector},
                )
                changes.append(change)
        
        return changes
    
    def _detect_flow_changes(
        self,
        old_flows: List[Dict[str, Any]],
        new_flows: List[Dict[str, Any]],
    ) -> List[SemanticChange]:
        """Detect flow changes.
        
        Args:
            old_flows: Previous flows
            new_flows: Current flows
            
        Returns:
            List of flow changes
        """
        changes = []
        
        old_flow_ids = {f.get("flow_id", "") for f in old_flows}
        new_flow_ids = {f.get("flow_id", "") for f in new_flows}
        
        # Detect added flows
        added_flow_ids = new_flow_ids - old_flow_ids
        for flow_id in added_flow_ids:
            flow = next(f for f in new_flows if f.get("flow_id", "") == flow_id)
            change = SemanticChange(
                change_id=f"CHANGE-{uuid4().hex[:8]}",
                change_type=ChangeType.FLOW_ADDED,
                previous_state={},
                current_state=flow,
                severity=ChangeSeverity.MINOR,
                confidence=0.8,
                evidence={"flow": flow},
            )
            changes.append(change)
        
        # Detect removed flows
        removed_flow_ids = old_flow_ids - new_flow_ids
        for flow_id in removed_flow_ids:
            flow = next(f for f in old_flows if f.get("flow_id", "") == flow_id)
            change = SemanticChange(
                change_id=f"CHANGE-{uuid4().hex[:8]}",
                change_type=ChangeType.FLOW_REMOVED,
                previous_state=flow,
                current_state={},
                severity=ChangeSeverity.SIGNIFICANT,
                confidence=0.8,
                evidence={"flow": flow},
            )
            changes.append(change)
        
        return changes
    
    def _create_page_type_change(
        self,
        old_page_type: str,
        new_page_type: str,
    ) -> SemanticChange:
        """Create a page type change.
        
        Args:
            old_page_type: Previous page type
            new_page_type: Current page type
            
        Returns:
            Page type change
        """
        return SemanticChange(
            change_id=f"CHANGE-{uuid4().hex[:8]}",
            change_type=ChangeType.PAGE_TYPE_CHANGED,
            previous_state={"page_type": old_page_type},
            current_state={"page_type": new_page_type},
            severity=ChangeSeverity.SIGNIFICANT,
            confidence=0.95,
            evidence={
                "old_page_type": old_page_type,
                "new_page_type": new_page_type,
            },
        )
    
    def _map_dom_change_type(self, dom_change_type: str) -> ChangeType:
        """Map DOM change type to semantic change type.
        
        Args:
            dom_change_type: DOM change type
            
        Returns:
            Semantic change type
        """
        mapping = {
            "added": ChangeType.COMPONENT_ADDED,
            "removed": ChangeType.COMPONENT_REMOVED,
            "modified": ChangeType.COMPONENT_MODIFIED,
        }
        return mapping.get(dom_change_type, ChangeType.DOM_CHANGED)
    
    def _assess_dom_severity(self, dom_change) -> ChangeSeverity:
        """Assess severity of DOM change.
        
        Args:
            dom_change: DOM change
            
        Returns:
            Change severity
        """
        # Simple severity assessment
        if dom_change.change_type == "removed":
            return ChangeSeverity.SIGNIFICANT
        elif dom_change.change_type == "added":
            return ChangeSeverity.MINOR
        else:
            return ChangeSeverity.MINOR
