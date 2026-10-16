"""Flow Reasoning Engine - AI-Enhanced Business Flow Recognition.

This module uses AI reasoning to enhance business flow discovery,
inferring flow types, completeness, and business patterns from
observed semantic evidence.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowGraph,
    FlowType,
    FlowNode,
    FlowEdge,
    SemanticAction,
    ActionType,
)

logger = logging.getLogger(__name__)


class FlowReasoningEngine:
    """AI-enhanced flow reasoning engine.
    
    This engine:
    - Analyzes flow graphs to infer business flow types
    - Determines flow completeness and happiness
    - Identifies recovery and validation paths
    - Provides AI-powered flow classification
    - Integrates with existing LLM infrastructure
    """
    
    def __init__(
        self,
        enable_ai_reasoning: bool = True,
        ai_confidence_threshold: float = 0.7,
    ):
        """Initialize the flow reasoning engine.
        
        Args:
            enable_ai_reasoning: Enable AI-powered reasoning
            ai_confidence_threshold: Minimum confidence for AI classifications
        """
        self.enable_ai_reasoning = enable_ai_reasoning
        self.ai_confidence_threshold = ai_confidence_threshold
        
        logger.info(f"[FLOW REASONING] Initialized with AI reasoning: {enable_ai_reasoning}")
        logger.info(f"[FLOW REASONING] AI confidence threshold: {ai_confidence_threshold}")
    
    def analyze_flow_graph(
        self,
        flow_graph: FlowGraph,
    ) -> List[BusinessFlow]:
        """Analyze a flow graph and extract business flows.
        
        Args:
            flow_graph: Flow graph to analyze
            
        Returns:
            List of discovered business flows
        """
        logger.info(f"[FLOW REASONING] Analyzing flow graph: {flow_graph.graph_id}")
        
        discovered_flows = []
        
        # Extract potential flows from graph structure
        potential_flows = self._extract_potential_flows(flow_graph)
        
        # Analyze each potential flow
        for potential_flow in potential_flows:
            flow = self._analyze_potential_flow(potential_flow, flow_graph)
            if flow:
                discovered_flows.append(flow)
        
        logger.info(f"[FLOW REASONING] Discovered {len(discovered_flows)} business flows")
        
        return discovered_flows
    
    def _extract_potential_flows(
        self,
        flow_graph: FlowGraph,
    ) -> List[Dict[str, Any]]:
        """Extract potential flows from graph structure.
        
        Args:
            flow_graph: Flow graph
            
        Returns:
            List of potential flow structures
        """
        potential_flows = []
        
        # Find linear paths (potential flows)
        linear_paths = self._find_linear_paths(flow_graph)
        
        for path in linear_paths:
            potential_flows.append({
                "type": "linear",
                "nodes": path,
                "edges": self._get_edges_for_path(flow_graph, path),
            })
        
        # Find branching structures
        branching_structures = self._find_branching_structures(flow_graph)
        
        for structure in branching_structures:
            potential_flows.append({
                "type": "branching",
                "root": structure["root"],
                "branches": structure["branches"],
            })
        
        return potential_flows
    
    def _find_linear_paths(self, flow_graph: FlowGraph) -> List[List[FlowNode]]:
        """Find linear paths in the flow graph.
        
        Args:
            flow_graph: Flow graph
            
        Returns:
            List of linear paths (each path is a list of nodes)
        """
        paths = []
        
        # Build adjacency
        outgoing: Dict[str, List[FlowNode]] = {}
        for node in flow_graph.nodes:
            outgoing[node.node_id] = []
        
        for edge in flow_graph.edges:
            source_node = next((n for n in flow_graph.nodes if n.node_id == edge.source_node_id), None)
            target_node = next((n for n in flow_graph.nodes if n.node_id == edge.target_node_id), None)
            if source_node and target_node:
                outgoing[source_node.node_id].append(target_node)
        
        # Find paths starting from nodes with no incoming edges
        incoming_count: Dict[str, int] = {node.node_id: 0 for node in flow_graph.nodes}
        for edge in flow_graph.edges:
            incoming_count[edge.target_node_id] += 1
        
        start_nodes = [node for node in flow_graph.nodes if incoming_count[node.node_id] == 0]
        
        for start_node in start_nodes:
            path = [start_node]
            current = start_node
            
            # Follow the path
            while current.node_id in outgoing and len(outgoing[current.node_id]) == 1:
                next_node = outgoing[current.node_id][0]
                path.append(next_node)
                current = next_node
            
            if len(path) > 1:
                paths.append(path)
        
        return paths
    
    def _find_branching_structures(self, flow_graph: FlowGraph) -> List[Dict[str, Any]]:
        """Find branching structures in the flow graph.
        
        Args:
            flow_graph: Flow graph
            
        Returns:
            List of branching structures
        """
        structures = []
        
        # Build adjacency
        outgoing: Dict[str, List[FlowNode]] = {}
        for node in flow_graph.nodes:
            outgoing[node.node_id] = []
        
        for edge in flow_graph.edges:
            source_node = next((n for n in flow_graph.nodes if n.node_id == edge.source_node_id), None)
            target_node = next((n for n in flow_graph.nodes if n.node_id == edge.target_node_id), None)
            if source_node and target_node:
                outgoing[source_node.node_id].append(target_node)
        
        # Find nodes with multiple outgoing edges
        for node in flow_graph.nodes:
            if node.node_id in outgoing and len(outgoing[node.node_id]) > 1:
                structures.append({
                    "root": node,
                    "branches": outgoing[node.node_id],
                })
        
        return structures
    
    def _get_edges_for_path(
        self,
        flow_graph: FlowGraph,
        path: List[FlowNode],
    ) -> List[FlowEdge]:
        """Get edges that connect nodes in a path.
        
        Args:
            flow_graph: Flow graph
            path: List of nodes in path
            
        Returns:
            List of edges connecting the nodes
        """
        edges = []
        
        for i in range(len(path) - 1):
            source_id = path[i].node_id
            target_id = path[i + 1].node_id
            
            edge = next(
                (e for e in flow_graph.edges 
                 if e.source_node_id == source_id and e.target_node_id == target_id),
                None
            )
            if edge:
                edges.append(edge)
        
        return edges
    
    def _analyze_potential_flow(
        self,
        potential_flow: Dict[str, Any],
        flow_graph: FlowGraph,
    ) -> Optional[BusinessFlow]:
        """Analyze a potential flow and classify it.
        
        Args:
            potential_flow: Potential flow structure
            flow_graph: Parent flow graph
            
        Returns:
            Classified business flow or None
        """
        if potential_flow["type"] == "linear":
            return self._analyze_linear_flow(potential_flow, flow_graph)
        elif potential_flow["type"] == "branching":
            return self._analyze_branching_flow(potential_flow, flow_graph)
        
        return None
    
    def _analyze_linear_flow(
        self,
        potential_flow: Dict[str, Any],
        flow_graph: FlowGraph,
    ) -> Optional[BusinessFlow]:
        """Analyze a linear flow.
        
        Args:
            potential_flow: Linear flow structure
            flow_graph: Parent flow graph
            
        Returns:
            Classified business flow
        """
        nodes = potential_flow["nodes"]
        edges = potential_flow["edges"]
        
        if len(nodes) < 2:
            return None
        
        # Extract semantic types
        semantic_types = [node.semantic_type for node in nodes]
        action_types = [edge.action.action_type for edge in edges]
        
        # Classify flow type based on semantic pattern
        flow_type, confidence = self._classify_flow_pattern(semantic_types, action_types)
        
        # Determine if this is a happy path
        is_happy_path = self._is_happy_path(semantic_types, action_types)
        
        # Determine if this is a recovery path
        is_recovery_path = self._is_recovery_path(semantic_types, action_types)
        
        # Determine if this is a validation path
        is_validation_path = self._is_validation_path(semantic_types, action_types)
        
        # Calculate completeness
        completeness = self._calculate_flow_completeness(nodes, edges)
        
        # Create business flow
        import uuid
        flow = BusinessFlow(
            flow_id=f"flow_{uuid.uuid4().hex[:8]}",
            flow_type=flow_type,
            flow_name=self._generate_flow_name(flow_type, semantic_types),
            nodes=nodes,
            edges=edges,
            confidence=confidence,
            completeness=completeness,
            is_happy_path=is_happy_path,
            is_recovery_path=is_recovery_path,
            is_validation_path=is_validation_path,
            project_name=flow_graph.project_name,
            evidence=[f"Pattern: {' -> '.join(semantic_types)}"],
        )
        
        # Calculate statistics
        flow.total_observations = sum(node.visit_count for node in nodes)
        flow.success_count = sum(node.success_count for node in nodes)
        flow.failure_count = sum(node.failure_count for node in nodes)
        
        return flow
    
    def _analyze_branching_flow(
        self,
        potential_flow: Dict[str, Any],
        flow_graph: FlowGraph,
    ) -> Optional[BusinessFlow]:
        """Analyze a branching flow.
        
        Args:
            potential_flow: Branching flow structure
            flow_graph: Parent flow graph
            
        Returns:
            Classified business flow
        """
        # For now, treat branching flows as complex navigation flows
        root = potential_flow["root"]
        branches = potential_flow["branches"]
        
        import uuid
        flow = BusinessFlow(
            flow_id=f"flow_{uuid.uuid4().hex[:8]}",
            flow_type=FlowType.NAVIGATION_FLOW,
            flow_name=f"Navigation from {root.semantic_type}",
            nodes=[root] + branches,
            edges=[],
            confidence=0.6,
            completeness=0.5,
            is_happy_path=False,
            project_name=flow_graph.project_name,
            evidence=[f"Branching structure with {len(branches)} branches"],
        )
        
        return flow
    
    def _classify_flow_pattern(
        self,
        semantic_types: List[str],
        action_types: List[ActionType],
    ) -> tuple[FlowType, float]:
        """Classify flow pattern based on semantic types and actions.
        
        Args:
            semantic_types: List of semantic page types
            action_types: List of action types
            
        Returns:
            Tuple of (flow_type, confidence)
        """
        # Generic pattern matching (application-agnostic)
        
        # Authentication flow
        if (semantic_types[0] == "authentication_screen" and 
            "dashboard" in semantic_types and
            ActionType.SUBMIT in action_types):
            return FlowType.AUTHENTICATION, 0.9
        
        # Search flow
        if (semantic_types[0] == "search_screen" and 
            "table_view" in semantic_types and
            ActionType.SEARCH in action_types):
            return FlowType.SEARCH_FLOW, 0.85
        
        # CRUD Create flow
        if (semantic_types[0] in ["table_view", "dashboard"] and
            "crud_form" in semantic_types and
            ActionType.CREATE in action_types and
            ActionType.SUBMIT in action_types):
            return FlowType.CRUD_CREATE, 0.88
        
        # CRUD Update flow
        if (semantic_types[0] == "table_view" and
            "crud_form" in semantic_types and
            ActionType.EDIT in action_types and
            ActionType.SUBMIT in action_types):
            return FlowType.CRUD_UPDATE, 0.87
        
        # CRUD Delete flow
        if (semantic_types[0] == "table_view" and
            ActionType.DELETE in action_types and
            ActionType.CONFIRM in action_types):
            return FlowType.CRUD_DELETE, 0.86
        
        # File upload flow
        if ("file_upload" in semantic_types and
            ActionType.UPLOAD in action_types):
            return FlowType.FILE_UPLOAD_FLOW, 0.84
        
        # Data entry flow
        if ("crud_form" in semantic_types and
            ActionType.FILL in action_types and
            ActionType.SUBMIT in action_types):
            return FlowType.DATA_ENTRY, 0.82
        
        # Default to unknown
        return FlowType.UNKNOWN, 0.5
    
    def _is_happy_path(
        self,
        semantic_types: List[str],
        action_types: List[ActionType],
    ) -> bool:
        """Determine if this is a happy path flow.
        
        Args:
            semantic_types: List of semantic page types
            action_types: List of action types
            
        Returns:
            True if this is a happy path
        """
        # Happy paths typically end in success states
        # and don't include error/validation pages
        happy_indicators = [
            "dashboard",
            "table_view",
            "confirmation",
        ]
        
        if semantic_types and semantic_types[-1] in happy_indicators:
            return True
        
        # Happy paths have successful actions
        if ActionType.SUBMIT in action_types or ActionType.CONFIRM in action_types:
            return True
        
        return False
    
    def _is_recovery_path(
        self,
        semantic_types: List[str],
        action_types: List[ActionType],
    ) -> bool:
        """Determine if this is a recovery path.
        
        Args:
            semantic_types: List of semantic page types
            action_types: List of action types
            
        Returns:
            True if this is a recovery path
        """
        # Recovery paths include retry or back actions
        recovery_actions = [ActionType.RETRY, ActionType.BACK, ActionType.CANCEL]
        
        return any(action in recovery_actions for action in action_types)
    
    def _is_validation_path(
        self,
        semantic_types: List[str],
        action_types: List[ActionType],
    ) -> bool:
        """Determine if this is a validation path.
        
        Args:
            semantic_types: List of semantic page types
            action_types: List of action types
            
        Returns:
            True if this is a validation path
        """
        # Validation paths include validation actions or error pages
        validation_indicators = [
            "error_page",
            "validation",
        ]
        
        if any(indicator in semantic_types for indicator in validation_indicators):
            return True
        
        if ActionType.VALIDATE in action_types:
            return True
        
        return False
    
    def _calculate_flow_completeness(
        self,
        nodes: List[FlowNode],
        edges: List[FlowEdge],
    ) -> float:
        """Calculate flow completeness based on node and edge confidence.
        
        Args:
            nodes: Flow nodes
            edges: Flow edges
            
        Returns:
            Completeness score (0.0 to 1.0)
        """
        if not nodes:
            return 0.0
        
        # Average node confidence
        avg_node_confidence = sum(n.confidence for n in nodes) / len(nodes)
        
        # Average edge confidence
        avg_edge_confidence = sum(e.confidence for e in edges) / len(edges) if edges else 0.5
        
        # Edge coverage (how well connected the flow is)
        edge_coverage = len(edges) / max(1, len(nodes) - 1)
        
        # Combined completeness
        completeness = (avg_node_confidence * 0.4) + (avg_edge_confidence * 0.3) + (edge_coverage * 0.3)
        
        return min(completeness, 1.0)
    
    def _generate_flow_name(
        self,
        flow_type: FlowType,
        semantic_types: List[str],
    ) -> str:
        """Generate a human-readable flow name.
        
        Args:
            flow_type: Flow type
            semantic_types: Semantic page types
            
        Returns:
            Human-readable flow name
        """
        type_name = flow_type.value.replace("_", " ").title()
        
        if semantic_types:
            path_str = " -> ".join(semantic_types[:3])  # Limit to first 3 types
            if len(semantic_types) > 3:
                path_str += " -> ..."
            return f"{type_name} ({path_str})"
        
        return type_name
    
    def enhance_with_ai_reasoning(
        self,
        flow: BusinessFlow,
        context: Dict[str, Any],
    ) -> BusinessFlow:
        """Enhance flow classification with AI reasoning.
        
        Args:
            flow: Business flow to enhance
            context: Additional context for AI reasoning
            
        Returns:
            Enhanced business flow
        """
        if not self.enable_ai_reasoning:
            return flow
        
        # Prepare AI prompt
        prompt = self._prepare_ai_prompt(flow, context)
        
        # TODO: Integrate with existing LLM infrastructure
        # For now, use rule-based enhancement
        
        # Enhance confidence based on evidence
        if len(flow.evidence) >= 3:
            flow.confidence = min(flow.confidence + 0.1, 1.0)
        
        # Enhance completeness based on node count
        if len(flow.nodes) >= 3:
            flow.completeness = min(flow.completeness + 0.1, 1.0)
        
        logger.debug(f"[FLOW REASONING] Enhanced flow {flow.flow_id} with AI reasoning")
        
        return flow
    
    def _prepare_ai_prompt(
        self,
        flow: BusinessFlow,
        context: Dict[str, Any],
    ) -> str:
        """Prepare AI prompt for flow reasoning.
        
        Args:
            flow: Business flow
            context: Additional context
            
        Returns:
            AI prompt
        """
        prompt = f"""
Analyze the following business flow and provide insights:

Flow Type: {flow.flow_type.value}
Flow Name: {flow.flow_name}
Nodes: {[node.semantic_type for node in flow.nodes]}
Actions: {[edge.action.action_type.value for edge in flow.edges]}
Evidence: {flow.evidence}

Context:
{json.dumps(context, indent=2)}

Please provide:
1. Confidence assessment (0.0 to 1.0)
2. Flow completeness assessment (0.0 to 1.0)
3. Whether this is a happy path
4. Whether this is a recovery path
5. Whether this is a validation path
6. Any additional business insights
"""
        return prompt
