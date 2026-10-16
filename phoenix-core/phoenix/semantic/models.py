"""Semantic Models - Universal Application Understanding Data Models.

This module defines all data models for semantic page classification,
UI component analysis, business intent detection, and navigation analysis.
These models are completely generic and work for ANY web application.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Page Types - Generic, Application-Agnostic
# ---------------------------------------------------------------------------

class PageType(str, Enum):
    """Generic page types that work for ANY web application."""
    
    AUTHENTICATION_SCREEN = "authentication_screen"
    DASHBOARD = "dashboard"
    CRUD_FORM = "crud_form"
    SEARCH_SCREEN = "search_screen"
    TABLE_VIEW = "table_view"
    REPORT_SCREEN = "report_screen"
    WIZARD = "wizard"
    FILE_UPLOAD = "file_upload"
    CALENDAR = "calendar"
    MODAL = "modal"
    NAVIGATION_MENU = "navigation_menu"
    SETTINGS = "settings"
    PROFILE = "profile"
    WORKFLOW_SCREEN = "workflow_screen"
    APPROVAL_SCREEN = "approval_screen"
    ANALYTICS = "analytics"
    LANDING_PAGE = "landing_page"
    ERROR_PAGE = "error_page"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Component Types - Generic UI Components
# ---------------------------------------------------------------------------

class ComponentType(str, Enum):
    """Generic UI component types that work for ANY web application."""
    
    TEXT_FIELD = "text_field"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    BUTTON = "button"
    LINK = "link"
    TABLE = "table"
    CARD = "card"
    MODAL = "modal"
    WIZARD = "wizard"
    CALENDAR = "calendar"
    FILE_UPLOAD = "file_upload"
    TREE = "tree"
    GRID = "grid"
    MENU = "menu"
    TOAST = "toast"
    ALERT = "alert"
    TAB = "tab"
    ACCORDION = "accordion"
    PROGRESS_BAR = "progress_bar"
    STEPPER = "stepper"
    BREADCRUMB = "breadcrumb"
    PAGINATION = "pagination"
    SIDEBAR = "sidebar"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Business Intent Types - Generic Business Intents
# ---------------------------------------------------------------------------

class BusinessIntentType(str, Enum):
    """Generic business intent types that work for ANY web application."""
    
    AUTHENTICATION = "authentication"
    DATA_ENTRY = "data_entry"
    DATA_RETRIEVAL = "data_retrieval"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    NAVIGATION = "navigation"
    REPORTING = "reporting"
    APPROVAL = "approval"
    CONFIGURATION = "configuration"
    FILE_MANAGEMENT = "file_management"
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"
    EXPORT = "export"
    IMPORT = "import"
    WORKFLOW_TRANSITION = "workflow_transition"
    NOTIFICATION = "notification"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Semantic Component Model
# ---------------------------------------------------------------------------

class SemanticComponent(BaseModel):
    """Represents a UI component with universal component intelligence (Priority 22)."""
    
    # Basic identification
    component_id: str = Field(default="", description="Unique component identifier")
    component_type: ComponentType = Field(..., description="Generic component type")
    element_id: str = Field(default="", description="DOM element ID")
    element_class: str = Field(default="", description="DOM element class")
    xpath: str = Field(default="", description="XPath to element")
    css_selector: str = Field(default="", description="CSS selector")
    text_content: str = Field(default="", description="Visible text content")
    label: str = Field(default="", description="Associated label")
    placeholder: str = Field(default="", description="Placeholder text")
    name: str = Field(default="", description="Name attribute")
    aria_role: str = Field(default="", description="ARIA role")
    aria_label: str = Field(default="", description="ARIA label")
    
    # Semantic understanding (Priority 22)
    semantic_role: str = Field(default="", description="Deeper semantic role")
    semantic_purpose: str = Field(default="", description="Inferred semantic purpose")
    purpose_confidence: float = Field(default=0.0, description="Purpose inference confidence")
    purpose_evidence: List[str] = Field(default_factory=list, description="Evidence for purpose")
    
    # Context
    page_type: str = Field(default="", description="Page type context")
    business_intent: str = Field(default="", description="Business intent context")
    
    # Component relationships (Priority 22)
    parent_component_id: str = Field(default="", description="Parent component ID")
    child_component_ids: List[str] = Field(default_factory=list, description="Child component IDs")
    nearby_component_ids: List[str] = Field(default_factory=list, description="Nearby component IDs")
    relationship_type: str = Field(default="", description="Relationship type (form_member, table_cell, etc.)")
    
    # Properties
    confidence: float = Field(default=0.0, description="Classification confidence")
    is_interactive: bool = Field(default=False, description="Is component interactive")
    is_required: bool = Field(default=False, description="Is component required")
    is_disabled: bool = Field(default=False, description="Is component disabled")
    is_visible: bool = Field(default=True, description="Is component visible")
    
    # Position and layout
    position: Dict[str, Any] = Field(default_factory=dict, description="Position information")
    layout_info: Dict[str, Any] = Field(default_factory=dict, description="Layout information")
    
    # Attributes
    attributes: Dict[str, str] = Field(default_factory=dict, description="All DOM attributes")
    
    # Interaction intelligence (Priority 22)
    supported_actions: List[str] = Field(default_factory=list, description="Supported actions")
    interaction_confidence: float = Field(default=0.0, description="Interaction confidence")
    
    # Validation intelligence (Priority 22)
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list, description="Validation rules")
    validation_characteristics: Dict[str, Any] = Field(default_factory=dict, description="Validation characteristics")
    
    # Locator intelligence (Priority 22)
    locator_candidates: List[Dict[str, Any]] = Field(default_factory=list, description="Locator candidates with confidence")
    selected_locator: str = Field(default="", description="Selected locator")
    locator_confidence: float = Field(default=0.0, description="Locator confidence")
    
    # Runtime learning (Priority 22)
    runtime_observations: List[Dict[str, Any]] = Field(default_factory=list, description="Runtime observations")
    success_count: int = Field(default=0, description="Successful interaction count")
    failure_count: int = Field(default=0, description="Failed interaction count")
    first_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="First seen timestamp")
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Last seen timestamp")
    learned_behavior: Dict[str, Any] = Field(default_factory=dict, description="Learned behavior patterns")
    
    # Metadata
    detection_method: str = Field(default="", description="How component was detected")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Priority 22: Component Intelligence Models
# ---------------------------------------------------------------------------

class ComponentPurpose(BaseModel):
    """Represents the inferred purpose of a component (Priority 22)."""
    
    purpose: str = Field(..., description="Inferred purpose (e.g., form_submit, search_trigger)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Purpose confidence")
    evidence: List[str] = Field(default_factory=list, description="Evidence for purpose inference")
    
    # Context
    page_type: str = Field(default="", description="Page type context")
    nearby_components: List[str] = Field(default_factory=list, description="Nearby component types")
    form_context: bool = Field(default=False, description="Is part of a form")
    business_intent: str = Field(default="", description="Business intent context")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ComponentRelationship(BaseModel):
    """Represents relationships between components (Priority 22)."""
    
    relationship_type: str = Field(..., description="Relationship type (parent_child, form_member, table_cell, etc.)")
    source_component_id: str = Field(..., description="Source component ID")
    target_component_id: str = Field(..., description="Target component ID")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Relationship confidence")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for relationship")
    dom_distance: int = Field(default=0, description="DOM distance between components")
    visual_distance: Dict[str, Any] = Field(default_factory=dict, description="Visual distance")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InteractionModel(BaseModel):
    """Represents how a component can be interacted with (Priority 22)."""
    
    component_type: ComponentType = Field(..., description="Component type")
    supported_actions: List[str] = Field(default_factory=list, description="Supported actions")
    action_parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for each action")
    
    # Expected behavior
    expected_outcomes: List[str] = Field(default_factory=list, description="Expected outcomes")
    side_effects: List[str] = Field(default_factory=list, description="Potential side effects")
    
    # Interaction confidence
    interaction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Interaction confidence")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ValidationRule(BaseModel):
    """Represents a validation rule for a component (Priority 22)."""
    
    field: str = Field(..., description="Field this rule applies to")
    validation_type: str = Field(..., description="Validation type (required, format, length, etc.)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Validation confidence")
    
    # Rule details
    rule_value: Any = Field(default=None, description="Rule value (e.g., min_length: 5)")
    error_message: str = Field(default="", description="Observed error message")
    trigger_condition: str = Field(default="", description="Condition that triggers validation")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for validation rule")
    observation_count: int = Field(default=0, description="Number of times observed")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LocatorCandidate(BaseModel):
    """Represents a candidate locator strategy (Priority 22)."""
    
    strategy: str = Field(..., description="Locator strategy (role, text, test_id, etc.)")
    locator: str = Field(..., description="Playwright locator string")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Locator confidence")
    stability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Stability score")
    uniqueness_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Uniqueness score")
    
    # Statistics
    success_count: int = Field(default=0, description="Success count")
    failure_count: int = Field(default=0, description="Failure count")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for this locator")
    generation_method: str = Field(default="", description="How this locator was generated")
    
    # Metadata
    last_used: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Navigation Context Model
# ---------------------------------------------------------------------------

class NavigationContext(BaseModel):
    """Represents navigation structure and context."""
    
    has_navigation_menu: bool = Field(default=False, description="Has navigation menu")
    has_breadcrumbs: bool = Field(default=False, description="Has breadcrumbs")
    has_tabs: bool = Field(default=False, description="Has tabs")
    has_sidebar: bool = Field(default=False, description="Has sidebar")
    has_header: bool = Field(default=False, description="Has header")
    has_footer: bool = Field(default=False, description="Has footer")
    
    navigation_type: str = Field(default="", description="Navigation type")
    active_menu_item: str = Field(default="", description="Active menu item")
    breadcrumb_trail: List[str] = Field(default_factory=list, description="Breadcrumb trail")
    
    # Navigation links
    navigation_links: List[Dict[str, str]] = Field(default_factory=list, description="Navigation links")
    
    # Navigation hierarchy
    menu_hierarchy: Dict[str, Any] = Field(default_factory=dict, description="Menu hierarchy")
    
    # Navigation actions
    back_available: bool = Field(default=False, description="Back navigation available")
    forward_available: bool = Field(default=False, description="Forward navigation available")
    
    # Metadata
    confidence: float = Field(default=0.0, description="Classification confidence")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Business Intent Model
# ---------------------------------------------------------------------------

class BusinessIntent(BaseModel):
    """Represents the business intent of a page."""
    
    primary_intent: BusinessIntentType = Field(default=BusinessIntentType.UNKNOWN, description="Primary business intent")
    secondary_intents: List[BusinessIntentType] = Field(default_factory=list, description="Secondary intents")
    
    # Intent evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for intent classification")
    
    # Action availability
    available_actions: List[str] = Field(default_factory=list, description="Available actions")
    primary_action: str = Field(default="", description="Primary action")
    
    # Data operations
    can_create: bool = Field(default=False, description="Can create data")
    can_read: bool = Field(default=False, description="Can read data")
    can_update: bool = Field(default=False, description="Can update data")
    can_delete: bool = Field(default=False, description="Can delete data")
    can_search: bool = Field(default=False, description="Can search data")
    can_filter: bool = Field(default=False, description="Can filter data")
    can_sort: bool = Field(default=False, description="Can sort data")
    can_export: bool = Field(default=False, description="Can export data")
    
    # Metadata
    confidence: float = Field(default=0.0, description="Classification confidence")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Semantic Page Model
# ---------------------------------------------------------------------------

class SemanticPage(BaseModel):
    """Represents a page with complete semantic understanding."""
    
    # Page identification
    url: str = Field(..., description="Page URL")
    page_type: PageType = Field(..., description="Semantic page type")
    title: str = Field(default="", description="Page title")
    heading: str = Field(default="", description="Main heading")
    
    # Components
    components: List[SemanticComponent] = Field(default_factory=list, description="UI components")
    interactive_components: List[SemanticComponent] = Field(default_factory=list, description="Interactive components")
    form_components: List[SemanticComponent] = Field(default_factory=list, description="Form components")
    
    # Business intent
    business_intent: BusinessIntent = Field(default_factory=BusinessIntent, description="Business intent")
    
    # Navigation
    navigation_context: NavigationContext = Field(default_factory=NavigationContext, description="Navigation context")
    
    # Page characteristics
    has_forms: bool = Field(default=False, description="Has forms")
    has_tables: bool = Field(default=False, description="Has tables")
    has_charts: bool = Field(default=False, description="Has charts")
    has_wizards: bool = Field(default=False, description="Has wizards")
    has_modals: bool = Field(default=False, description="Has modals")
    has_tabs: bool = Field(default=False, description="Has tabs")
    
    # Form analysis
    form_fields: List[SemanticComponent] = Field(default_factory=list, description="Form fields")
    submit_buttons: List[SemanticComponent] = Field(default_factory=list, description="Submit buttons")
    cancel_buttons: List[SemanticComponent] = Field(default_factory=list, description="Cancel buttons")
    
    # Table analysis
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="Table information")
    
    # Classification confidence
    confidence: float = Field(default=0.0, description="Overall classification confidence")
    
    # DOM reference
    dom_hash: str = Field(default="", description="DOM hash for reference")
    dom_snapshot_id: str = Field(default="", description="DOM snapshot ID")
    
    # Metadata
    project_name: str = Field(default="", description="Project name")
    test_name: str = Field(default="", description="Test name")
    execution_id: str = Field(default="", description="Execution ID")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Classification evidence
    classification_evidence: List[str] = Field(default_factory=list, description="Evidence for classification")
    
    def get_components_by_type(self, component_type: ComponentType) -> List[SemanticComponent]:
        """Get all components of a specific type."""
        return [c for c in self.components if c.component_type == component_type]
    
    def get_interactive_components(self) -> List[SemanticComponent]:
        """Get all interactive components."""
        return [c for c in self.components if c.is_interactive]
    
    def get_form_components(self) -> List[SemanticComponent]:
        """Get all form components."""
        return [c for c in self.components if c.component_type in [
            ComponentType.TEXT_FIELD,
            ComponentType.DROPDOWN,
            ComponentType.CHECKBOX,
            ComponentType.RADIO_BUTTON,
            ComponentType.FILE_UPLOAD,
            ComponentType.CALENDAR,
        ]]
    
    def get_primary_action_component(self) -> Optional[SemanticComponent]:
        """Get the primary action component (submit button, etc.)."""
        if self.business_intent.primary_action:
            for component in self.components:
                if component.text_content.lower() == self.business_intent.primary_action.lower():
                    return component
        return None
    
    def to_summary(self) -> str:
        """Generate a human-readable summary of the semantic page."""
        lines = [
            f"Page Type: {self.page_type.value}",
            f"URL: {self.url}",
            f"Title: {self.title}",
            f"Heading: {self.heading}",
            f"Business Intent: {self.business_intent.primary_intent.value}",
            f"Components: {len(self.components)}",
            f"Interactive Components: {len(self.interactive_components)}",
            f"Form Components: {len(self.form_components)}",
            f"Confidence: {self.confidence:.2f}",
        ]
        return "\n".join(lines)
