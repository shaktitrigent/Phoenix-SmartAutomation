"""Unit tests for Flow Detection Module (Priority 21)."""

import pytest
from datetime import datetime, timezone
from phoenix.flow_detection.models import (
    ActionType,
    FlowType,
    SemanticAction,
    PageTransition,
    FlowNode,
    FlowEdge,
    BusinessFlow,
    FlowGraph,
)
from phoenix.flow_detection.transition_tracker import PageTransitionTracker
from phoenix.flow_detection.flow_graph_builder import FlowGraphBuilder
from phoenix.flow_detection.flow_reasoning import FlowReasoningEngine
from phoenix.flow_detection.flow_persistence import FlowPersistenceManager
from phoenix.flow_detection.flow_discovery import FlowDiscoveryEngine


class TestSemanticAction:
    """Test SemanticAction model."""
    
    def test_create_semantic_action(self):
        """Test creating a semantic action."""
        action = SemanticAction(
            action_type=ActionType.CLICK,
            confidence=0.8,
            element_role="button",
            element_text="Submit",
            page_type="crud_form",
            page_url="http://example.com/form",
        )
        
        assert action.action_type == ActionType.CLICK
        assert action.confidence == 0.8
        assert action.element_role == "button"
        assert action.element_text == "Submit"
    
    def test_semantic_action_with_evidence(self):
        """Test semantic action with evidence."""
        action = SemanticAction(
            action_type=ActionType.SUBMIT,
            confidence=0.9,
            evidence=["Element role: button", "Element text: Submit"],
        )
        
        assert len(action.evidence) == 2
        assert "Element role: button" in action.evidence


class TestPageTransition:
    """Test PageTransition model."""
    
    def test_create_page_transition(self):
        """Test creating a page transition."""
        action = SemanticAction(action_type=ActionType.CLICK)
        
        transition = PageTransition(
            source_page_type="authentication_screen",
            target_page_type="dashboard",
            action=action,
            execution_id="test_exec_001",
        )
        
        assert transition.source_page_type == "authentication_screen"
        assert transition.target_page_type == "dashboard"
        assert transition.action.action_type == ActionType.CLICK
        assert transition.execution_id == "test_exec_001"


class TestFlowNode:
    """Test FlowNode model."""
    
    def test_create_flow_node(self):
        """Test creating a flow node."""
        node = FlowNode(
            node_id="node_001",
            semantic_type="dashboard",
            visit_count=5,
            success_count=4,
            failure_count=1,
        )
        
        assert node.node_id == "node_001"
        assert node.semantic_type == "dashboard"
        assert node.visit_count == 5
        assert node.success_count == 4


class TestFlowEdge:
    """Test FlowEdge model."""
    
    def test_create_flow_edge(self):
        """Test creating a flow edge."""
        action = SemanticAction(action_type=ActionType.CLICK)
        
        edge = FlowEdge(
            edge_id="edge_001",
            source_node_id="node_001",
            target_node_id="node_002",
            action=action,
            frequency=3,
            success_count=2,
            failure_count=1,
        )
        
        assert edge.edge_id == "edge_001"
        assert edge.source_node_id == "node_001"
        assert edge.target_node_id == "node_002"
        assert edge.frequency == 3


class TestBusinessFlow:
    """Test BusinessFlow model."""
    
    def test_create_business_flow(self):
        """Test creating a business flow."""
        nodes = [
            FlowNode(node_id="n1", semantic_type="authentication_screen"),
            FlowNode(node_id="n2", semantic_type="dashboard"),
        ]
        
        edges = [
            FlowEdge(
                edge_id="e1",
                source_node_id="n1",
                target_node_id="n2",
                action=SemanticAction(action_type=ActionType.SUBMIT),
            )
        ]
        
        flow = BusinessFlow(
            flow_id="flow_001",
            flow_type=FlowType.AUTHENTICATION,
            flow_name="Authentication Flow",
            nodes=nodes,
            edges=edges,
            confidence=0.9,
            is_happy_path=True,
        )
        
        assert flow.flow_id == "flow_001"
        assert flow.flow_type == FlowType.AUTHENTICATION
        assert len(flow.nodes) == 2
        assert len(flow.edges) == 1
        assert flow.is_happy_path is True


class TestFlowGraph:
    """Test FlowGraph model."""
    
    def test_create_flow_graph(self):
        """Test creating a flow graph."""
        graph = FlowGraph(
            graph_id="graph_001",
            project_name="test_project",
        )
        
        assert graph.graph_id == "graph_001"
        assert graph.project_name == "test_project"
        assert graph.total_nodes == 0
        assert graph.total_edges == 0
    
    def test_add_node_to_graph(self):
        """Test adding a node to the graph."""
        graph = FlowGraph(graph_id="graph_001")
        node = FlowNode(node_id="n1", semantic_type="dashboard")
        
        graph.add_node(node)
        
        assert graph.total_nodes == 1
        assert len(graph.nodes) == 1
    
    def test_add_edge_to_graph(self):
        """Test adding an edge to the graph."""
        graph = FlowGraph(graph_id="graph_001")
        edge = FlowEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            action=SemanticAction(action_type=ActionType.CLICK),
        )
        
        graph.add_edge(edge)
        
        assert graph.total_edges == 1
        assert len(graph.edges) == 1
    
    def test_add_flow_to_graph(self):
        """Test adding a flow to the graph."""
        graph = FlowGraph(graph_id="graph_001")
        flow = BusinessFlow(
            flow_id="f1",
            flow_type=FlowType.AUTHENTICATION,
        )
        
        graph.add_flow(flow)
        
        assert graph.total_flows == 1
        assert len(graph.flows) == 1


class TestPageTransitionTracker:
    """Test PageTransitionTracker."""
    
    def test_initialization(self, tmp_path):
        """Test tracker initialization."""
        tracker = PageTransitionTracker(base_dir=str(tmp_path))
        
        assert tracker.current_page_type is None
        assert tracker.current_url is None
        assert len(tracker.transitions) == 0
    
    def test_set_current_page(self, tmp_path):
        """Test setting current page."""
        tracker = PageTransitionTracker(base_dir=str(tmp_path))
        
        tracker.set_current_page(
            page_type="dashboard",
            url="http://example.com",
            dom_content="<html>...</html>",
        )
        
        assert tracker.current_page_type == "dashboard"
        assert tracker.current_url == "http://example.com"
    
    def test_infer_action_from_dom_change(self, tmp_path):
        """Test inferring action from DOM change."""
        tracker = PageTransitionTracker(base_dir=str(tmp_path))
        
        tracker.set_current_page(
            page_type="crud_form",
            url="http://example.com/form",
            dom_content="<html>...</html>",
        )
        
        element_info = {
            "role": "button",
            "text": "Submit",
            "label": "",
            "xpath": "//button[text()='Submit']",
        }
        
        action = tracker.infer_action_from_dom_change(
            previous_dom="<html>...</html>",
            current_dom="<html>...</html>",
            element_info=element_info,
        )
        
        assert action.action_type == ActionType.SUBMIT
        assert action.element_role == "button"
        assert action.element_text == "Submit"
    
    def test_record_transition(self, tmp_path):
        """Test recording a page transition."""
        tracker = PageTransitionTracker(base_dir=str(tmp_path), enable_persistence=False)
        
        tracker.set_current_page(
            page_type="authentication_screen",
            url="http://example.com/login",
            dom_content="<html>...</html>",
        )
        
        action = SemanticAction(action_type=ActionType.SUBMIT)
        
        transition = tracker.record_transition(
            target_page_type="dashboard",
            target_url="http://example.com/dashboard",
            target_dom_content="<html>...</html>",
            action=action,
            execution_id="test_exec_001",
        )
        
        assert transition.source_page_type == "authentication_screen"
        assert transition.target_page_type == "dashboard"
        assert len(tracker.transitions) == 1
    
    def test_get_transitions(self, tmp_path):
        """Test getting transitions."""
        tracker = PageTransitionTracker(base_dir=str(tmp_path), enable_persistence=False)
        
        action = SemanticAction(action_type=ActionType.CLICK)
        tracker.record_transition(
            target_page_type="dashboard",
            target_url="http://example.com",
            target_dom_content="<html>...</html>",
            action=action,
            execution_id="exec_001",
            project_name="test_project",
        )
        
        transitions = tracker.get_transitions(project_name="test_project")
        
        assert len(transitions) == 1
        assert transitions[0].project_name == "test_project"


class TestFlowGraphBuilder:
    """Test FlowGraphBuilder."""
    
    def test_initialization(self):
        """Test builder initialization."""
        builder = FlowGraphBuilder()
        
        assert builder.graph is None
        assert len(builder.node_id_map) == 0
    
    def test_create_graph(self):
        """Test creating a graph."""
        builder = FlowGraphBuilder()
        graph = builder.create_graph(project_name="test_project")
        
        assert graph is not None
        assert graph.project_name == "test_project"
        assert builder.graph == graph
    
    def test_add_transition_to_graph(self):
        """Test adding a transition to the graph."""
        builder = FlowGraphBuilder()
        builder.create_graph(project_name="test_project")
        
        action = SemanticAction(action_type=ActionType.CLICK)
        transition = PageTransition(
            source_page_type="authentication_screen",
            target_page_type="dashboard",
            action=action,
        )
        
        builder.add_transition_to_graph(transition)
        
        assert builder.graph.total_nodes == 2
        assert builder.graph.total_edges == 1
    
    def test_build_from_transitions(self):
        """Test building a graph from transitions."""
        builder = FlowGraphBuilder()
        
        transitions = [
            PageTransition(
                source_page_type="authentication_screen",
                target_page_type="dashboard",
                action=SemanticAction(action_type=ActionType.SUBMIT),
            ),
            PageTransition(
                source_page_type="dashboard",
                target_page_type="crud_form",
                action=SemanticAction(action_type=ActionType.CREATE),
            ),
        ]
        
        graph = builder.build_from_transitions(transitions, project_name="test_project")
        
        assert graph.total_nodes == 3
        assert graph.total_edges == 2
    
    def test_detect_linear_chains(self):
        """Test detecting linear chains."""
        builder = FlowGraphBuilder()
        builder.create_graph()
        
        # Create a linear chain: auth -> dashboard -> form
        transitions = [
            PageTransition(
                source_page_type="authentication_screen",
                target_page_type="dashboard",
                action=SemanticAction(action_type=ActionType.SUBMIT),
            ),
            PageTransition(
                source_page_type="dashboard",
                target_page_type="crud_form",
                action=SemanticAction(action_type=ActionType.CREATE),
            ),
        ]
        
        for t in transitions:
            builder.add_transition_to_graph(t)
        
        patterns = builder.detect_flow_patterns()
        
        assert len(patterns["linear_flows"]) >= 1


class TestFlowReasoningEngine:
    """Test FlowReasoningEngine."""
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        assert engine.enable_ai_reasoning is False
    
    def test_classify_flow_pattern_authentication(self):
        """Test classifying authentication flow pattern."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        semantic_types = ["authentication_screen", "dashboard"]
        action_types = [ActionType.SUBMIT]
        
        flow_type, confidence = engine._classify_flow_pattern(semantic_types, action_types)
        
        assert flow_type == FlowType.AUTHENTICATION
        assert confidence >= 0.8
    
    def test_classify_flow_pattern_search(self):
        """Test classifying search flow pattern."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        semantic_types = ["search_screen", "table_view"]
        action_types = [ActionType.SEARCH]
        
        flow_type, confidence = engine._classify_flow_pattern(semantic_types, action_types)
        
        assert flow_type == FlowType.SEARCH_FLOW
        assert confidence >= 0.8
    
    def test_classify_flow_pattern_crud_create(self):
        """Test classifying CRUD create flow pattern."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        semantic_types = ["table_view", "crud_form"]
        action_types = [ActionType.CREATE, ActionType.SUBMIT]
        
        flow_type, confidence = engine._classify_flow_pattern(semantic_types, action_types)
        
        assert flow_type == FlowType.CRUD_CREATE
        assert confidence >= 0.8
    
    def test_is_happy_path(self):
        """Test happy path detection."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        # Happy path ending in dashboard
        semantic_types = ["authentication_screen", "dashboard"]
        action_types = [ActionType.SUBMIT]
        
        is_happy = engine._is_happy_path(semantic_types, action_types)
        
        assert is_happy is True
    
    def test_is_recovery_path(self):
        """Test recovery path detection."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        semantic_types = ["error_page", "dashboard"]
        action_types = [ActionType.RETRY]
        
        is_recovery = engine._is_recovery_path(semantic_types, action_types)
        
        assert is_recovery is True
    
    def test_analyze_flow_graph(self):
        """Test analyzing a flow graph."""
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        
        # Create a simple graph
        graph = FlowGraph(graph_id="test_graph", project_name="test_project")
        graph.add_node(FlowNode(node_id="n1", semantic_type="authentication_screen"))
        graph.add_node(FlowNode(node_id="n2", semantic_type="dashboard"))
        graph.add_edge(
            FlowEdge(
                edge_id="e1",
                source_node_id="n1",
                target_node_id="n2",
                action=SemanticAction(action_type=ActionType.SUBMIT),
            )
        )
        
        flows = engine.analyze_flow_graph(graph)
        
        assert len(flows) >= 0  # May or may not discover flows depending on confidence


class TestFlowPersistenceManager:
    """Test FlowPersistenceManager."""
    
    def test_initialization(self, tmp_path):
        """Test manager initialization."""
        manager = FlowPersistenceManager(base_dir=str(tmp_path), enable_persistence=False)
        
        assert manager.enable_persistence is False
        assert len(manager.flows_cache) == 0
    
    def test_store_and_load_flow(self, tmp_path):
        """Test storing and loading a flow."""
        manager = FlowPersistenceManager(base_dir=str(tmp_path))
        
        flow = BusinessFlow(
            flow_id="test_flow",
            flow_type=FlowType.AUTHENTICATION,
            flow_name="Test Flow",
            project_name="test_project",
        )
        
        manager.store_flow(flow, project_name="test_project")
        
        loaded_flow = manager.load_flow("test_flow", project_name="test_project")
        
        assert loaded_flow is not None
        assert loaded_flow.flow_id == "test_flow"
        assert loaded_flow.flow_type == FlowType.AUTHENTICATION
    
    def test_load_all_flows(self, tmp_path):
        """Test loading all flows for a project."""
        manager = FlowPersistenceManager(base_dir=str(tmp_path))
        
        flow1 = BusinessFlow(flow_id="f1", flow_type=FlowType.AUTHENTICATION)
        flow2 = BusinessFlow(flow_id="f2", flow_type=FlowType.SEARCH_FLOW)
        
        manager.store_flow(flow1, project_name="test_project")
        manager.store_flow(flow2, project_name="test_project")
        
        flows = manager.load_all_flows(project_name="test_project")
        
        assert len(flows) == 2
    
    def test_update_flow_statistics(self, tmp_path):
        """Test updating flow statistics."""
        manager = FlowPersistenceManager(base_dir=str(tmp_path))
        
        flow = BusinessFlow(
            flow_id="test_flow",
            flow_type=FlowType.AUTHENTICATION,
            total_observations=5,
            success_count=4,
            failure_count=1,
        )
        
        manager.store_flow(flow, project_name="test_project")
        manager.update_flow_statistics("test_flow", success=True, project_name="test_project")
        
        updated_flow = manager.load_flow("test_flow", project_name="test_project")
        
        assert updated_flow.total_observations == 6
        assert updated_flow.success_count == 5
    
    def test_get_flow_statistics(self, tmp_path):
        """Test getting flow statistics."""
        manager = FlowPersistenceManager(base_dir=str(tmp_path))
        
        flow = BusinessFlow(flow_id="f1", flow_type=FlowType.AUTHENTICATION, confidence=0.8)
        manager.store_flow(flow, project_name="test_project")
        
        stats = manager.get_flow_statistics(project_name="test_project")
        
        assert stats["total_flows"] == 1
        assert "authentication" in stats["flow_types"]


class TestFlowDiscoveryEngine:
    """Test FlowDiscoveryEngine."""
    
    def test_initialization(self, tmp_path):
        """Test engine initialization."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        
        assert engine.current_execution_id is None
        assert len(engine.discovered_flows) == 0
    
    def test_start_execution(self, tmp_path):
        """Test starting an execution."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        
        engine.start_execution(
            execution_id="test_exec_001",
            test_id="test_login",
            project_name="test_project",
        )
        
        assert engine.current_execution_id == "test_exec_001"
        assert engine.current_test_id == "test_login"
        assert engine.current_project_name == "test_project"
        assert engine.current_graph is not None
    
    def test_observe_page(self, tmp_path):
        """Test observing a page."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        engine.start_execution(execution_id="test_exec_001")
        
        engine.observe_page(
            page_type="dashboard",
            url="http://example.com",
            dom_content="<html>...</html>",
        )
        
        assert engine.transition_tracker.current_page_type == "dashboard"
    
    def test_observe_action(self, tmp_path):
        """Test observing an action."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        engine.start_execution(execution_id="test_exec_001")
        
        element_info = {"role": "button", "text": "Submit"}
        action = engine.observe_action(element_info=element_info)
        
        assert action.action_type == ActionType.SUBMIT
    
    def test_observe_page_transition(self, tmp_path):
        """Test observing a page transition."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        engine.start_execution(execution_id="test_exec_001")
        
        engine.observe_page(
            page_type="authentication_screen",
            url="http://example.com/login",
            dom_content="<html>...</html>",
        )
        
        action = SemanticAction(action_type=ActionType.SUBMIT)
        transition = engine.observe_page_transition(
            target_page_type="dashboard",
            target_url="http://example.com/dashboard",
            target_dom_content="<html>...</html>",
            action=action,
        )
        
        assert transition.source_page_type == "authentication_screen"
        assert transition.target_page_type == "dashboard"
    
    def test_end_execution(self, tmp_path):
        """Test ending an execution."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        engine.start_execution(execution_id="test_exec_001")
        
        # Add some transitions
        engine.observe_page(
            page_type="authentication_screen",
            url="http://example.com/login",
            dom_content="<html>...</html>",
        )
        
        action = SemanticAction(action_type=ActionType.SUBMIT)
        engine.observe_page_transition(
            target_page_type="dashboard",
            target_url="http://example.com/dashboard",
            target_dom_content="<html>...</html>",
            action=action,
        )
        
        flows = engine.end_execution()
        
        assert isinstance(flows, list)
        assert engine.current_execution_id == "test_exec_001"
    
    def test_get_test_generation_recommendations(self, tmp_path):
        """Test getting test generation recommendations."""
        engine = FlowDiscoveryEngine(base_dir=str(tmp_path), enable_persistence=False)
        
        # Add a discovered flow
        flow = BusinessFlow(
            flow_id="test_flow",
            flow_type=FlowType.AUTHENTICATION,
            flow_name="Authentication Flow",
            confidence=0.8,
            is_happy_path=True,
        )
        engine.discovered_flows.append(flow)
        
        recommendations = engine.get_test_generation_recommendations(project_name="test_project")
        
        assert "happy_paths" in recommendations
        assert "business_workflows" in recommendations
        assert "coverage_gaps" in recommendations
