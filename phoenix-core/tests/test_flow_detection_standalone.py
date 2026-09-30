"""Standalone unit tests for Flow Detection Module (Priority 21).

These tests avoid the full Phoenix import chain to work around the sqlite3 DLL issue.
They directly test the flow detection components.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add phoenix-core to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def test_basic_functionality():
    """Test basic flow detection functionality."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Test SemanticAction
        action = SemanticAction(action_type=ActionType.CLICK, confidence=0.8)
        assert action.action_type == ActionType.CLICK
        assert action.confidence == 0.8
        
        # Test PageTransitionTracker
        tracker = PageTransitionTracker(base_dir=temp_dir, enable_persistence=False)
        tracker.set_current_page('dashboard', 'http://example.com', '<html>...</html>')
        assert tracker.current_page_type == 'dashboard'
        
        # Test FlowGraphBuilder
        builder = FlowGraphBuilder()
        graph = builder.create_graph(project_name='test')
        assert graph.graph_id.startswith('graph_')
        
        # Test FlowReasoningEngine
        engine = FlowReasoningEngine(enable_ai_reasoning=False)
        semantic_types = ['authentication_screen', 'dashboard']
        action_types = [ActionType.SUBMIT]
        flow_type, confidence = engine._classify_flow_pattern(semantic_types, action_types)
        assert flow_type == FlowType.AUTHENTICATION
        assert confidence >= 0.8
        
        # Test FlowDiscoveryEngine
        discovery = FlowDiscoveryEngine(base_dir=temp_dir, enable_persistence=False)
        discovery.start_execution('test_exec', 'test', 'test_project')
        discovery.observe_page('dashboard', 'http://example.com', '<html>...</html>')
        assert discovery.current_execution_id == 'test_exec'
        
        print("[PASS] All basic functionality tests passed")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_flow_classification():
    """Test flow classification patterns."""
    engine = FlowReasoningEngine(enable_ai_reasoning=False)
    
    test_cases = [
        (['authentication_screen', 'dashboard'], [ActionType.SUBMIT], FlowType.AUTHENTICATION),
        (['search_screen', 'table_view'], [ActionType.SEARCH], FlowType.SEARCH_FLOW),
        (['table_view', 'crud_form'], [ActionType.CREATE, ActionType.SUBMIT], FlowType.CRUD_CREATE),
        (['table_view', 'crud_form'], [ActionType.EDIT, ActionType.SUBMIT], FlowType.CRUD_UPDATE),
    ]
    
    for semantic_types, action_types, expected_type in test_cases:
        flow_type, confidence = engine._classify_flow_pattern(semantic_types, action_types)
        assert flow_type == expected_type, f"Expected {expected_type}, got {flow_type}"
        assert confidence >= 0.7, f"Confidence too low: {confidence}"
    
    print("[PASS] Flow classification tests passed")


def test_action_classification():
    """Test generic action classification."""
    tracker = PageTransitionTracker(base_dir=tempfile.mkdtemp(), enable_persistence=False)
    
    test_cases = [
        ({"role": "button", "text": "Submit"}, ActionType.SUBMIT),
        ({"role": "button", "text": "Save"}, ActionType.SUBMIT),
        ({"role": "button", "text": "Create"}, ActionType.CREATE),
        ({"role": "button", "text": "Delete"}, ActionType.DELETE),
        ({"role": "button", "text": "Cancel"}, ActionType.CANCEL),
    ]
    
    for element_info, expected_type in test_cases:
        action = tracker.infer_action_from_dom_change(
            previous_dom="<html>...</html>",
            current_dom="<html>...</html>",
            element_info=element_info,
        )
        assert action.action_type == expected_type, f"Expected {expected_type}, got {action.action_type}"
    
    print("[PASS] Action classification tests passed")


def test_flow_graph_operations():
    """Test flow graph operations."""
    graph = FlowGraph(graph_id="test_graph", project_name="test_project")
    
    # Add nodes
    node1 = FlowNode(node_id="n1", semantic_type="authentication_screen")
    node2 = FlowNode(node_id="n2", semantic_type="dashboard")
    
    graph.add_node(node1)
    graph.add_node(node2)
    
    assert graph.total_nodes == 2
    assert len(graph.nodes) == 2
    
    # Add edge
    edge = FlowEdge(
        edge_id="e1",
        source_node_id="n1",
        target_node_id="n2",
        action=SemanticAction(action_type=ActionType.SUBMIT),
    )
    
    graph.add_edge(edge)
    
    assert graph.total_edges == 1
    assert len(graph.edges) == 1
    
    # Add flow
    flow = BusinessFlow(
        flow_id="f1",
        flow_type=FlowType.AUTHENTICATION,
        nodes=[node1, node2],
        edges=[edge],
    )
    
    graph.add_flow(flow)
    
    assert graph.total_flows == 1
    assert len(graph.flows) == 1
    
    print("[PASS] Flow graph operations tests passed")


def test_transition_tracking():
    """Test page transition tracking."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        tracker = PageTransitionTracker(base_dir=temp_dir, enable_persistence=False)
        
        # Set initial page
        tracker.set_current_page(
            page_type="authentication_screen",
            url="http://example.com/login",
            dom_content="<html>...</html>",
        )
        
        # Record transition
        action = SemanticAction(action_type=ActionType.SUBMIT)
        transition = tracker.record_transition(
            target_page_type="dashboard",
            target_url="http://example.com/dashboard",
            target_dom_content="<html>...</html>",
            action=action,
            execution_id="test_exec",
            project_name="test_project",
        )
        
        assert transition.source_page_type == "authentication_screen"
        assert transition.target_page_type == "dashboard"
        assert len(tracker.transitions) == 1
        
        # Get transitions
        transitions = tracker.get_transitions(project_name="test_project")
        assert len(transitions) == 1
        
        # Get patterns
        patterns = tracker.get_transition_patterns(project_name="test_project")
        assert patterns["total_transitions"] == 1
        assert "authentication_screen" in patterns["unique_page_types"]
        
        print("[PASS] Transition tracking tests passed")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_flow_discovery_pipeline():
    """Test complete flow discovery pipeline."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        discovery = FlowDiscoveryEngine(base_dir=temp_dir, enable_persistence=False)
        
        # Start execution
        discovery.start_execution(
            execution_id="pipeline_test",
            test_id="test_pipeline",
            project_name="pipeline_test",
        )
        
        # Simulate authentication flow
        discovery.observe_page(
            page_type="authentication_screen",
            url="http://example.com/login",
            dom_content="<html>...</html>",
        )
        
        action = discovery.observe_action(
            element_info={"role": "button", "text": "Submit"}
        )
        
        transition = discovery.observe_page_transition(
            target_page_type="dashboard",
            target_url="http://example.com/dashboard",
            target_dom_content="<html>...</html>",
            action=action,
        )
        
        # End execution
        flows = discovery.end_execution()
        
        assert isinstance(flows, list)
        assert discovery.current_graph is not None
        assert discovery.current_graph.total_nodes >= 2
        assert discovery.current_graph.total_edges >= 1
        
        print("[PASS] Flow discovery pipeline tests passed")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_flow_persistence():
    """Test flow persistence."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = FlowPersistenceManager(base_dir=temp_dir)
        
        # Store flow
        flow = BusinessFlow(
            flow_id="test_flow",
            flow_type=FlowType.AUTHENTICATION,
            flow_name="Test Flow",
            project_name="test_project",
        )
        
        manager.store_flow(flow, project_name="test_project")
        
        # Load flow
        loaded_flow = manager.load_flow("test_flow", project_name="test_project")
        
        assert loaded_flow is not None
        assert loaded_flow.flow_id == "test_flow"
        assert loaded_flow.flow_type == FlowType.AUTHENTICATION
        
        # Update statistics
        manager.update_flow_statistics("test_flow", success=True, project_name="test_project")
        
        updated_flow = manager.load_flow("test_flow", project_name="test_project")
        assert updated_flow.total_observations == 1
        assert updated_flow.success_count == 1
        
        # Get statistics
        stats = manager.get_flow_statistics(project_name="test_project")
        assert stats["total_flows"] == 1
        
        print("[PASS] Flow persistence tests passed")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Running standalone flow detection tests...\n")
    
    test_basic_functionality()
    test_flow_classification()
    test_action_classification()
    test_flow_graph_operations()
    test_transition_tracking()
    test_flow_discovery_pipeline()
    test_flow_persistence()
    
    print("\n[PASS] All standalone tests passed!")
