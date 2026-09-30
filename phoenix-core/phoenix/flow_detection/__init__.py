"""Flow Detection Module - AI Business Flow Discovery (Priority 21).

This module provides generic, application-agnostic business flow discovery
that builds on Priority 20 Semantic Understanding to discover and understand
complete workflows across ANY web application.

Phoenix should never hardcode application-specific flows (OrangeHRM, Jira, etc.).
Instead, it must discover flows semantically using reusable concepts.
"""

from __future__ import annotations

from phoenix.flow_detection.models import (
    FlowNode,
    FlowEdge,
    BusinessFlow,
    FlowGraph,
    ActionType,
    FlowType,
    PageTransition,
    SemanticAction,
)
from phoenix.flow_detection.transition_tracker import PageTransitionTracker
from phoenix.flow_detection.flow_graph_builder import FlowGraphBuilder
from phoenix.flow_detection.flow_reasoning import FlowReasoningEngine
from phoenix.flow_detection.flow_discovery import FlowDiscoveryEngine
from phoenix.flow_detection.flow_persistence import FlowPersistenceManager

__all__ = [
    "FlowNode",
    "FlowEdge",
    "BusinessFlow",
    "FlowGraph",
    "ActionType",
    "FlowType",
    "PageTransition",
    "SemanticAction",
    "PageTransitionTracker",
    "FlowGraphBuilder",
    "FlowReasoningEngine",
    "FlowDiscoveryEngine",
    "FlowPersistenceManager",
]
