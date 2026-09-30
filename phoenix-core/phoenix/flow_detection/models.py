"""Flow Detection Models - Generic Business Flow Data Structures.

This module defines all data models for business flow discovery.
These models are completely generic and work for ANY web application.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generic Action Types - Application-Agnostic
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """Generic action types that work for ANY web application."""
    
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SUBMIT = "submit"
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    CREATE = "create"
    EDIT = "edit"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    CANCEL = "cancel"
    CONFIRM = "confirm"
    RETRY = "retry"
    BACK = "back"
    NEXT = "next"
    TAB_CHANGE = "tab_change"
    MODAL_OPEN = "modal_open"
    MODAL_CLOSE = "modal_close"
    VALIDATE = "validate"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Generic Flow Types - Application-Agnostic
# ---------------------------------------------------------------------------

class FlowType(str, Enum):
    """Generic business flow types that work for ANY web application."""
    
    AUTHENTICATION = "authentication"
    SEARCH_FLOW = "search_flow"
    CRUD_CREATE = "crud_create"
    CRUD_READ = "crud_read"
    CRUD_UPDATE = "crud_update"
    CRUD_DELETE = "crud_delete"
    FILE_UPLOAD_FLOW = "file_upload_flow"
    DATA_ENTRY = "data_entry"
    NAVIGATION_FLOW = "navigation_flow"
    APPROVAL_FLOW = "approval_flow"
    VALIDATION_FLOW = "validation_flow"
    RECOVERY_FLOW = "recovery_flow"
    MULTI_STEP_FORM = "multi_step_form"
    REPORTING_FLOW = "reporting_flow"
    EXPORT_FLOW = "export_flow"
    IMPORT_FLOW = "import_flow"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Semantic Action Model
# ---------------------------------------------------------------------------

class SemanticAction(BaseModel):
    """Represents a semantically understood user action."""
    
    action_type: ActionType = Field(..., description="Generic action type")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Classification confidence")
    
    # Action context
    element_role: str = Field(default="", description="ARIA role of element")
    element_text: str = Field(default="", description="Visible text content")
    element_label: str = Field(default="", description="Associated label")
    element_xpath: str = Field(default="", description="XPath to element")
    
    # Page context
    page_type: str = Field(default="", description="Semantic page type")
    page_url: str = Field(default="", description="Page URL")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for action classification")
    detection_method: str = Field(default="", description="How action was detected")
    
    # Timestamp
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Page Transition Model
# ---------------------------------------------------------------------------

class PageTransition(BaseModel):
    """Represents a transition between semantic pages."""
    
    # Source page
    source_page_type: str = Field(..., description="Semantic type of source page")
    source_url: str = Field(default="", description="URL of source page")
    source_dom_hash: str = Field(default="", description="DOM hash of source page")
    
    # Target page
    target_page_type: str = Field(..., description="Semantic type of target page")
    target_url: str = Field(default="", description="URL of target page")
    target_dom_hash: str = Field(default="", description="DOM hash of target page")
    
    # Action that caused transition
    action: SemanticAction = Field(..., description="Action that caused transition")
    
    # Transition metadata
    transition_type: str = Field(default="", description="Type of transition")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Transition confidence")
    
    # Execution context
    execution_id: str = Field(default="", description="Execution ID")
    test_id: str = Field(default="", description="Test ID")
    project_name: str = Field(default="", description="Project name")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for transition")
    dom_change_detected: bool = Field(default=False, description="Whether DOM change was detected")
    
    # Timestamp
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Flow Node Model
# ---------------------------------------------------------------------------

class FlowNode(BaseModel):
    """Represents a node in a business flow graph."""
    
    node_id: str = Field(..., description="Unique node identifier")
    semantic_type: str = Field(..., description="Semantic page type")
    url_pattern: str = Field(default="", description="URL pattern (optional)")
    
    # Node statistics
    visit_count: int = Field(default=0, description="Number of times visited")
    success_count: int = Field(default=0, description="Number of successful transitions")
    failure_count: int = Field(default=0, description="Number of failed transitions")
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Node confidence")
    
    # Metadata
    first_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Flow Edge Model
# ---------------------------------------------------------------------------

class FlowEdge(BaseModel):
    """Represents an edge in a business flow graph."""
    
    edge_id: str = Field(..., description="Unique edge identifier")
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")
    
    # Action
    action: SemanticAction = Field(..., description="Action that causes this transition")
    
    # Edge statistics
    frequency: int = Field(default=0, description="Number of times this edge was traversed")
    success_count: int = Field(default=0, description="Number of successful traversals")
    failure_count: int = Field(default=0, description="Number of failed traversals")
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Edge confidence")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Success rate")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for this edge")
    
    # Metadata
    first_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Business Flow Model
# ---------------------------------------------------------------------------

class BusinessFlow(BaseModel):
    """Represents a discovered business flow."""
    
    flow_id: str = Field(..., description="Unique flow identifier")
    flow_type: FlowType = Field(..., description="Generic flow type")
    flow_name: str = Field(default="", description="Human-readable flow name")
    
    # Flow structure
    nodes: List[FlowNode] = Field(default_factory=list, description="Flow nodes")
    edges: List[FlowEdge] = Field(default_factory=list, description="Flow edges")
    
    # Flow statistics
    total_observations: int = Field(default=0, description="Total times flow was observed")
    success_count: int = Field(default=0, description="Number of successful completions")
    failure_count: int = Field(default=0, description="Number of failed completions")
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Flow confidence")
    completeness: float = Field(default=0.0, ge=0.0, le=1.0, description="Flow completeness")
    
    # Classification
    is_happy_path: bool = Field(default=False, description="Is this a happy path flow")
    is_recovery_path: bool = Field(default=False, description="Is this a recovery path")
    is_validation_path: bool = Field(default=False, description="Is this a validation path")
    
    # Application context
    project_name: str = Field(default="", description="Project name")
    application_domain: str = Field(default="", description="Application domain (inferred)")
    
    # Evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence for flow classification")
    
    # Metadata
    first_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Flow Graph Model
# ---------------------------------------------------------------------------

class FlowGraph(BaseModel):
    """Represents a complete flow graph with multiple business flows."""
    
    graph_id: str = Field(..., description="Unique graph identifier")
    project_name: str = Field(default="", description="Project name")
    
    # All nodes and edges
    nodes: List[FlowNode] = Field(default_factory=list, description="All nodes in graph")
    edges: List[FlowEdge] = Field(default_factory=list, description="All edges in graph")
    
    # Discovered flows
    flows: List[BusinessFlow] = Field(default_factory=list, description="Discovered business flows")
    
    # Graph statistics
    total_nodes: int = Field(default=0, description="Total nodes")
    total_edges: int = Field(default=0, description="Total edges")
    total_flows: int = Field(default=0, description="Total flows")
    
    # Graph metadata
    first_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_node(self, node: FlowNode) -> None:
        """Add a node to the graph."""
        # Check if node already exists
        existing = next((n for n in self.nodes if n.node_id == node.node_id), None)
        if existing:
            # Update existing node
            existing.visit_count += node.visit_count
            existing.success_count += node.success_count
            existing.failure_count += node.failure_count
            existing.confidence = max(existing.confidence, node.confidence)
            existing.last_observed = node.last_observed
        else:
            self.nodes.append(node)
        self.total_nodes = len(self.nodes)
    
    def add_edge(self, edge: FlowEdge) -> None:
        """Add an edge to the graph."""
        # Check if edge already exists
        existing = next((e for e in self.edges if e.edge_id == edge.edge_id), None)
        if existing:
            # Update existing edge
            existing.frequency += edge.frequency
            existing.success_count += edge.success_count
            existing.failure_count += edge.failure_count
            existing.confidence = max(existing.confidence, edge.confidence)
            existing.success_rate = existing.success_count / max(1, existing.frequency)
            existing.last_observed = edge.last_observed
        else:
            self.edges.append(edge)
        self.total_edges = len(self.edges)
    
    def add_flow(self, flow: BusinessFlow) -> None:
        """Add a business flow to the graph."""
        # Check if flow already exists
        existing = next((f for f in self.flows if f.flow_id == flow.flow_id), None)
        if existing:
            # Update existing flow
            existing.total_observations += flow.total_observations
            existing.success_count += flow.success_count
            existing.failure_count += flow.failure_count
            existing.confidence = max(existing.confidence, flow.confidence)
            existing.completeness = max(existing.completeness, flow.completeness)
            existing.last_observed = flow.last_observed
        else:
            self.flows.append(flow)
        self.total_flows = len(self.flows)
