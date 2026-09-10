"""Flow Graph Builder - Construct flow graphs from page transitions.

This module builds flow graph structures from observed page transitions,
creating nodes (semantic pages) and edges (transitions) that represent
discovered business workflows.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

from phoenix.flow_detection.models import (
    FlowNode,
    FlowEdge,
    FlowGraph,
    PageTransition,
)

logger = logging.getLogger(__name__)


class FlowGraphBuilder:
    """Builds flow graphs from page transitions.
    
    This builder:
    - Creates flow nodes from semantic page types
    - Creates flow edges from page transitions
    - Constructs complete flow graphs
    - Tracks node and edge statistics
    - Supports incremental graph building
    """
    
    def __init__(self):
        """Initialize the flow graph builder."""
        self.graph: Optional[FlowGraph] = None
        self.node_id_map: Dict[str, str] = {}  # semantic_type -> node_id
        self.edge_id_map: Dict[str, str] = {}  # (source_id, target_id, action) -> edge_id
        
        logger.info("[FLOW GRAPH BUILDER] Initialized")
    
    def create_graph(
        self,
        project_name: str = "",
        graph_id: Optional[str] = None,
    ) -> FlowGraph:
        """Create a new flow graph.
        
        Args:
            project_name: Project name
            graph_id: Optional graph ID (auto-generated if not provided)
            
        Returns:
            New flow graph
        """
        if graph_id is None:
            graph_id = f"graph_{uuid.uuid4().hex[:8]}"
        
        self.graph = FlowGraph(
            graph_id=graph_id,
            project_name=project_name,
        )
        
        self.node_id_map.clear()
        self.edge_id_map.clear()
        
        logger.info(f"[FLOW GRAPH BUILDER] Created new graph: {graph_id}")
        
        return self.graph
    
    def add_transition_to_graph(
        self,
        transition: PageTransition,
    ) -> None:
        """Add a page transition to the flow graph.
        
        Args:
            transition: Page transition to add
        """
        if self.graph is None:
            logger.warning("[FLOW GRAPH BUILDER] No graph created, call create_graph() first")
            return
        
        # Get or create source node
        source_node = self._get_or_create_node(
            semantic_type=transition.source_page_type,
            url_pattern=transition.source_url,
        )
        
        # Get or create target node
        target_node = self._get_or_create_node(
            semantic_type=transition.target_page_type,
            url_pattern=transition.target_url,
        )
        
        # Create or update edge
        edge = self._get_or_create_edge(
            source_node=source_node,
            target_node=target_node,
            action=transition.action,
            transition=transition,
        )
        
        # Update node statistics
        source_node.visit_count += 1
        target_node.visit_count += 1
        
        if transition.dom_change_detected:
            # Consider this a successful transition
            source_node.success_count += 1
            edge.success_count += 1
        else:
            # Transition might have failed
            source_node.failure_count += 1
            edge.failure_count += 1
        
        # Update edge statistics
        edge.frequency += 1
        edge.success_rate = edge.success_count / max(1, edge.frequency)
        
        # Update node confidence based on visit frequency
        self._update_node_confidence(source_node)
        self._update_node_confidence(target_node)
        
        # Update edge confidence based on success rate and frequency
        edge.confidence = (edge.success_rate * 0.7) + (min(edge.frequency / 10, 1.0) * 0.3)
        
        # Update timestamps
        source_node.last_observed = transition.timestamp
        target_node.last_observed = transition.timestamp
        edge.last_observed = transition.timestamp
        self.graph.last_observed = transition.timestamp
        
        logger.debug(f"[FLOW GRAPH BUILDER] Added transition: {source_node.semantic_type} -> {target_node.semantic_type}")
    
    def _get_or_create_node(
        self,
        semantic_type: str,
        url_pattern: str = "",
    ) -> FlowNode:
        """Get existing node or create new one.
        
        Args:
            semantic_type: Semantic page type
            url_pattern: URL pattern
            
        Returns:
            Flow node
        """
        # Check if node already exists
        if semantic_type in self.node_id_map:
            node_id = self.node_id_map[semantic_type]
            node = next((n for n in self.graph.nodes if n.node_id == node_id), None)
            if node:
                return node
        
        # Create new node
        node_id = f"node_{semantic_type}_{uuid.uuid4().hex[:8]}"
        node = FlowNode(
            node_id=node_id,
            semantic_type=semantic_type,
            url_pattern=url_pattern,
            confidence=0.5,  # Initial confidence
        )
        
        self.node_id_map[semantic_type] = node_id
        self.graph.add_node(node)
        
        logger.debug(f"[FLOW GRAPH BUILDER] Created node: {semantic_type}")
        
        return node
    
    def _get_or_create_edge(
        self,
        source_node: FlowNode,
        target_node: FlowNode,
        action: Any,
        transition: PageTransition,
    ) -> FlowEdge:
        """Get existing edge or create new one.
        
        Args:
            source_node: Source flow node
            target_node: Target flow node
            action: Semantic action
            transition: Page transition
            
        Returns:
            Flow edge
        """
        # Create edge key
        edge_key = f"{source_node.node_id}_{target_node.node_id}_{action.action_type.value}"
        
        # Check if edge already exists
        if edge_key in self.edge_id_map:
            edge_id = self.edge_id_map[edge_key]
            edge = next((e for e in self.graph.edges if e.edge_id == edge_id), None)
            if edge:
                # Add evidence
                edge.evidence.extend(transition.evidence)
                return edge
        
        # Create new edge
        edge_id = f"edge_{uuid.uuid4().hex[:8]}"
        edge = FlowEdge(
            edge_id=edge_id,
            source_node_id=source_node.node_id,
            target_node_id=target_node.node_id,
            action=action,
            confidence=transition.confidence,
            evidence=transition.evidence.copy(),
        )
        
        self.edge_id_map[edge_key] = edge_id
        self.graph.add_edge(edge)
        
        logger.debug(f"[FLOW GRAPH BUILDER] Created edge: {source_node.semantic_type} -> {target_node.semantic_type}")
        
        return edge
    
    def _update_node_confidence(self, node: FlowNode) -> None:
        """Update node confidence based on statistics.
        
        Args:
            node: Flow node to update
        """
        if node.visit_count == 0:
            node.confidence = 0.5
        else:
            # Confidence based on success rate and visit frequency
            success_rate = node.success_count / max(1, node.visit_count)
            visit_factor = min(node.visit_count / 10, 1.0)
            node.confidence = (success_rate * 0.6) + (visit_factor * 0.4)
    
    def build_from_transitions(
        self,
        transitions: List[PageTransition],
        project_name: str = "",
    ) -> FlowGraph:
        """Build a complete flow graph from transitions.
        
        Args:
            transitions: List of page transitions
            project_name: Project name
            
        Returns:
            Complete flow graph
        """
        # Create new graph
        self.create_graph(project_name=project_name)
        
        # Add all transitions
        for transition in transitions:
            self.add_transition_to_graph(transition)
        
        logger.info(f"[FLOW GRAPH BUILDER] Built graph with {self.graph.total_nodes} nodes and {self.graph.total_edges} edges")
        
        return self.graph
    
    def detect_flow_patterns(self) -> Dict[str, Any]:
        """Detect common flow patterns in the graph.
        
        Returns:
            Dictionary of detected patterns
        """
        if self.graph is None:
            return {}
        
        patterns = {
            "linear_flows": [],
            "branching_flows": [],
            "cyclic_flows": [],
            "hub_nodes": [],
            "dead_ends": [],
        }
        
        # Build adjacency list
        outgoing: Dict[str, List[str]] = {}
        incoming: Dict[str, Dict[str, int]] = {}
        
        for edge in self.graph.edges:
            if edge.source_node_id not in outgoing:
                outgoing[edge.source_node_id] = []
            outgoing[edge.source_node_id].append(edge.target_node_id)
            
            if edge.target_node_id not in incoming:
                incoming[edge.target_node_id] = {}
            incoming[edge.target_node_id][edge.source_node_id] = incoming[edge.target_node_id].get(edge.source_node_id, 0) + 1
        
        # Detect linear flows (chains)
        patterns["linear_flows"] = self._detect_linear_chains(outgoing, incoming)
        
        # Detect branching flows (nodes with multiple outgoing edges)
        patterns["branching_flows"] = [
            {
                "node_id": node_id,
                "semantic_type": next((n.semantic_type for n in self.graph.nodes if n.node_id == node_id), ""),
                "branch_count": len(targets),
            }
            for node_id, targets in outgoing.items()
            if len(targets) > 1
        ]
        
        # Detect cyclic flows
        patterns["cyclic_flows"] = self._detect_cycles(outgoing)
        
        # Detect hub nodes (nodes with many incoming edges)
        patterns["hub_nodes"] = [
            {
                "node_id": node_id,
                "semantic_type": next((n.semantic_type for n in self.graph.nodes if n.node_id == node_id), ""),
                "incoming_count": sum(sources.values()),
            }
            for node_id, sources in incoming.items()
            if sum(sources.values()) >= 3
        ]
        
        # Detect dead ends (nodes with no outgoing edges)
        patterns["dead_ends"] = [
            {
                "node_id": node_id,
                "semantic_type": next((n.semantic_type for n in self.graph.nodes if n.node_id == node_id), ""),
            }
            for node in self.graph.nodes
            if node.node_id not in outgoing or len(outgoing[node.node_id]) == 0
        ]
        
        return patterns
    
    def _detect_linear_chains(
        self,
        outgoing: Dict[str, List[str]],
        incoming: Dict[str, Dict[str, int]],
    ) -> List[Dict[str, Any]]:
        """Detect linear flow chains.
        
        Args:
            outgoing: Outgoing edge mapping
            incoming: Incoming edge mapping
            
        Returns:
            List of linear chains
        """
        chains = []
        visited: Set[str] = set()
        
        for node in self.graph.nodes:
            if node.node_id in visited:
                continue
            
            # Start of a potential chain
            if node.node_id not in incoming or len(incoming[node.node_id]) == 0:
                chain = [node]
                current = node
                
                # Follow the chain
                while current.node_id in outgoing and len(outgoing[current.node_id]) == 1:
                    next_node_id = outgoing[current.node_id][0]
                    next_node = next((n for n in self.graph.nodes if n.node_id == next_node_id), None)
                    if not next_node:
                        break
                    
                    # Check if this is a simple chain (single incoming)
                    if next_node_id in incoming and len(incoming[next_node_id]) == 1:
                        chain.append(next_node)
                        visited.add(next_node_id)
                        current = next_node
                    else:
                        break
                
                if len(chain) > 1:
                    chains.append({
                        "nodes": [n.semantic_type for n in chain],
                        "length": len(chain),
                    })
                    visited.update(n.node_id for n in chain)
        
        return chains
    
    def _detect_cycles(self, outgoing: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Detect cyclic flows using DFS.
        
        Args:
            outgoing: Outgoing edge mapping
            
        Returns:
            List of detected cycles
        """
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            if node_id in outgoing:
                for neighbor in outgoing[node_id]:
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:]
                        cycles.append({
                            "nodes": cycle,
                            "length": len(cycle),
                        })
            
            rec_stack.remove(node_id)
            path.pop()
            return False
        
        for node in self.graph.nodes:
            if node.node_id not in visited:
                dfs(node.node_id)
        
        return cycles
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get comprehensive graph statistics.
        
        Returns:
            Graph statistics
        """
        if self.graph is None:
            return {}
        
        stats = {
            "graph_id": self.graph.graph_id,
            "project_name": self.graph.project_name,
            "total_nodes": self.graph.total_nodes,
            "total_edges": self.graph.total_edges,
            "total_flows": self.graph.total_flows,
            "node_types": {},
            "edge_types": {},
            "avg_node_confidence": 0.0,
            "avg_edge_confidence": 0.0,
            "avg_edge_success_rate": 0.0,
        }
        
        # Node type distribution
        for node in self.graph.nodes:
            stats["node_types"][node.semantic_type] = stats["node_types"].get(node.semantic_type, 0) + 1
        
        # Edge type distribution
        for edge in self.graph.edges:
            action_type = edge.action.action_type.value
            stats["edge_types"][action_type] = stats["edge_types"].get(action_type, 0) + 1
        
        # Average confidences
        if self.graph.nodes:
            stats["avg_node_confidence"] = sum(n.confidence for n in self.graph.nodes) / len(self.graph.nodes)
        
        if self.graph.edges:
            stats["avg_edge_confidence"] = sum(e.confidence for e in self.graph.edges) / len(self.graph.edges)
            stats["avg_edge_success_rate"] = sum(e.success_rate for e in self.graph.edges) / len(self.graph.edges)
        
        return stats
