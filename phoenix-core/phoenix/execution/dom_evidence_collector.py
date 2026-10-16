"""DOM Evidence Collector - Collects DOM evidence for intelligent healing.

This module provides intelligent DOM evidence collection to improve
healing quality by using actual page state instead of heuristics.
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DOMEvidence:
    """Collected DOM evidence for intelligent healing."""
    
    # Current DOM state
    current_dom_hash: str = ""
    dom_snapshot: Optional[Dict[str, Any]] = None
    
    # Element-specific evidence
    element_attributes: Dict[str, Any] = field(default_factory=dict)
    element_context: Dict[str, Any] = field(default_factory=dict)
    
    # Strategy preferences based on DOM analysis
    preferred_strategies: List[str] = field(default_factory=list)
    
    # Historical success data
    successful_locators: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    collection_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    page_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        return {
            "current_dom_hash": self.current_dom_hash,
            "dom_snapshot": self.dom_snapshot,
            "element_attributes": self.element_attributes,
            "element_context": self.element_context,
            "preferred_strategies": self.preferred_strategies,
            "successful_locators": self.successful_locators,
            "collection_timestamp": self.collection_timestamp,
            "page_url": self.page_url,
        }


class DOMEvidenceCollector:
    """Collects and analyzes DOM evidence for intelligent healing.
    
    This collector:
    - Captures current DOM state
    - Analyzes element attributes and context
    - Determines preferred locator strategies based on DOM characteristics
    - Tracks historical success patterns
    """
    
    def __init__(self, page=None):
        """Initialize the DOM evidence collector.
        
        Args:
            page: Playwright Page object (optional, can be set later)
        """
        self.page = page
        self._historical_data: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("DOM Evidence Collector initialized")
    
    def set_page(self, page):
        """Set the Playwright page object."""
        self.page = page
        logger.info("DOM Evidence Collector page updated")
    
    def collect_current_evidence(self, element_name: str = "") -> DOMEvidence:
        """Collect current DOM evidence.
        
        Args:
            element_name: Optional element name to focus evidence collection
            
        Returns:
            DOMEvidence object with collected data
        """
        if not self.page:
            logger.warning("No page available for DOM evidence collection")
            return DOMEvidence()
        
        try:
            # Collect basic DOM state
            dom_hash = self._compute_dom_hash()
            dom_snapshot = self._capture_dom_snapshot()
            
            # Analyze DOM characteristics
            preferred_strategies = self._analyze_dom_characteristics(dom_snapshot)
            
            # Collect element-specific evidence if element_name provided
            element_attributes = {}
            element_context = {}
            if element_name:
                element_attributes, element_context = self._collect_element_evidence(
                    element_name, dom_snapshot
                )
            
            # Get historical success data
            successful_locators = self._historical_data.get(element_name, [])
            
            evidence = DOMEvidence(
                current_dom_hash=dom_hash,
                dom_snapshot=dom_snapshot,
                element_attributes=element_attributes,
                element_context=element_context,
                preferred_strategies=preferred_strategies,
                successful_locators=successful_locators,
                page_url=self.page.url,
            )
            
            logger.info(
                f"DOM evidence collected: hash={dom_hash[:8]}, "
                f"strategies={len(preferred_strategies)}, "
                f"element={element_name or 'global'}"
            )
            
            return evidence
            
        except Exception as e:
            logger.error(f"Failed to collect DOM evidence: {e}")
            return DOMEvidence()
    
    def _compute_dom_hash(self) -> str:
        """Compute a hash of the current DOM state."""
        try:
            # Get page content and compute hash
            content = self.page.content()
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"Failed to compute DOM hash: {e}")
            return "unknown"
    
    def _capture_dom_snapshot(self) -> Optional[Dict[str, Any]]:
        """Capture a structured DOM snapshot."""
        try:
            # Use Playwright's built-in snapshot capabilities
            # This captures the accessible tree which is more stable than raw HTML
            snapshot = {
                "url": self.page.url,
                "title": self.page.title(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Try to get accessible tree if available
            try:
                # This is a simplified snapshot - in production you'd want more detail
                accessibility_tree = self.page.accessibility.snapshot()
                if accessibility_tree:
                    snapshot["accessibility_tree"] = self._simplify_accessibility_tree(
                        accessibility_tree
                    )
            except Exception as e:
                logger.debug(f"Could not capture accessibility tree: {e}")
            
            return snapshot
            
        except Exception as e:
            logger.warning(f"Failed to capture DOM snapshot: {e}")
            return None
    
    def _simplify_accessibility_tree(self, node: Dict[str, Any], max_depth: int = 3) -> Dict[str, Any]:
        """Simplify accessibility tree for evidence collection."""
        if max_depth <= 0:
            return {"role": node.get("role"), "name": node.get("name")}
        
        simplified = {
            "role": node.get("role"),
            "name": node.get("name"),
            "description": node.get("description"),
        }
        
        # Include key attributes
        if "checked" in node:
            simplified["checked"] = node["checked"]
        if "expanded" in node:
            simplified["expanded"] = node["expanded"]
        if "selected" in node:
            simplified["selected"] = node["selected"]
        
        # Recursively process children (limited depth)
        children = node.get("children", [])
        if children and max_depth > 1:
            simplified["children"] = [
                self._simplify_accessibility_tree(child, max_depth - 1)
                for child in children[:5]  # Limit to first 5 children
            ]
        
        return simplified
    
    def _analyze_dom_characteristics(self, dom_snapshot: Optional[Dict[str, Any]]) -> List[str]:
        """Analyze DOM characteristics to determine preferred locator strategies.
        
        Returns a list of preferred strategy names in order of preference.
        """
        preferred = []
        
        if not dom_snapshot:
            return preferred
        
        # Check for accessibility tree presence
        has_accessibility = "accessibility_tree" in dom_snapshot
        if has_accessibility:
            preferred.append("role")
            preferred.append("accessible_name")
        
        # Check for structured data attributes
        # In a real implementation, you'd scan the DOM for test IDs, data attributes, etc.
        # For now, we'll use heuristics based on common patterns
        
        # Default preferences based on best practices
        if not preferred:
            preferred = ["test_id", "role", "label", "name"]
        
        return preferred
    
    def _collect_element_evidence(
        self, element_name: str, dom_snapshot: Optional[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Collect element-specific evidence.
        
        Returns:
            Tuple of (element_attributes, element_context)
        """
        attributes = {}
        context = {}
        
        if not dom_snapshot or not self.page:
            return attributes, context
        
        try:
            # Try to find the element by various strategies
            # This is a simplified version - in production you'd want more sophisticated matching
            
            # For now, we'll collect basic page-level context
            context = {
                "page_url": self.page.url,
                "page_title": self.page.title(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # In a real implementation, you'd:
            # 1. Search for the element in the DOM
            # 2. Extract its attributes (id, class, data-*, aria-*, etc.)
            # 3. Analyze its parent/child context
            # 4. Check for similar elements that could cause ambiguity
            
        except Exception as e:
            logger.warning(f"Failed to collect element evidence: {e}")
        
        return attributes, context
    
    def record_successful_locator(
        self, element_name: str, strategy: str, locator: str, confidence: float
    ):
        """Record a successful locator for future healing decisions.
        
        Args:
            element_name: Name of the element
            strategy: Locator strategy that worked
            locator: The locator string that worked
            confidence: Confidence score of the locator
        """
        if element_name not in self._historical_data:
            self._historical_data[element_name] = []
        
        record = {
            "strategy": strategy,
            "locator": locator,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self._historical_data[element_name].append(record)
        
        # Keep only the last 10 successful records per element
        if len(self._historical_data[element_name]) > 10:
            self._historical_data[element_name] = self._historical_data[element_name][-10:]
        
        logger.info(
            f"Recorded successful locator for {element_name}: "
            f"{strategy} (confidence={confidence:.2f})"
        )
    
    def get_historical_success_rate(self, element_name: str, strategy: str) -> float:
        """Get the historical success rate for a specific strategy.
        
        Args:
            element_name: Name of the element
            strategy: Locator strategy to check
            
        Returns:
            Success rate between 0.0 and 1.0
        """
        if element_name not in self._historical_data:
            return 0.0
        
        records = self._historical_data[element_name]
        if not records:
            return 0.0
        
        strategy_records = [r for r in records if r["strategy"] == strategy]
        if not strategy_records:
            return 0.0
        
        # Simple success rate: count of recent uses
        # In a real implementation, you'd track actual success/failure
        return min(len(strategy_records) / len(records), 1.0)