"""Flow Persistence Manager - Persist discovered business flows.

This module manages the persistence of discovered business flows,
ensuring they survive across executions and can be used for
runtime learning, test generation, and healing.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowGraph,
)

logger = logging.getLogger(__name__)


class FlowPersistenceManager:
    """Manages persistence of discovered business flows.
    
    This manager:
    - Stores business flows in structured storage
    - Loads flows for reuse across executions
    - Updates flow statistics based on new observations
    - Maintains flow history and metadata
    - Integrates with existing runtime storage architecture
    """
    
    def __init__(
        self,
        base_dir: str = "phoenix_runtime",
        enable_persistence: bool = True,
    ):
        """Initialize the flow persistence manager.
        
        Args:
            base_dir: Base directory for storage
            enable_persistence: Enable flow persistence
        """
        self.base_dir = Path(base_dir)
        self.flow_storage_dir = self.base_dir / "business_flows"
        self.flow_storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_persistence = enable_persistence
        
        # In-memory cache
        self.flows_cache: Dict[str, BusinessFlow] = {}
        self.graphs_cache: Dict[str, FlowGraph] = {}
        
        logger.info(f"[FLOW PERSISTENCE] Initialized with storage: {self.flow_storage_dir}")
        logger.info(f"[FLOW PERSISTENCE] Persistence enabled: {enable_persistence}")
    
    def _get_project_storage_path(self, project_name: str) -> Path:
        """Get storage path for a specific project.
        
        Args:
            project_name: Project name
            
        Returns:
            Storage path for project
        """
        project_dir = self.flow_storage_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def store_flow(
        self,
        flow: BusinessFlow,
        project_name: str = "",
    ) -> None:
        """Store a business flow.
        
        Args:
            flow: Business flow to store
            project_name: Project name
        """
        if not self.enable_persistence:
            logger.debug("[FLOW PERSISTENCE] Persistence disabled, skipping storage")
            return
        
        project_dir = self._get_project_storage_path(project_name or flow.project_name)
        
        # Store individual flow
        flow_file = project_dir / f"flow_{flow.flow_id}.json"
        flow_file.write_text(flow.model_dump_json(indent=2), encoding='utf-8')
        
        # Update cache
        self.flows_cache[flow.flow_id] = flow
        
        logger.info(f"[FLOW PERSISTENCE] Stored flow: {flow.flow_id} ({flow.flow_type.value})")
    
    def store_graph(
        self,
        graph: FlowGraph,
        project_name: str = "",
    ) -> None:
        """Store a flow graph.
        
        Args:
            graph: Flow graph to store
            project_name: Project name
        """
        if not self.enable_persistence:
            logger.debug("[FLOW PERSISTENCE] Persistence disabled, skipping storage")
            return
        
        project_dir = self._get_project_storage_path(project_name or graph.project_name)
        
        # Store graph
        graph_file = project_dir / f"graph_{graph.graph_id}.json"
        graph_file.write_text(graph.model_dump_json(indent=2), encoding='utf-8')
        
        # Update cache
        self.graphs_cache[graph.graph_id] = graph
        
        logger.info(f"[FLOW PERSISTENCE] Stored graph: {graph.graph_id}")
    
    def load_flow(
        self,
        flow_id: str,
        project_name: str = "",
    ) -> Optional[BusinessFlow]:
        """Load a business flow.
        
        Args:
            flow_id: Flow ID
            project_name: Project name
            
        Returns:
            Business flow or None if not found
        """
        # Check cache first
        if flow_id in self.flows_cache:
            return self.flows_cache[flow_id]
        
        project_dir = self._get_project_storage_path(project_name)
        flow_file = project_dir / f"flow_{flow_id}.json"
        
        if not flow_file.exists():
            logger.warning(f"[FLOW PERSISTENCE] Flow not found: {flow_id}")
            return None
        
        try:
            flow_data = json.loads(flow_file.read_text(encoding='utf-8'))
            flow = BusinessFlow(**flow_data)
            
            # Update cache
            self.flows_cache[flow_id] = flow
            
            logger.info(f"[FLOW PERSISTENCE] Loaded flow: {flow_id}")
            
            return flow
        except Exception as e:
            logger.error(f"[FLOW PERSISTENCE] Failed to load flow {flow_id}: {e}")
            return None
    
    def load_graph(
        self,
        graph_id: str,
        project_name: str = "",
    ) -> Optional[FlowGraph]:
        """Load a flow graph.
        
        Args:
            graph_id: Graph ID
            project_name: Project name
            
        Returns:
            Flow graph or None if not found
        """
        # Check cache first
        if graph_id in self.graphs_cache:
            return self.graphs_cache[graph_id]
        
        project_dir = self._get_project_storage_path(project_name)
        graph_file = project_dir / f"graph_{graph_id}.json"
        
        if not graph_file.exists():
            logger.warning(f"[FLOW PERSISTENCE] Graph not found: {graph_id}")
            return None
        
        try:
            graph_data = json.loads(graph_file.read_text(encoding='utf-8'))
            graph = FlowGraph(**graph_data)
            
            # Update cache
            self.graphs_cache[graph_id] = graph
            
            logger.info(f"[FLOW PERSISTENCE] Loaded graph: {graph_id}")
            
            return graph
        except Exception as e:
            logger.error(f"[FLOW PERSISTENCE] Failed to load graph {graph_id}: {e}")
            return None
    
    def load_all_flows(
        self,
        project_name: str = "",
    ) -> List[BusinessFlow]:
        """Load all flows for a project.
        
        Args:
            project_name: Project name
            
        Returns:
            List of business flows
        """
        project_dir = self._get_project_storage_path(project_name)
        
        flows = []
        for flow_file in project_dir.glob("flow_*.json"):
            try:
                flow_data = json.loads(flow_file.read_text(encoding='utf-8'))
                flow = BusinessFlow(**flow_data)
                flows.append(flow)
                self.flows_cache[flow.flow_id] = flow
            except Exception as e:
                logger.warning(f"[FLOW PERSISTENCE] Failed to load flow from {flow_file}: {e}")
        
        logger.info(f"[FLOW PERSISTENCE] Loaded {len(flows)} flows for project {project_name}")
        
        return flows
    
    def update_flow_statistics(
        self,
        flow_id: str,
        success: bool,
        project_name: str = "",
    ) -> None:
        """Update flow statistics based on execution result.
        
        Args:
            flow_id: Flow ID
            success: Whether the execution was successful
            project_name: Project name
        """
        flow = self.load_flow(flow_id, project_name)
        
        if not flow:
            logger.warning(f"[FLOW PERSISTENCE] Cannot update non-existent flow: {flow_id}")
            return
        
        # Update statistics
        flow.total_observations += 1
        if success:
            flow.success_count += 1
        else:
            flow.failure_count += 1
        
        # Update confidence based on success rate
        if flow.total_observations > 0:
            success_rate = flow.success_count / flow.total_observations
            flow.confidence = (flow.confidence * 0.7) + (success_rate * 0.3)
        
        # Update timestamp
        flow.last_observed = datetime.now(timezone.utc).isoformat()
        
        # Store updated flow
        self.store_flow(flow, project_name)
        
        logger.debug(f"[FLOW PERSISTENCE] Updated statistics for flow {flow_id}: success={success}")
    
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
        flows = self.load_all_flows(project_name)
        return [f for f in flows if f.flow_type.value == flow_type]
    
    def get_high_confidence_flows(
        self,
        min_confidence: float = 0.7,
        project_name: str = "",
    ) -> List[BusinessFlow]:
        """Get high-confidence flows.
        
        Args:
            min_confidence: Minimum confidence threshold
            project_name: Project name
            
        Returns:
            List of high-confidence flows
        """
        flows = self.load_all_flows(project_name)
        return [f for f in flows if f.confidence >= min_confidence]
    
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
        flows = self.load_all_flows(project_name)
        return [f for f in flows if f.is_happy_path]
    
    def delete_flow(
        self,
        flow_id: str,
        project_name: str = "",
    ) -> bool:
        """Delete a flow.
        
        Args:
            flow_id: Flow ID
            project_name: Project name
            
        Returns:
            True if deleted successfully
        """
        project_dir = self._get_project_storage_path(project_name)
        flow_file = project_dir / f"flow_{flow_id}.json"
        
        if flow_file.exists():
            flow_file.unlink()
            
            # Remove from cache
            if flow_id in self.flows_cache:
                del self.flows_cache[flow_id]
            
            logger.info(f"[FLOW PERSISTENCE] Deleted flow: {flow_id}")
            return True
        
        return False
    
    def clear_project_flows(
        self,
        project_name: str = "",
    ) -> None:
        """Clear all flows for a project.
        
        Args:
            project_name: Project name
        """
        project_dir = self._get_project_storage_path(project_name)
        
        for flow_file in project_dir.glob("flow_*.json"):
            flow_file.unlink()
        
        for graph_file in project_dir.glob("graph_*.json"):
            graph_file.unlink()
        
        # Clear cache
        self.flows_cache.clear()
        self.graphs_cache.clear()
        
        logger.info(f"[FLOW PERSISTENCE] Cleared all flows for project {project_name}")
    
    def get_flow_statistics(
        self,
        project_name: str = "",
    ) -> Dict[str, Any]:
        """Get flow statistics for a project.
        
        Args:
            project_name: Project name
            
        Returns:
            Flow statistics
        """
        flows = self.load_all_flows(project_name)
        
        if not flows:
            return {
                "total_flows": 0,
                "flow_types": {},
                "avg_confidence": 0.0,
                "high_confidence_count": 0,
                "happy_path_count": 0,
            }
        
        stats = {
            "total_flows": len(flows),
            "flow_types": {},
            "avg_confidence": sum(f.confidence for f in flows) / len(flows),
            "high_confidence_count": sum(1 for f in flows if f.confidence >= 0.7),
            "happy_path_count": sum(1 for f in flows if f.is_happy_path),
        }
        
        # Count flow types
        for flow in flows:
            flow_type = flow.flow_type.value
            stats["flow_types"][flow_type] = stats["flow_types"].get(flow_type, 0) + 1
        
        return stats
