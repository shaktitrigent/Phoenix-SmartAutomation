"""Component Relationship Analyzer - Generic Component Relationship Detection (Priority 22).

This module detects relationships between components based on DOM structure,
spatial proximity, and semantic patterns.

This is completely generic and works for ANY web application without product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    ComponentRelationship,
)

logger = logging.getLogger(__name__)


class ComponentRelationshipAnalyzer:
    """Generic component relationship analyzer using DOM and spatial analysis.
    
    This analyzer detects:
    - Parent-child relationships
    - Form member relationships
    - Table cell relationships
    - Navigation group relationships
    - Modal trigger relationships
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the relationship analyzer."""
        logger.info("[COMPONENT RELATIONSHIP ANALYZER] Initialized")
    
    def analyze_relationships(
        self,
        components: List[SemanticComponent],
        dom_structure: Dict[str, Any] = None,
    ) -> List[ComponentRelationship]:
        """Analyze relationships between all components.
        
        Args:
            components: List of components to analyze
            dom_structure: Optional DOM structure information
            
        Returns:
            List of detected component relationships
        """
        relationships = []
        
        # Build component lookup
        component_map = {c.component_id: c for c in components if c.component_id}
        
        # Detect parent-child relationships
        parent_child = self._detect_parent_child_relationships(components, dom_structure)
        relationships.extend(parent_child)
        
        # Detect form member relationships
        form_members = self._detect_form_relationships(components)
        relationships.extend(form_members)
        
        # Detect table relationships
        table_relationships = self._detect_table_relationships(components)
        relationships.extend(table_relationships)
        
        # Detect navigation relationships
        nav_relationships = self._detect_navigation_relationships(components)
        relationships.extend(nav_relationships)
        
        # Detect modal relationships
        modal_relationships = self._detect_modal_relationships(components)
        relationships.extend(modal_relationships)
        
        logger.info(f"[COMPONENT RELATIONSHIP ANALYZER] Detected {len(relationships)} relationships")
        
        return relationships
    
    def _detect_parent_child_relationships(
        self,
        components: List[SemanticComponent],
        dom_structure: Dict[str, Any] = None,
    ) -> List[ComponentRelationship]:
        """Detect parent-child relationships from DOM structure."""
        relationships = []
        
        for component in components:
            if not component.component_id:
                continue
            
            # Find potential children based on XPath
            children = self._find_children_by_xpath(component, components)
            
            for child in children:
                if not child.component_id:
                    continue
                
                relationship = ComponentRelationship(
                    relationship_type="parent_child",
                    source_component_id=component.component_id,
                    target_component_id=child.component_id,
                    confidence=0.8,
                    evidence=["XPath nesting detected"],
                    dom_distance=self._calculate_xpath_distance(component, child),
                )
                relationships.append(relationship)
        
        return relationships
    
    def _detect_form_relationships(
        self,
        components: List[SemanticComponent],
    ) -> List[ComponentRelationship]:
        """Detect form member relationships."""
        relationships = []
        
        # Find form containers and their members
        form_containers = [c for c in components if c.component_type in [
            ComponentType.MODAL,  # Modals often contain forms
            ComponentType.CARD,   # Cards can contain forms
        ]]
        
        form_fields = [c for c in components if c.component_type in [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.FILE_UPLOAD,
            ComponentType.CALENDAR,
        ]]
        
        submit_buttons = [c for c in components if c.component_type == ComponentType.BUTTON]
        
        # Group form fields and buttons
        for container in form_containers:
            if not container.component_id:
                continue
            
            # Find nearby form fields
            nearby_fields = self._find_nearby_components(
                container,
                form_fields,
                max_distance=3,
            )
            
            for field in nearby_fields:
                if not field.component_id:
                    continue
                
                relationship = ComponentRelationship(
                    relationship_type="form_member",
                    source_component_id=container.component_id,
                    target_component_id=field.component_id,
                    confidence=0.7,
                    evidence=["Form field near container"],
                    dom_distance=self._calculate_xpath_distance(container, field),
                )
                relationships.append(relationship)
        
        # Connect submit buttons to forms
        for button in submit_buttons:
            if not button.component_id:
                continue
            
            # Find nearby form fields
            nearby_fields = self._find_nearby_components(
                button,
                form_fields,
                max_distance=5,
            )
            
            if nearby_fields:
                # Assume button submits the nearest form
                nearest_field = nearby_fields[0]
                
                relationship = ComponentRelationship(
                    relationship_type="form_submit",
                    source_component_id=button.component_id,
                    target_component_id=nearest_field.component_id,
                    confidence=0.6,
                    evidence=["Submit button near form fields"],
                    dom_distance=self._calculate_xpath_distance(button, nearest_field),
                )
                relationships.append(relationship)
        
        return relationships
    
    def _detect_table_relationships(
        self,
        components: List[SemanticComponent],
    ) -> List[ComponentRelationship]:
        """Detect table relationships."""
        relationships = []
        
        tables = [c for c in components if c.component_type == ComponentType.TABLE]
        
        for table in tables:
            if not table.component_id:
                continue
            
            # Find components that might be in this table
            # In a real implementation, this would use DOM structure
            # For now, we'll use spatial proximity
            nearby_components = self._find_nearby_components(
                table,
                components,
                max_distance=10,
            )
            
            for nearby in nearby_components:
                if nearby.component_id == table.component_id:
                    continue
                if not nearby.component_id:
                    continue
                
                relationship = ComponentRelationship(
                    relationship_type="table_member",
                    source_component_id=table.component_id,
                    target_component_id=nearby.component_id,
                    confidence=0.5,
                    evidence=["Component near table"],
                    dom_distance=self._calculate_xpath_distance(table, nearby),
                )
                relationships.append(relationship)
        
        return relationships
    
    def _detect_navigation_relationships(
        self,
        components: List[SemanticComponent],
    ) -> List[ComponentRelationship]:
        """Detect navigation group relationships."""
        relationships = []
        
        # Find navigation-related components
        nav_components = [c for c in components if c.component_type in [
            ComponentType.LINK,
            ComponentType.BUTTON,
            ComponentType.MENU,
            ComponentType.TAB,
            ComponentType.BREADCRUMB,
        ]]
        
        # Group nearby navigation components
        for i, comp1 in enumerate(nav_components):
            if not comp1.component_id:
                continue
            
            for comp2 in nav_components[i+1:]:
                if not comp2.component_id:
                    continue
                
                # Check if they're nearby
                distance = self._calculate_xpath_distance(comp1, comp2)
                if distance and distance < 5:
                    relationship = ComponentRelationship(
                        relationship_type="navigation_group",
                        source_component_id=comp1.component_id,
                        target_component_id=comp2.component_id,
                        confidence=0.6,
                        evidence=["Navigation components near each other"],
                        dom_distance=distance,
                    )
                    relationships.append(relationship)
        
        return relationships
    
    def _detect_modal_relationships(
        self,
        components: List[SemanticComponent],
    ) -> List[ComponentRelationship]:
        """Detect modal trigger relationships."""
        relationships = []
        
        # Find buttons/links that might open modals
        triggers = [c for c in components if c.component_type in [
            ComponentType.BUTTON,
            ComponentType.LINK,
        ]]
        
        modals = [c for c in components if c.component_type == ComponentType.MODAL]
        
        for trigger in triggers:
            if not trigger.component_id:
                continue
            
            trigger_text = f"{trigger.text_content} {trigger.label}".lower()
            
            # Look for modal-related keywords
            modal_keywords = ["open", "show", "display", "view", "details", "edit", "add", "create"]
            
            if any(keyword in trigger_text for keyword in modal_keywords):
                # This might be a modal trigger
                # In a real implementation, we'd connect it to the specific modal
                # For now, we'll just note it as a potential trigger
                pass
        
        return relationships
    
    def _find_children_by_xpath(
        self,
        parent: SemanticComponent,
        components: List[SemanticComponent],
    ) -> List[SemanticComponent]:
        """Find child components based on XPath nesting."""
        children = []
        
        if not parent.xpath:
            return children
        
        for component in components:
            if not component.xpath or component.component_id == parent.component_id:
                continue
            
            # Check if component's XPath starts with parent's XPath
            if component.xpath.startswith(parent.xpath):
                children.append(component)
        
        return children
    
    def _find_nearby_components(
        self,
        component: SemanticComponent,
        candidates: List[SemanticComponent],
        max_distance: int = 5,
    ) -> List[SemanticComponent]:
        """Find components nearby the given component."""
        nearby = []
        
        for candidate in candidates:
            if candidate.component_id == component.component_id:
                continue
            
            distance = self._calculate_xpath_distance(component, candidate)
            if distance and distance <= max_distance:
                nearby.append(candidate)
        
        # Sort by distance
        nearby.sort(key=lambda c: self._calculate_xpath_distance(component, c) or 999)
        
        return nearby
    
    def _calculate_xpath_distance(
        self,
        comp1: SemanticComponent,
        comp2: SemanticComponent,
    ) -> Optional[int]:
        """Calculate DOM distance between two components using XPath."""
        if not comp1.xpath or not comp2.xpath:
            return None
        
        # Simple distance calculation based on XPath depth
        # In a real implementation, this would use actual DOM structure
        parts1 = comp1.xpath.split('/')
        parts2 = comp2.xpath.split('/')
        
        # Find common prefix
        common = 0
        for i, (p1, p2) in enumerate(zip(parts1, parts2)):
            if p1 == p2:
                common += 1
            else:
                break
        
        # Distance is total depth minus common prefix
        distance = (len(parts1) - common) + (len(parts2) - common)
        
        return distance