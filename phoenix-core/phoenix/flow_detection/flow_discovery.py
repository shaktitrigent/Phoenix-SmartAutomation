"""Flow Discovery Engine - Main coordinator for business flow discovery.

This module coordinates all flow detection components, integrating with
IntelligentRuntime to provide seamless business flow discovery during
test execution.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowGraph,
    PageTransition,
    SemanticAction,
)
from phoenix.flow_detection.transition_tracker import PageTransitionTracker
from phoenix.flow_detection.flow_graph_builder import FlowGraphBuilder
from phoenix.flow_detection.flow_reasoning import FlowReasoningEngine
from phoenix.flow_detection.flow_persistence import FlowPersistenceManager

logger = logging.getLogger(__name__)


class FlowDiscoveryEngine:
    """Main coordinator for business flow discovery.
    
    This engine:
    - Coordinates all flow detection components
    - Integrates with IntelligentRuntime
    - Observes page transitions during execution
    - Builds flow graphs from observed transitions
    - Discovers business flows using AI reasoning
    - Persists flows for runtime learning
    - Provides flow intelligence for test generation and healing
    """
    
    def __init__(
        self,
        base_dir: str = "phoenix_runtime",
        enable_persistence: bool = True,
        enable_ai_reasoning: bool = True,
        enable_flow_learning: bool = True,
    ):
        """Initialize the flow discovery engine.
        
        Args:
            base_dir: Base directory for storage
            enable_persistence: Enable flow persistence
            enable_ai_reasoning: Enable AI-powered flow reasoning
            enable_flow_learning: Enable runtime flow learning
        """
        self.base_dir = base_dir
        self.enable_persistence = enable_persistence
        self.enable_ai_reasoning = enable_ai_reasoning
        self.enable_flow_learning = enable_flow_learning
        
        # Initialize components
        self.transition_tracker = PageTransitionTracker(
            base_dir=base_dir,
            enable_persistence=enable_persistence,
        )
        
        self.flow_graph_builder = FlowGraphBuilder()
        
        self.flow_reasoning = FlowReasoningEngine(
            enable_ai_reasoning=enable_ai_reasoning,
        )
        
        self.flow_persistence = FlowPersistenceManager(
            base_dir=base_dir,
            enable_persistence=enable_persistence,
        )
        
        # Runtime state
        self.current_graph: Optional[FlowGraph] = None
        self.current_execution_id: Optional[str] = None
        self.current_test_id: Optional[str] = None
        self.current_project_name: Optional[str] = None
        
        # Discovered flows
        self.discovered_flows: List[BusinessFlow] = []
        
        logger.info(f"[FLOW DISCOVERY] Initialized with base_dir: {base_dir}")
        logger.info(f"[FLOW DISCOVERY] Persistence: {enable_persistence}")
        logger.info(f"[FLOW DISCOVERY] AI reasoning: {enable_ai_reasoning}")
        logger.info(f"[FLOW DISCOVERY] Flow learning: {enable_flow_learning}")
    
    def start_execution(
        self,
        execution_id: str,
        test_id: str = "",
        project_name: str = "",
    ) -> None:
        """Start a new execution for flow discovery.
        
        Args:
            execution_id: Execution ID
            test_id: Test ID
            project_name: Project name
        """
        self.current_execution_id = execution_id
        self.current_test_id = test_id
        self.current_project_name = project_name
        
        # Create new flow graph for this execution
        self.current_graph = self.flow_graph_builder.create_graph(
            project_name=project_name,
            graph_id=f"graph_execution_{execution_id}",
        )
        
        # Clear discovered flows for this execution
        self.discovered_flows = []
        
        logger.info(f"[FLOW DISCOVERY] Started execution: {execution_id}")
        logger.info(f"[FLOW DISCOVERY] Project: {project_name}, Test: {test_id}")
    
    def observe_page(
        self,
        page_type: str,
        url: str,
        dom_content: str,
        semantic_page: Any = None,
    ) -> None:
        """Observe a page during execution.
        
        Args:
            page_type: Semantic page type
            url: Page URL
            dom_content: DOM content
            semantic_page: Full semantic page object
        """
        # Set current page in transition tracker
        self.transition_tracker.set_current_page(
            page_type=page_type,
            url=url,
            dom_content=dom_content,
            semantic_page=semantic_page,
        )
        
        logger.debug(f"[FLOW DISCOVERY] Observed page: {page_type} at {url}")
    
    def observe_action(
        self,
        element_info: Dict[str, Any],
        previous_dom: str = "",
        current_dom: str = "",
    ) -> SemanticAction:
        """Observe a user action during execution.
        
        Args:
            element_info: Information about the element interacted with
            previous_dom: Previous DOM content
            current_dom: Current DOM content
            
        Returns:
            Inferred semantic action
        """
        # Infer action from DOM change
        action = self.transition_tracker.infer_action_from_dom_change(
            previous_dom=previous_dom,
            current_dom=current_dom,
            element_info=element_info,
        )
        
        logger.debug(f"[FLOW DISCOVERY] Observed action: {action.action_type.value}")
        
        return action
    
    def observe_page_transition(
        self,
        target_page_type: str,
        target_url: str,
        target_dom_content: str,
        action: SemanticAction,
    ) -> PageTransition:
        """Observe a page transition during execution.
        
        Args:
            target_page_type: Semantic type of target page
            target_url: URL of target page
            target_dom_content: DOM content of target page
            action: Action that caused the transition
            
        Returns:
            Recorded page transition
        """
        # Record transition
        transition = self.transition_tracker.record_transition(
            target_page_type=target_page_type,
            target_url=target_url,
            target_dom_content=target_dom_content,
            action=action,
            execution_id=self.current_execution_id or "",
            test_id=self.current_test_id or "",
            project_name=self.current_project_name or "",
        )
        
        # Add to flow graph
        if self.current_graph:
            self.flow_graph_builder.add_transition_to_graph(transition)
        
        logger.info(f"[FLOW DISCOVERY] Observed transition: {transition.source_page_type} -> {transition.target_page_type}")
        
        return transition
    
    def end_execution(self) -> List[BusinessFlow]:
        """End current execution and discover flows.
        
        Returns:
            List of discovered business flows
        """
        if not self.current_graph:
            logger.warning("[FLOW DISCOVERY] No active execution to end")
            return []
        
        logger.info(f"[FLOW DISCOVERY] Ending execution: {self.current_execution_id}")
        logger.info(f"[FLOW DISCOVERY] Graph has {self.current_graph.total_nodes} nodes, {self.current_graph.total_edges} edges")
        
        # Analyze flow graph to discover business flows
        self.discovered_flows = self.flow_reasoning.analyze_flow_graph(self.current_graph)
        
        # Enhance flows with AI reasoning
        if self.enable_ai_reasoning:
            for flow in self.discovered_flows:
                context = {
                    "execution_id": self.current_execution_id,
                    "test_id": self.current_test_id,
                    "project_name": self.current_project_name,
                    "graph_statistics": self.flow_graph_builder.get_graph_statistics(),
                }
                self.flow_reasoning.enhance_with_ai_reasoning(flow, context)
        
        # Persist flows
        if self.enable_persistence:
            for flow in self.discovered_flows:
                self.flow_persistence.store_flow(flow, self.current_project_name or "")
            
            # Persist graph
            self.flow_persistence.store_graph(self.current_graph, self.current_project_name or "")
        
        # Learn from flows
        if self.enable_flow_learning:
            self._learn_from_flows()
        
        logger.info(f"[FLOW DISCOVERY] Discovered {len(self.discovered_flows)} business flows")
        
        return self.discovered_flows
    
    def _learn_from_flows(self) -> None:
        """Learn from discovered flows for runtime improvement."""
        if not self.discovered_flows:
            return
        
        # Update confidence based on execution
        for flow in self.discovered_flows:
            if flow.flow_id in self.flow_persistence.flows_cache:
                # Flow already exists, update it
                existing_flow = self.flow_persistence.flows_cache[flow.flow_id]
                
                # Merge statistics
                existing_flow.total_observations += flow.total_observations
                existing_flow.success_count += flow.success_count
                existing_flow.failure_count += flow.failure_count
                
                # Update confidence
                if existing_flow.total_observations > 0:
                    success_rate = existing_flow.success_count / existing_flow.total_observations
                    existing_flow.confidence = (existing_flow.confidence * 0.7) + (success_rate * 0.3)
                
                # Update timestamp
                existing_flow.last_observed = flow.last_observed
                
                # Store updated flow
                self.flow_persistence.store_flow(existing_flow, self.current_project_name or "")
        
        logger.debug("[FLOW DISCOVERY] Learned from discovered flows")
    
    def get_discovered_flows(
        self,
        project_name: str = "",
    ) -> List[BusinessFlow]:
        """Get discovered flows for a project.
        
        Args:
            project_name: Project name
            
        Returns:
            List of discovered business flows
        """
        if self.discovered_flows:
            return self.discovered_flows
        
        # Load from persistence
        return self.flow_persistence.load_all_flows(project_name)
    
    def get_flow_by_type(
        self,
        flow_type: str,
        project_name: str = "",
    ) -> List[BusinessFlow]:
        """Get flows by type.
        
        Args:
            flow_type: Flow type
            project_name: Project name
            
        Returns:
            List of flows of the specified type
        """
        return self.flow_persistence.get_flow_by_type(flow_type, project_name)
    
    def get_happy_path_flows(
        self,
        project_name: str = "",
    ) -> List[BusinessFlow]:
        """Get happy path flows.
        
        Args:
            project_name: Project name
            
        Returns:
            List of happy path flows
        """
        return self.flow_persistence.get_happy_path_flows(project_name)
    
    def get_flow_statistics(
        self,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Get flow discovery statistics.
        
        Args:
            project_name: Project name
            
        Returns:
            Flow discovery statistics
        """
        return self.flow_persistence.get_flow_statistics(project_name)
    
    def get_transition_patterns(
        self,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Get transition patterns.
        
        Args:
            project_name: Project name
            
        Returns:
            Transition pattern analysis
        """
        return self.transition_tracker.get_transition_patterns(project_name)
    
    def clear_history(
        self,
        project_name: str = "",
    ) -> None:
        """Clear flow discovery history.
        
        Args:
            project_name: Project name
        """
        self.transition_tracker.clear_history()
        
        if project_name:
            self.flow_persistence.clear_project_flows(project_name)
        
        logger.info(f"[FLOW DISCOVERY] Cleared history for project {project_name}")
    
    def integrate_with_runtime(
        self,
        semantic_page: Any,
        url: str,
        dom_content: str,
    ) -> None:
        """Integrate with IntelligentRuntime semantic understanding.
        
        Args:
            semantic_page: SemanticPage object from Priority 20
            url: Page URL
            dom_content: DOM content
        """
        if not semantic_page:
            return
        
        # Extract semantic information
        page_type = semantic_page.page_type.value if hasattr(semantic_page, 'page_type') else "unknown"
        
        # Observe the page
        self.observe_page(
            page_type=page_type,
            url=url,
            dom_content=dom_content,
            semantic_page=semantic_page,
        )
        
        logger.debug(f"[FLOW DISCOVERY] Integrated with semantic understanding: {page_type}")
    
    def get_test_generation_recommendations(
        self,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Get flow-based recommendations for test generation.
        
        Args:
            project_name: Project name
            
        Returns:
            Test generation recommendations based on discovered flows
        """
        flows = self.get_discovered_flows(project_name)
        
        recommendations = {
            "happy_paths": [],
            "negative_paths": [],
            "validation_paths": [],
            "business_workflows": [],
            "coverage_gaps": [],
        }
        
        # Happy paths
        happy_flows = self.get_happy_path_flows(project_name)
        for flow in happy_flows:
            if flow.confidence >= 0.7:
                recommendations["happy_paths"].append({
                    "flow_type": flow.flow_type.value,
                    "flow_name": flow.flow_name,
                    "confidence": flow.confidence,
                    "steps": [node.semantic_type for node in flow.nodes],
                })
        
        # Negative/recovery paths
        for flow in flows:
            if flow.is_recovery_path and flow.confidence >= 0.6:
                recommendations["negative_paths"].append({
                    "flow_type": flow.flow_type.value,
                    "flow_name": flow.flow_name,
                    "confidence": flow.confidence,
                    "steps": [node.semantic_type for node in flow.nodes],
                })
        
        # Validation paths
        for flow in flows:
            if flow.is_validation_path and flow.confidence >= 0.6:
                recommendations["validation_paths"].append({
                    "flow_type": flow.flow_type.value,
                    "flow_name": flow.flow_name,
                    "confidence": flow.confidence,
                    "steps": [node.semantic_type for node in flow.nodes],
                })
        
        # Business workflows
        for flow in flows:
            if flow.confidence >= 0.7 and flow.flow_type.value != "unknown":
                recommendations["business_workflows"].append({
                    "flow_type": flow.flow_type.value,
                    "flow_name": flow.flow_name,
                    "confidence": flow.confidence,
                    "completeness": flow.completeness,
                    "steps": [node.semantic_type for node in flow.nodes],
                })
        
        # Coverage gaps (high-level suggestion)
        common_flow_types = [
            "authentication",
            "search_flow",
            "crud_create",
            "crud_update",
            "crud_delete",
        ]
        
        discovered_types = set(f.flow_type.value for f in flows)
        for flow_type in common_flow_types:
            if flow_type not in discovered_types:
                recommendations["coverage_gaps"].append({
                    "missing_flow_type": flow_type,
                    "suggestion": f"Consider generating tests for {flow_type} scenarios",
                })
        
        logger.info(f"[FLOW DISCOVERY] Generated test generation recommendations: {len(recommendations['happy_paths'])} happy paths, {len(recommendations['business_workflows'])} workflows")
        
        return recommendations
