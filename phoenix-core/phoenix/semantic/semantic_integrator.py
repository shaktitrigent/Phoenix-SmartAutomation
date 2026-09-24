"""Semantic Integrator - Integration with Existing Phoenix Modules.

This module integrates the semantic understanding system with existing Phoenix modules
including DOMSnapshotManager, IntelligentPage, IntelligentRuntime, KnowledgeBase,
and other runtime components.

The integrator ensures semantic understanding is seamlessly incorporated into the
existing Phoenix architecture without breaking existing functionality.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone

from phoenix.semantic.models import (
    SemanticPage,
    SemanticComponent,
    PageType,
    ComponentType,
    BusinessIntentType,
    NavigationContext,
    BusinessIntent,
)
from phoenix.semantic.page_classifier import SemanticPageClassifier
from phoenix.semantic.component_analyzer import UIComponentAnalyzer
from phoenix.semantic.intent_detector import BusinessIntentDetector
from phoenix.semantic.navigation_analyzer import NavigationStructureAnalyzer
# Priority 22: Universal Component Intelligence
from phoenix.semantic.component_purpose_detector import ComponentPurposeDetector
from phoenix.semantic.component_relationship_analyzer import ComponentRelationshipAnalyzer
from phoenix.semantic.interaction_model_builder import InteractionModelBuilder
from phoenix.semantic.validation_detector import ValidationDetector
from phoenix.semantic.locator_intelligence import LocatorIntelligence

logger = logging.getLogger(__name__)


class SemanticIntegrator:
    """Main integrator for semantic understanding with Phoenix modules.
    
    This integrator coordinates all semantic analysis components and
    integrates them with existing Phoenix infrastructure.
    """
    
    def __init__(
        self,
        base_dir: str = "phoenix_runtime",
        enable_page_classification: bool = True,
        enable_component_analysis: bool = True,
        enable_intent_detection: bool = True,
        enable_navigation_analysis: bool = True,
        enable_component_intelligence: bool = True,  # Priority 22
    ):
        """Initialize the semantic integrator.
        
        Args:
            base_dir: Base directory for semantic storage
            enable_page_classification: Enable page type classification
            enable_component_analysis: Enable UI component analysis
            enable_intent_detection: Enable business intent detection
            enable_navigation_analysis: Enable navigation structure analysis
            enable_component_intelligence: Enable Priority 22 component intelligence
        """
        self.base_dir = Path(base_dir)
        self.semantic_storage_dir = self.base_dir / "semantic_understanding"
        self.semantic_storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize semantic analyzers
        self.page_classifier = SemanticPageClassifier() if enable_page_classification else None
        self.component_analyzer = UIComponentAnalyzer() if enable_component_analysis else None
        self.intent_detector = BusinessIntentDetector() if enable_intent_detection else None
        self.navigation_analyzer = NavigationStructureAnalyzer() if enable_navigation_analysis else None
        
        # Priority 22: Initialize component intelligence modules
        self.component_purpose_detector = ComponentPurposeDetector() if enable_component_intelligence else None
        self.component_relationship_analyzer = ComponentRelationshipAnalyzer() if enable_component_intelligence else None
        self.interaction_model_builder = InteractionModelBuilder() if enable_component_intelligence else None
        self.validation_detector = ValidationDetector() if enable_component_intelligence else None
        self.locator_intelligence = LocatorIntelligence() if enable_component_intelligence else None
        
        # Configuration
        self.enable_page_classification = enable_page_classification
        self.enable_component_analysis = enable_component_analysis
        self.enable_intent_detection = enable_intent_detection
        self.enable_navigation_analysis = enable_navigation_analysis
        self.enable_component_intelligence = enable_component_intelligence
        
        logger.info(f"[SEMANTIC INTEGRATOR] Initialized with storage: {self.semantic_storage_dir}")
        logger.info(f"[SEMANTIC INTEGRATOR] Page classification: {enable_page_classification}")
        logger.info(f"[SEMANTIC INTEGRATOR] Component analysis: {enable_component_analysis}")
        logger.info(f"[SEMANTIC INTEGRATOR] Intent detection: {enable_intent_detection}")
        logger.info(f"[SEMANTIC INTEGRATOR] Navigation analysis: {enable_navigation_analysis}")
        logger.info(f"[SEMANTIC INTEGRATOR] Component intelligence (Priority 22): {enable_component_intelligence}")
    
    def analyze_page(
        self,
        url: str,
        title: str,
        heading: str,
        dom_content: str,
        dom_elements: List[Dict[str, Any]],
        text_content: str,
        project_name: str = "default",
        test_name: str = "default",
        execution_id: str = "",
        dom_hash: str = "",
    ) -> SemanticPage:
        """Perform complete semantic analysis of a page.
        
        Args:
            url: Page URL
            title: Page title
            heading: Main heading
            dom_content: Full DOM content
            dom_elements: List of DOM element dictionaries
            text_content: Page text content
            project_name: Project name
            test_name: Test name
            execution_id: Execution ID
            dom_hash: DOM hash
            
        Returns:
            SemanticPage with complete semantic understanding
        """
        logger.info(f"[SEMANTIC INTEGRATOR] Analyzing page: {url}")
        
        # Step 1: Analyze components
        components = []
        if self.enable_component_analysis and self.component_analyzer:
            components = self.component_analyzer.analyze_dom(dom_elements, dom_content)
            logger.info(f"[SEMANTIC INTEGRATOR] Analyzed {len(components)} components")
        
        # Step 2: Classify page type
        page_type = PageType.UNKNOWN
        page_confidence = 0.0
        page_evidence = []
        
        if self.enable_page_classification and self.page_classifier:
            page_type, page_confidence, page_evidence = self.page_classifier.classify(
                url, title, heading, dom_content, components, text_content
            )
            logger.info(f"[SEMANTIC INTEGRATOR] Page type: {page_type.value} (confidence: {page_confidence:.2f})")
        
        # Step 3: Detect business intent
        business_intent = BusinessIntent(primary_intent=BusinessIntentType.UNKNOWN)
        
        if self.enable_intent_detection and self.intent_detector:
            business_intent = self.intent_detector.detect_intent(
                url, title, heading, components, text_content, page_type
            )
            logger.info(f"[SEMANTIC INTEGRATOR] Business intent: {business_intent.primary_intent.value}")
        
        # Step 4: Analyze navigation
        navigation_context = NavigationContext()
        
        if self.enable_navigation_analysis and self.navigation_analyzer:
            navigation_context = self.navigation_analyzer.analyze_navigation(
                components, dom_content, url
            )
            logger.info(f"[SEMANTIC INTEGRATOR] Navigation type: {navigation_context.navigation_type}")
        
        # Step 5: Priority 22 - Enhance components with universal intelligence
        if self.enable_component_intelligence:
            components = self._enhance_components_with_intelligence(
                components,
                page_type,
                business_intent.primary_intent,
                dom_content,
            )
            logger.info(f"[SEMANTIC INTEGRATOR] Enhanced {len(components)} components with Priority 22 intelligence")
        
        # Step 6: Build semantic page
        semantic_page = self._build_semantic_page(
            url=url,
            title=title,
            heading=heading,
            page_type=page_type,
            components=components,
            business_intent=business_intent,
            navigation_context=navigation_context,
            page_confidence=page_confidence,
            page_evidence=page_evidence,
            project_name=project_name,
            test_name=test_name,
            execution_id=execution_id,
            dom_hash=dom_hash,
        )
        
        # Step 7: Store semantic analysis
        self._store_semantic_page(semantic_page)
        
        logger.info(f"[SEMANTIC INTEGRATOR] Semantic analysis complete: {semantic_page.page_type.value}")
        
        return semantic_page
    
    def _build_semantic_page(
        self,
        url: str,
        title: str,
        heading: str,
        page_type: PageType,
        components: List[SemanticComponent],
        business_intent: BusinessIntent,
        navigation_context: NavigationContext,
        page_confidence: float,
        page_evidence: List[str],
        project_name: str,
        test_name: str,
        execution_id: str,
        dom_hash: str,
    ) -> SemanticPage:
        """Build a complete semantic page object."""
        
        # Extract component categories
        interactive_components = [c for c in components if c.is_interactive]
        form_components = [c for c in components if c.component_type in [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.FILE_UPLOAD,
            ComponentType.CALENDAR,
        ]]
        
        # Extract form fields
        form_fields = [c for c in components if c.component_type in [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.FILE_UPLOAD,
            ComponentType.CALENDAR,
        ]]
        
        # Extract buttons
        submit_buttons = [
            c for c in components
            if c.component_type == ComponentType.BUTTON and
            any(action in c.text_content.lower() for action in ["submit", "save", "login", "sign in"])
        ]
        
        cancel_buttons = [
            c for c in components
            if c.component_type == ComponentType.BUTTON and
            any(action in c.text_content.lower() for action in ["cancel", "close", "back"])
        ]
        
        # Check page characteristics
        has_forms = len(form_components) > 0
        has_tables = any(c.component_type == ComponentType.TABLE for c in components)
        has_charts = "chart" in title.lower() or "chart" in heading.lower()
        has_wizards = any(c.component_type == ComponentType.WIZARD for c in components)
        has_modals = any(c.component_type == ComponentType.MODAL for c in components)
        has_tabs = any(c.component_type == ComponentType.TAB for c in components)
        
        # Extract table information
        tables = self._extract_table_info(components)
        
        # Create semantic page
        semantic_page = SemanticPage(
            url=url,
            page_type=page_type,
            title=title,
            heading=heading,
            components=components,
            interactive_components=interactive_components,
            form_components=form_components,
            business_intent=business_intent,
            navigation_context=navigation_context,
            has_forms=has_forms,
            has_tables=has_tables,
            has_charts=has_charts,
            has_wizards=has_wizards,
            has_modals=has_modals,
            has_tabs=has_tabs,
            form_fields=form_fields,
            submit_buttons=submit_buttons,
            cancel_buttons=cancel_buttons,
            tables=tables,
            confidence=page_confidence,
            dom_hash=dom_hash,
            project_name=project_name,
            test_name=test_name,
            execution_id=execution_id,
            classification_evidence=page_evidence,
        )
        
        return semantic_page
    
    def _extract_table_info(self, components: List[SemanticComponent]) -> List[Dict[str, Any]]:
        """Extract table information from components."""
        tables = []
        
        table_components = [c for c in components if c.component_type == ComponentType.TABLE]
        
        for table in table_components:
            table_info = {
                "element_id": table.element_id,
                "element_class": table.element_class,
                "xpath": table.xpath,
                "css_selector": table.css_selector,
                "row_count": self._estimate_row_count(table),
                "column_count": self._estimate_column_count(table),
            }
            tables.append(table_info)
        
        return tables
    
    def _estimate_row_count(self, table_component: SemanticComponent) -> int:
        """Estimate row count from table component."""
        # This is a simplified estimation
        # In production, this would analyze the actual DOM structure
        return 0
    
    def _estimate_column_count(self, table_component: SemanticComponent) -> int:
        """Estimate column count from table component."""
        # This is a simplified estimation
        # In production, this would analyze the actual DOM structure
        return 0
    
    def _store_semantic_page(self, semantic_page: SemanticPage):
        """Store semantic page analysis."""
        try:
            # Create storage path
            page_dir = self.semantic_storage_dir / semantic_page.project_name / semantic_page.test_name
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # Store semantic page
            semantic_file = page_dir / f"semantic_{semantic_page.execution_id}.json"
            semantic_file.write_text(semantic_page.model_dump_json(indent=2), encoding='utf-8')
            
            # Store latest semantic page
            latest_file = page_dir / "latest_semantic.json"
            latest_file.write_text(semantic_page.model_dump_json(indent=2), encoding='utf-8')
            
            logger.info(f"[SEMANTIC INTEGRATOR] Stored semantic analysis: {semantic_file}")
            
        except Exception as e:
            logger.warning(f"[SEMANTIC INTEGRATOR] Failed to store semantic analysis: {e}")
    
    def load_semantic_page(
        self,
        project_name: str,
        test_name: str,
        execution_id: Optional[str] = None
    ) -> Optional[SemanticPage]:
        """Load semantic page analysis.
        
        Args:
            project_name: Project name
            test_name: Test name
            execution_id: Optional execution ID (loads latest if not provided)
            
        Returns:
            SemanticPage or None if not found
        """
        try:
            page_dir = self.semantic_storage_dir / project_name / test_name
            
            if execution_id:
                semantic_file = page_dir / f"semantic_{execution_id}.json"
            else:
                semantic_file = page_dir / "latest_semantic.json"
            
            if not semantic_file.exists():
                logger.info(f"[SEMANTIC INTEGRATOR] No semantic analysis found: {semantic_file}")
                return None
            
            semantic_data = json.loads(semantic_file.read_text(encoding='utf-8'))
            semantic_page = SemanticPage(**semantic_data)
            
            logger.info(f"[SEMANTIC INTEGRATOR] Loaded semantic analysis: {semantic_file}")
            
            return semantic_page
            
        except Exception as e:
            logger.warning(f"[SEMANTIC INTEGRATOR] Failed to load semantic analysis: {e}")
            return None
    
    def get_semantic_summary(
        self,
        project_name: str,
        test_name: str
    ) -> Dict[str, Any]:
        """Get semantic analysis summary for a project/test.
        
        Args:
            project_name: Project name
            test_name: Test name
            
        Returns:
            Summary dictionary
        """
        try:
            page_dir = self.semantic_storage_dir / project_name / test_name
            
            if not page_dir.exists():
                return {"error": "No semantic analysis found"}
            
            # Load latest semantic page
            semantic_page = self.load_semantic_page(project_name, test_name)
            
            if not semantic_page:
                return {"error": "No semantic analysis found"}
            
            # Build summary
            summary = {
                "url": semantic_page.url,
                "page_type": semantic_page.page_type.value,
                "title": semantic_page.title,
                "heading": semantic_page.heading,
                "business_intent": semantic_page.business_intent.primary_intent.value,
                "navigation_type": semantic_page.navigation_context.navigation_type,
                "component_count": len(semantic_page.components),
                "interactive_component_count": len(semantic_page.interactive_components),
                "form_component_count": len(semantic_page.form_components),
                "confidence": semantic_page.confidence,
                "has_forms": semantic_page.has_forms,
                "has_tables": semantic_page.has_tables,
                "has_charts": semantic_page.has_charts,
                "has_wizards": semantic_page.has_wizards,
                "has_modals": semantic_page.has_modals,
                "has_tabs": semantic_page.has_tabs,
                "timestamp": semantic_page.timestamp,
            }
            
            return summary
            
        except Exception as e:
            logger.warning(f"[SEMANTIC INTEGRATOR] Failed to get semantic summary: {e}")
            return {"error": str(e)}
    
    def integrate_with_dom_snapshot(
        self,
        dom_snapshot: Dict[str, Any],
        semantic_page: SemanticPage
    ) -> Dict[str, Any]:
        """Integrate semantic understanding with DOM snapshot.
        
        Args:
            dom_snapshot: DOM snapshot dictionary
            semantic_page: Semantic page analysis
            
        Returns:
            Enhanced DOM snapshot with semantic metadata
        """
        # Add semantic metadata to DOM snapshot
        enhanced_snapshot = dom_snapshot.copy()
        
        enhanced_snapshot["semantic"] = {
            "page_type": semantic_page.page_type.value,
            "business_intent": semantic_page.business_intent.primary_intent.value,
            "navigation_type": semantic_page.navigation_context.navigation_type,
            "component_count": len(semantic_page.components),
            "confidence": semantic_page.confidence,
            "classification_evidence": semantic_page.classification_evidence,
            "timestamp": semantic_page.timestamp,
        }
        
        return enhanced_snapshot
    
    def integrate_with_locator_repository(
        self,
        semantic_page: SemanticPage,
        locators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Integrate semantic understanding with locator repository.
        
        Args:
            semantic_page: Semantic page analysis
            locators: Locator dictionary
            
        Returns:
            Enhanced locators with semantic component types
        """
        enhanced_locators = locators.copy()
        
        # Add semantic component types to locators
        for component in semantic_page.components:
            if component.element_id in enhanced_locators:
                enhanced_locators[component.element_id]["semantic_type"] = component.component_type.value
                enhanced_locators[component.element_id]["semantic_confidence"] = component.confidence
        
        return enhanced_locators
    
    def get_semantic_context_for_llm(
        self,
        semantic_page: SemanticPage
    ) -> str:
        """Generate semantic context for LLM prompts.
        
        Args:
            semantic_page: Semantic page analysis
            
        Returns:
            Formatted semantic context string
        """
        lines = [
            "## Semantic Page Understanding",
            f"Page Type: {semantic_page.page_type.value}",
            f"Business Intent: {semantic_page.business_intent.primary_intent.value}",
            f"Navigation Type: {semantic_page.navigation_context.navigation_type}",
            f"Confidence: {semantic_page.confidence:.2f}",
            "",
            "## Page Characteristics",
            f"Has Forms: {semantic_page.has_forms}",
            f"Has Tables: {semantic_page.has_tables}",
            f"Has Charts: {semantic_page.has_charts}",
            f"Has Wizards: {semantic_page.has_wizards}",
            f"Has Modals: {semantic_page.has_modals}",
            f"Has Tabs: {semantic_page.has_tabs}",
            "",
            "## Component Summary",
            f"Total Components: {len(semantic_page.components)}",
            f"Interactive Components: {len(semantic_page.interactive_components)}",
            f"Form Components: {len(semantic_page.form_components)}",
            f"Form Fields: {len(semantic_page.form_fields)}",
            "",
            "## Available Actions",
        ]
        
        for action in semantic_page.business_intent.available_actions:
            lines.append(f"- {action}")
        
        lines.append("")
        lines.append("## Data Capabilities")
        lines.append(f"Can Create: {semantic_page.business_intent.can_create}")
        lines.append(f"Can Read: {semantic_page.business_intent.can_read}")
        lines.append(f"Can Update: {semantic_page.business_intent.can_update}")
        lines.append(f"Can Delete: {semantic_page.business_intent.can_delete}")
        lines.append(f"Can Search: {semantic_page.business_intent.can_search}")
        lines.append(f"Can Filter: {semantic_page.business_intent.can_filter}")
        lines.append(f"Can Sort: {semantic_page.business_intent.can_sort}")
        lines.append(f"Can Export: {semantic_page.business_intent.can_export}")
        
        return "\n".join(lines)
    
    def _enhance_components_with_intelligence(
        self,
        components: List[SemanticComponent],
        page_type: PageType,
        business_intent: BusinessIntentType,
        dom_content: str,
    ) -> List[SemanticComponent]:
        """Enhance components with Priority 22 universal component intelligence.
        
        Args:
            components: List of components to enhance
            page_type: Current page type
            business_intent: Current business intent
            dom_content: DOM content for context
            
        Returns:
            Enhanced components with Priority 22 intelligence
        """
        enhanced_components = []
        
        # Step 1: Assign component IDs
        for i, component in enumerate(components):
            if not component.component_id:
                component.component_id = f"comp_{i}_{hash(component.xpath or component.text_content) % 10000}"
        
        # Step 2: Detect component relationships
        relationships = []
        if self.component_relationship_analyzer:
            relationships = self.component_relationship_analyzer.analyze_relationships(
                components,
                {"dom_content": dom_content},
            )
            logger.info(f"[SEMANTIC INTEGRATOR] Detected {len(relationships)} component relationships")
        
        # Step 3: Enhance each component
        for component in components:
            # Find nearby components
            nearby_components = self._find_nearby_components(component, components)
            
            # Infer purpose
            if self.component_purpose_detector:
                purpose = self.component_purpose_detector.infer_purpose(
                    component,
                    nearby_components,
                    page_type,
                    business_intent,
                )
                component.semantic_purpose = purpose.purpose
                component.purpose_confidence = purpose.confidence
                component.purpose_evidence = purpose.evidence
            
            # Build interaction model
            if self.interaction_model_builder:
                interaction_model = self.interaction_model_builder.build_interaction_model(
                    component.component_type,
                    context={
                        "is_password_field": "password" in component.name.lower() or "password" in component.placeholder.lower(),
                        "is_required": component.is_required,
                        "has_validation": bool(component.attributes.get("required") or component.attributes.get("pattern")),
                    },
                )
                component.supported_actions = interaction_model.supported_actions
                component.interaction_confidence = interaction_model.interaction_confidence
            
            # Detect validation rules
            if self.validation_detector and component.component_type in [
                ComponentType.TEXT_FIELD,
                ComponentType.DROPDOWN,
                ComponentType.CHECKBOX,
                ComponentType.RADIO_BUTTON,
            ]:
                validation_rules = self.validation_detector.detect_validation_rules(component)
                component.validation_rules = [rule.dict() for rule in validation_rules]
                component.validation_characteristics = self.validation_detector.detect_validation_characteristics(
                    component, validation_rules
                )
            
            # Generate locator candidates
            if self.locator_intelligence:
                locator_candidates = self.locator_intelligence.generate_locator_candidates(component)
                component.locator_candidates = [candidate.dict() for candidate in locator_candidates]
                
                # Select best locator
                best_locator = self.locator_intelligence.select_best_locator(locator_candidates)
                if best_locator:
                    component.selected_locator = best_locator.locator
                    component.locator_confidence = best_locator.confidence
            
            # Add context
            component.page_type = page_type.value
            component.business_intent = business_intent.value
            
            # Add relationship information
            component_relationships = [r for r in relationships if r.source_component_id == component.component_id]
            if component_relationships:
                component.relationship_type = component_relationships[0].relationship_type
            
            enhanced_components.append(component)
        
        return enhanced_components
    
    def _find_nearby_components(
        self,
        component: SemanticComponent,
        all_components: List[SemanticComponent],
        max_count: int = 5,
    ) -> List[SemanticComponent]:
        """Find nearby components for context."""
        # Simple implementation: return components close in the list
        # In a real implementation, this would use spatial/position information
        try:
            index = all_components.index(component)
        except ValueError:
            return []
        
        start = max(0, index - max_count // 2)
        end = min(len(all_components), index + max_count // 2 + 1)
        
        nearby = all_components[start:end]
        nearby = [c for c in nearby if c.component_id != component.component_id]
        
        return nearby
