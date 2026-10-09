"""DOM Difference Engine - Compare DOM snapshots and detect changes.

This module implements DOM comparison that:
- Compares previous and current DOM snapshots
- Detects added, removed, and modified nodes
- Identifies changed attributes, IDs, and text
- Generates detailed change reports
- Provides verifiable change evidence
"""

from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# DOM Diff Models
# ---------------------------------------------------------------------------

class DOMChange(BaseModel):
    """Single DOM change record."""
    change_type: str = Field(..., description="added, removed, modified")
    element_tag: str = ""
    element_id: str = ""
    element_class: str = ""
    element_text: str = ""
    xpath: str = ""
    old_value: str = ""
    new_value: str = ""
    confidence: float = 1.0


class DOMDiffReport(BaseModel):
    """Complete DOM difference report."""
    old_hash: str = ""
    new_hash: str = ""
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    changed_elements: List[str] = Field(default_factory=list)
    changes: List[DOMChange] = Field(default_factory=list)
    summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# DOM Difference Engine
# ---------------------------------------------------------------------------

class DOMDifferenceEngine:
    """Engine for comparing DOM snapshots and detecting changes.
    
    Features:
    - Node addition/removal detection
    - Attribute change detection
    - Text content change detection
    - XPath-based element tracking
    - Detailed change reporting
    """
    
    def __init__(self, artifacts_manager=None):
        self.artifacts_manager = artifacts_manager
    
    def compare(
        self,
        old_dom: str,
        new_dom: str,
        old_hash: str = "",
        new_hash: str = ""
    ) -> DOMDiffReport:
        """Compare two DOM snapshots.
        
        Args:
            old_dom: Previous DOM content
            new_dom: Current DOM content
            old_hash: Hash of old DOM
            new_hash: Hash of new DOM
            
        Returns:
            DOM difference report
        """
        # Parse DOMs into comparable structures
        old_elements = self._parse_dom(old_dom)
        new_elements = self._parse_dom(new_dom)
        
        # Detect changes
        changes = []
        
        # Find added elements
        added = self._find_added_elements(old_elements, new_elements)
        changes.extend(added)
        
        # Find removed elements
        removed = self._find_removed_elements(old_elements, new_elements)
        changes.extend(removed)
        
        # Find modified elements
        modified = self._find_modified_elements(old_elements, new_elements)
        changes.extend(modified)
        
        # Build report
        report = DOMDiffReport(
            old_hash=old_hash,
            new_hash=new_hash,
            added_count=len(added),
            removed_count=len(removed),
            modified_count=len(modified),
            changed_elements=self._extract_changed_element_names(changes),
            changes=changes,
            summary=self._generate_summary(added, removed, modified)
        )
        
        # Save report if artifacts manager available
        if self.artifacts_manager:
            self._save_diff_report(report)
        
        return report
    
    def _parse_dom(self, dom_content: str) -> List[Dict[str, Any]]:
        """Parse DOM content into comparable structure.
        
        Args:
            dom_content: HTML content
            
        Returns:
            List of element dictionaries
        """
        elements = []
        
        # Simple regex-based parsing (could be enhanced with proper HTML parser)
        # Find all opening tags
        tag_pattern = re.compile(r'<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>')
        
        for match in tag_pattern.finditer(dom_content):
            tag = match.group(1)
            attrs_str = match.group(2)
            
            # Parse attributes
            attrs = {}
            attr_pattern = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
            for attr_match in attr_pattern.finditer(attrs_str):
                attrs[attr_match.group(1)] = attr_match.group(2)
            
            # Extract text content (simplified)
            text = ""
            text_match = re.search(r'>{([^<]+)<', dom_content[match.end():match.end()+100])
            if text_match:
                text = text_match.group(1).strip()
            
            element = {
                "tag": tag,
                "id": attrs.get("id", ""),
                "class": attrs.get("class", ""),
                "text": text,
                "attrs": attrs,
                "xpath": self._generate_simple_xpath(tag, attrs)
            }
            
            elements.append(element)
        
        return elements
    
    def _find_added_elements(
        self,
        old_elements: List[Dict[str, Any]],
        new_elements: List[Dict[str, Any]]
    ) -> List[DOMChange]:
        """Find elements that were added.
        
        Args:
            old_elements: Previous DOM elements
            new_elements: Current DOM elements
            
        Returns:
            List of added element changes
        """
        added = []
        
        # Create signature sets for comparison
        old_signatures = {self._element_signature(e) for e in old_elements}
        
        for element in new_elements:
            sig = self._element_signature(element)
            if sig not in old_signatures:
                change = DOMChange(
                    change_type="added",
                    element_tag=element["tag"],
                    element_id=element["id"],
                    element_class=element["class"],
                    element_text=element["text"],
                    xpath=element["xpath"],
                    new_value=json.dumps(element["attrs"], default=str)
                )
                added.append(change)
        
        return added
    
    def _find_removed_elements(
        self,
        old_elements: List[Dict[str, Any]],
        new_elements: List[Dict[str, Any]]
    ) -> List[DOMChange]:
        """Find elements that were removed.
        
        Args:
            old_elements: Previous DOM elements
            new_elements: Current DOM elements
            
        Returns:
            List of removed element changes
        """
        removed = []
        
        # Create signature sets for comparison
        new_signatures = {self._element_signature(e) for e in new_elements}
        
        for element in old_elements:
            sig = self._element_signature(element)
            if sig not in new_signatures:
                change = DOMChange(
                    change_type="removed",
                    element_tag=element["tag"],
                    element_id=element["id"],
                    element_class=element["class"],
                    element_text=element["text"],
                    xpath=element["xpath"],
                    old_value=json.dumps(element["attrs"], default=str)
                )
                removed.append(change)
        
        return removed
    
    def _find_modified_elements(
        self,
        old_elements: List[Dict[str, Any]],
        new_elements: List[Dict[str, Any]]
    ) -> List[DOMChange]:
        """Find elements that were modified.
        
        Args:
            old_elements: Previous DOM elements
            new_elements: Current DOM elements
            
        Returns:
            List of modified element changes
        """
        modified = []
        
        # Create signature maps
        old_map = {self._element_signature(e): e for e in old_elements}
        new_map = {self._element_signature(e): e for e in new_elements}
        
        # Find common elements
        common_signatures = set(old_map.keys()) & set(new_map.keys())
        
        for sig in common_signatures:
            old_elem = old_map[sig]
            new_elem = new_map[sig]
            
            # Check for modifications
            changes = self._detect_element_changes(old_elem, new_elem)
            
            if changes:
                for change_type, old_val, new_val in changes:
                    change = DOMChange(
                        change_type="modified",
                        element_tag=old_elem["tag"],
                        element_id=old_elem["id"],
                        element_class=old_elem["class"],
                        element_text=old_elem["text"],
                        xpath=old_elem["xpath"],
                        old_value=old_val,
                        new_value=new_val
                    )
                    modified.append(change)
        
        return modified
    
    def _detect_element_changes(
        self,
        old_elem: Dict[str, Any],
        new_elem: Dict[str, Any]
    ) -> List[Tuple[str, str, str]]:
        """Detect specific changes in an element.
        
        Args:
            old_elem: Old element data
            new_elem: New element data
            
        Returns:
            List of (change_type, old_value, new_value) tuples
        """
        changes = []
        
        # Check ID change
        if old_elem["id"] != new_elem["id"]:
            changes.append(("id_changed", old_elem["id"], new_elem["id"]))
        
        # Check class change
        if old_elem["class"] != new_elem["class"]:
            changes.append(("class_changed", old_elem["class"], new_elem["class"]))
        
        # Check text change
        if old_elem["text"] != new_elem["text"]:
            changes.append(("text_changed", old_elem["text"], new_elem["text"]))
        
        # Check attribute changes
        old_attrs = set(old_elem["attrs"].items())
        new_attrs = set(new_elem["attrs"].items())
        
        if old_attrs != new_attrs:
            changes.append(("attrs_changed", 
                          json.dumps(old_elem["attrs"], default=str),
                          json.dumps(new_elem["attrs"], default=str)))
        
        return changes
    
    def _element_signature(self, element: Dict[str, Any]) -> str:
        """Generate unique signature for element comparison.
        
        Args:
            element: Element dictionary
            
        Returns:
            Unique signature string
        """
        parts = [element["tag"]]
        
        if element["id"]:
            parts.append(f"id={element['id']}")
        
        if element["class"]:
            parts.append(f"class={element['class']}")
        
        if element["text"]:
            parts.append(f"text={element['text'][:20]}")  # Truncate long text
        
        return "|".join(parts)
    
    def _generate_simple_xpath(self, tag: str, attrs: Dict[str, str]) -> str:
        """Generate simple XPath for element.
        
        Args:
            tag: Element tag
            attrs: Element attributes
            
        Returns:
            Simple XPath string
        """
        parts = [f"//{tag}"]
        
        if "id" in attrs and attrs["id"]:
            parts.append(f"[@id='{attrs['id']}']")
        elif "class" in attrs and attrs["class"]:
            parts.append(f"[@class='{attrs['class']}']")
        
        return "".join(parts)
    
    def _extract_changed_element_names(self, changes: List[DOMChange]) -> List[str]:
        """Extract human-readable element names from changes.
        
        Args:
            changes: List of DOM changes
            
        Returns:
            List of element names
        """
        names = []
        
        for change in changes:
            # Build descriptive name
            parts = []
            
            if change.element_text:
                parts.append(change.element_text)
            elif change.element_id:
                parts.append(f"#{change.element_id}")
            elif change.element_class:
                parts.append(f".{change.element_class}")
            
            if change.element_tag:
                parts.append(f"<{change.element_tag}>")
            
            if parts:
                names.append(" ".join(parts))
        
        return names[:10]  # Limit to top 10 changed elements
    
    def _generate_summary(
        self,
        added: List[DOMChange],
        removed: List[DOMChange],
        modified: List[DOMChange]
    ) -> str:
        """Generate human-readable summary.
        
        Args:
            added: Added changes
            removed: Removed changes
            modified: Modified changes
            
        Returns:
            Summary string
        """
        parts = []
        
        if added:
            parts.append(f"{len(added)} nodes added")
        if removed:
            parts.append(f"{len(removed)} nodes removed")
        if modified:
            parts.append(f"{len(modified)} nodes modified")
        
        if not parts:
            return "No changes detected"
        
        return ", ".join(parts)
    
    def _save_diff_report(self, report: DOMDiffReport) -> None:
        """Save diff report to artifacts.
        
        Args:
            report: DOM difference report
        """
        if not self.artifacts_manager:
            return
        
        try:
            run_dir = self.artifacts_manager.get_run_directory()
            if run_dir:
                dom_dir = run_dir / "dom"
                diff_path = dom_dir / "dom_diff.json"
                diff_path.write_text(report.model_dump_json(indent=2), encoding='utf-8')
        except Exception as e:
            pass  # Don't fail if artifact saving fails