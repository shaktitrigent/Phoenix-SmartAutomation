"""Intelligent Runtime - Self-Learning Execution Engine.

This module integrates all intelligent components into the Phoenix runtime
to create a self-learning execution engine that automatically consumes
previous intelligence and improves every execution.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add try-except for semantic module imports to handle missing dependencies gracefully
try:
    from phoenix.semantic.semantic_integrator import SemanticIntegrator
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    SemanticIntegrator = None

logger = logging.getLogger(__name__)

from phoenix.execution.artifacts import get_artifacts_manager
from phoenix.execution.intelligent_cache import IntelligentDOMCache
from phoenix.execution.dom_snapshot_manager import DOMSnapshotManager
from phoenix.execution.locator_repository import LocatorRepository
from phoenix.execution.dom_diff import DOMDifferenceEngine
from phoenix.execution.runtime_metrics import RuntimeMetricsCollector
from phoenix.execution.runtime_timeline import RuntimeTimelineTracker
from phoenix.execution.healing import HealingEngine

# Conditional imports for semantic modules
if SEMANTIC_AVAILABLE:
    from phoenix.semantic.semantic_integrator import SemanticIntegrator
from phoenix.flow_detection.flow_discovery import FlowDiscoveryEngine


class DecisionReason(Enum):
    """Reasons for intelligent decisions."""
    DOM_UNCHANGED = "DOM unchanged"
    DOM_CHANGED = "DOM changed"
    LOCATOR_HIGH_CONFIDENCE = "Locator confidence high"
    LOCATOR_LOW_CONFIDENCE = "Locator confidence low"
    LOCATOR_NOT_FOUND = "Locator not found"
    CACHE_HIT = "Cache hit"
    CACHE_MISS = "Cache miss"
    HEALING_AVAILABLE = "Healing available"
    HEALING_NOT_AVAILABLE = "Healing not available"
    FIRST_EXECUTION = "First execution"
    IMPROVEMENT_DETECTED = "Improvement detected"


@dataclass
class IntelligentDecision:
    """Record of an intelligent decision made during execution."""
    decision_type: str
    decision: str
    reason: DecisionReason
    evidence: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ExecutionDelta:
    """Comparison between current and previous execution."""
    previous_execution_id: Optional[str]
    current_execution_id: str
    time_saved_ms: float
    dom_cache_hit_count: int
    dom_cache_miss_count: int
    locator_reuse_count: int
    locator_generation_count: int
    healing_attempts: int
    healing_successes: int
    mcp_calls_saved: int
    llm_calls_saved: int
    improvement_percentage: float


@dataclass
class RuntimeEvidence:
    """Complete runtime evidence for an execution."""
    execution_id: str
    project_name: str
    test_name: str
    timestamp: str
    
    # Artifacts loaded
    artifacts_loaded: List[str] = field(default_factory=list)
    
    # Artifacts reused
    artifacts_reused: List[str] = field(default_factory=list)
    
    # Artifacts updated
    artifacts_updated: List[str] = field(default_factory=list)
    
    # Artifacts created
    artifacts_created: List[str] = field(default_factory=list)
    
    # Cache statistics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_ratio: float = 0.0
    
    # Locator statistics
    locator_reuse_count: int = 0
    locator_generation_count: int = 0
    locator_reuse_ratio: float = 0.0
    
    # Healing statistics
    healing_attempts: int = 0
    healing_successes: int = 0
    healing_failures: int = 0
    healing_success_rate: float = 0.0
    
    # DOM statistics
    dom_reuse_count: int = 0
    dom_generation_count: int = 0
    dom_reuse_ratio: float = 0.0
    
    # Time savings
    time_saved_ms: float = 0.0
    time_saved_percentage: float = 0.0
    
    # Call savings
    mcp_calls_saved: int = 0
    llm_calls_saved: int = 0
    
    # Intelligence decisions
    decisions: List[IntelligentDecision] = field(default_factory=list)
    
    # Execution delta
    execution_delta: Optional[ExecutionDelta] = None
    
    # Confidence scores
    confidence_score: float = 0.0
    automation_score: float = 0.0


class IntelligentRuntime:
    """Self-learning execution engine with integrated intelligence."""
    
    def __init__(
        self,
        base_dir: str = "phoenix_runtime",
        project_name: str = "default",
        enable_cache: bool = True,
        enable_repository: bool = True,
        enable_diff: bool = True,
        enable_healing: bool = True,
        enable_metrics: bool = True,
        enable_timeline: bool = True,
        enable_semantic: bool = True,
    ):
        """Initialize intelligent runtime with unified storage architecture."""
        self.base_dir = Path(base_dir)
        self.project_name = project_name
        
        # Create unified storage architecture
        self._create_storage_structure()
        
        # Initialize artifacts manager
        self.artifacts_manager = get_artifacts_manager(base_dir=str(self.base_dir / "artifacts"))
        
        # Initialize DOM Snapshot Manager for permanent storage with configurable validation
        self.dom_snapshot_manager = DOMSnapshotManager(
            base_dir=str(self.base_dir),
            min_dom_size_bytes=100,  # Configurable minimum DOM size
            enable_size_validation=True  # Enable size validation
        ) if enable_cache else None
        
        # Initialize intelligent components
        self.dom_cache = IntelligentDOMCache(
            cache_dir=str(self.base_dir / "dom_cache"),
            ttl_seconds=3600,
            artifacts_manager=self.artifacts_manager
        ) if enable_cache else None
        
        self.locator_repository = LocatorRepository(
            repository_dir=str(self.base_dir / "locator_repository"),
            artifacts_manager=self.artifacts_manager
        ) if enable_repository else None
        
        self.dom_diff_engine = DOMDifferenceEngine(
            artifacts_manager=self.artifacts_manager
        ) if enable_diff else None
        
        # Initialize DOM evidence collector for intelligent healing
        self.dom_evidence_collector = None
        if enable_healing:
            try:
                from phoenix.execution.dom_evidence_collector import DOMEvidenceCollector
                self.dom_evidence_collector = DOMEvidenceCollector()
                logger.info("[INTELLIGENT RUNTIME] DOM Evidence Collector initialized for intelligent healing")
            except ImportError as e:
                logger.warning(f"[INTELLIGENT RUNTIME] Could not initialize DOM Evidence Collector: {e}")
        
        self.healing_engine = HealingEngine(
            locator_registry=self.locator_repository,
            dom_evidence_collector=self.dom_evidence_collector
        ) if enable_healing else None
        
        self.metrics_collector = RuntimeMetricsCollector(
            artifacts_manager=self.artifacts_manager
        ) if enable_metrics else None
        
        self.timeline_tracker = RuntimeTimelineTracker(
            artifacts_manager=self.artifacts_manager
        ) if enable_timeline else None
        
        # Initialize Semantic Understanding (Priority 20 + Priority 22)
        self.semantic_integrator = None
        if enable_semantic and SEMANTIC_AVAILABLE:
            try:
                self.semantic_integrator = SemanticIntegrator(
                    base_dir=str(self.base_dir),
                    enable_page_classification=enable_semantic,
                    enable_component_analysis=enable_semantic,
                    enable_intent_detection=enable_semantic,
                    enable_navigation_analysis=enable_semantic,
                    enable_component_intelligence=enable_semantic,  # Priority 22: Universal Component Intelligence
                )
            except Exception as e:
                logger.warning(f"[INTELLIGENT RUNTIME] Failed to initialize SemanticIntegrator: {e}")
                self.semantic_integrator = None
        
        # Initialize Flow Detection (Priority 21)
        self.flow_discovery = FlowDiscoveryEngine(
            base_dir=str(self.base_dir),
            enable_persistence=True,
            enable_ai_reasoning=enable_semantic,
            enable_flow_learning=True,
        ) if enable_semantic else None
        
        # Link flow discovery to healing engine for flow-aware healing
        if self.healing_engine and self.flow_discovery:
            self.healing_engine.flow_discovery = self.flow_discovery
        
        # Link DOM evidence collector with page when available
        if self.dom_evidence_collector:
            # This will be set during execution when page is available
            self._setup_dom_evidence_integration()
        
        # Runtime state
        self.execution_id: Optional[str] = None
        self.test_name: Optional[str] = None
        self.runtime_evidence: Optional[RuntimeEvidence] = None
        self.previous_execution: Optional[Dict[str, Any]] = None
        self.semantic_page: Optional[Any] = None  # Store semantic understanding
        
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Base directory: {self.base_dir}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Project name: {self.project_name}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - DOM Snapshot Manager: {self.dom_snapshot_manager is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Locator Repository: {self.locator_repository is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Healing Engine: {self.healing_engine is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Metrics Collector: {self.metrics_collector is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Timeline Tracker: {self.timeline_tracker is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Semantic Integrator: {self.semantic_integrator is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Flow Discovery: {self.flow_discovery is not None}")
        logger.info(f"[INTELLIGENT RUNTIME] CREATED - Priority 22 Component Intelligence: {enable_semantic}")
        self.headed_mode = False  # Track headed mode for enhanced logging
    
    def _setup_dom_evidence_integration(self):
        """Setup DOM evidence collector integration with page when available."""
        # This will be called during execution when the page is available
        # For now, we'll set up the infrastructure
        logger.info("[INTELLIGENT RUNTIME] DOM evidence integration infrastructure set up")
    
    def set_page_for_dom_evidence(self, page):
        """Set the Playwright page for DOM evidence collection.
        
        Args:
            page: Playwright Page object
        """
        if self.dom_evidence_collector:
            self.dom_evidence_collector.set_page(page)
            logger.info("[INTELLIGENT RUNTIME] Page set for DOM evidence collection")
    
    def set_headed_mode(self, enabled: bool = True):
        """Enable or disable headed mode for enhanced logging.
        
        Args:
            enabled: Whether headed mode is enabled
        """
        self.headed_mode = enabled
        if enabled:
            logger.info("[HEADED MODE] Browser visible - Enhanced logging enabled")
        else:
            logger.info("[HEADLESS MODE] Standard logging")
    
    def record_component_interaction(
        self,
        component: Any,
        interaction_result: str,
        locator_used: str = "",
        error_message: str = "",
    ) -> None:
        """Record component interaction result for runtime learning (Priority 22).
        
        Args:
            component: Semantic component that was interacted with
            interaction_result: Result of interaction (success, failure, timeout, etc.)
            locator_used: Locator that was used
            error_message: Error message if interaction failed
        """
        if not component:
            return
        
        # Update component runtime statistics
        if hasattr(component, 'success_count') and hasattr(component, 'failure_count'):
            if interaction_result == "success":
                component.success_count += 1
                component.last_seen = datetime.now(timezone.utc).isoformat()
                
                # Update locator confidence if locator repository is available
                if self.locator_repository and locator_used:
                    self.locator_repository.record_success(
                        project_name=self.project_name,
                        page_name=self.test_name or "unknown",
                        element_name=component.component_id or component.name or "unknown",
                    )
                    
                if self.headed_mode:
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Component interaction SUCCESS: {component.component_id}")
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Success count: {component.success_count}")
                    
            else:
                component.failure_count += 1
                component.runtime_observations.append({
                    "result": interaction_result,
                    "locator": locator_used,
                    "error": error_message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                
                # Update locator confidence if locator repository is available
                if self.locator_repository and locator_used:
                    self.locator_repository.record_failure(
                        project_name=self.project_name,
                        page_name=self.test_name or "unknown",
                        element_name=component.component_id or component.name or "unknown",
                    )
                
                if self.headed_mode:
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Component interaction FAILURE: {component.component_id}")
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Failure count: {component.failure_count}")
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Error: {error_message}")
        
        # Update component confidence based on success rate
        if hasattr(component, 'success_count') and hasattr(component, 'failure_count'):
            total = component.success_count + component.failure_count
            if total > 0:
                success_rate = component.success_count / total
                # Update confidence with learning
                if hasattr(component, 'confidence'):
                    component.confidence = min(component.confidence + (success_rate - 0.5) * 0.1, 1.0)
                    component.confidence = max(component.confidence, 0.0)
                    
                if self.headed_mode:
                    logger.info(f"[HEADED MODE] [RUNTIME LEARNING] Updated component confidence: {component.confidence:.2f}")
        
    def _create_storage_structure(self):
        """Create unified enterprise-grade storage architecture."""
        directories = [
            self.base_dir,
            self.base_dir / "artifacts",
            self.base_dir / "dom_cache",
            self.base_dir / "locator_repository",
            self.base_dir / "healing_repository",
            self.base_dir / "execution_history",
            self.base_dir / "intelligence_dashboard",
            self.base_dir / "runtime_reports",
            self.base_dir / "semantic_understanding",  # Priority 20: Semantic Understanding
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def start_execution(self, test_name: str) -> str:
        """Start a new intelligent execution with comprehensive pipeline logging."""
        # Comprehensive pipeline logging
        print(f"[PHOENIX] === EXECUTION PIPELINE STARTED ===")
        print(f"[PHOENIX] Test: {test_name}")
        print(f"[PHOENIX] Project: {self.project_name}")
        print(f"[PHOENIX] Timestamp: {datetime.now(timezone.utc).isoformat()}")
        
        logger.info(f"[PHOENIX PIPELINE] Execution started for test: {test_name}")
        logger.info(f"[PHOENIX PIPELINE] Project: {self.project_name}")
        
        # Start run
        self.execution_id = self.artifacts_manager.start_run()
        self.test_name = test_name
        
        print(f"[PHOENIX] Execution ID: {self.execution_id}")
        logger.info(f"[PHOENIX PIPELINE] Execution ID: {self.execution_id}")
        
        # Log component status
        print(f"[PHOENIX] === INTELLIGENT COMPONENTS STATUS ===")
        print(f"[PHOENIX] DOM Snapshot Manager: {'ENABLED' if self.dom_snapshot_manager else 'DISABLED'}")
        print(f"[PHOENIX] DOM Cache: {'ENABLED' if self.dom_cache else 'DISABLED'}")
        print(f"[PHOENIX] Locator Repository: {'ENABLED' if self.locator_repository else 'DISABLED'}")
        print(f"[PHOENIX] DOM Difference Engine: {'ENABLED' if self.dom_diff_engine else 'DISABLED'}")
        print(f"[PHOENIX] Healing Engine: {'ENABLED' if self.healing_engine else 'DISABLED'}")
        print(f"[PHOENIX] Metrics Collector: {'ENABLED' if self.metrics_collector else 'DISABLED'}")
        print(f"[PHOENIX] Timeline Tracker: {'ENABLED' if self.timeline_tracker else 'DISABLED'}")
        
        # Initialize runtime evidence
        self.runtime_evidence = RuntimeEvidence(
            execution_id=self.execution_id,
            project_name=self.project_name,
            test_name=test_name,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        print(f"[PHOENIX] Runtime Evidence Tracking: ENABLED")
        
        # Load previous execution data
        self._load_previous_execution()
        
        # Start tracking
        if self.timeline_tracker:
            self.timeline_tracker.start_timeline(self.execution_id, test_name)
            print(f"[PHOENIX] Timeline Tracking: STARTED")
        
        if self.metrics_collector:
            self.metrics_collector.start_collection(self.execution_id, test_name)
            print(f"[PHOENIX] Metrics Collection: STARTED")
        
        # Initialize DOM snapshot manager with execution ID for evidence tracking
        if self.dom_snapshot_manager:
            logger.info(f"[PHOENIX PIPELINE] DOM Snapshot Manager ready for execution {self.execution_id}")
            print(f"[PHOENIX] DOM Snapshot Manager: READY")
        
        # Start flow discovery (Priority 21)
        if self.flow_discovery:
            self.flow_discovery.start_execution(
                execution_id=self.execution_id,
                test_id=test_name,
                project_name=self.project_name,
            )
            logger.info(f"[PHOENIX PIPELINE] Flow Discovery started for execution {self.execution_id}")
            print(f"[PHOENIX] Flow Discovery: STARTED")
        
        # Record decision
        self._record_decision(
            decision_type="execution_start",
            decision="Start intelligent execution",
            reason=DecisionReason.FIRST_EXECUTION if not self.previous_execution else DecisionReason.IMPROVEMENT_DETECTED,
            evidence={"previous_execution": self.previous_execution is not None}
        )
        
        print(f"[PHOENIX] === EXECUTION PIPELINE READY ===")
        
        return self.execution_id
    
    def _load_previous_execution(self):
        """Automatically load previous execution artifacts."""
        execution_history_dir = self.base_dir / "execution_history"
        
        if not execution_history_dir.exists():
            return
        
        # Find most recent execution
        executions = sorted(execution_history_dir.glob("*.json"), reverse=True)
        
        if executions:
            try:
                with open(executions[0], 'r', encoding='utf-8') as f:
                    self.previous_execution = json.load(f)
                    self.runtime_evidence.artifacts_loaded.append(str(executions[0]))
            except Exception:
                self.previous_execution = None
    
    def make_intelligent_decision(
        self,
        decision_type: str,
        context: Dict[str, Any]
    ) -> Tuple[str, DecisionReason, Dict[str, Any]]:
        """Make intelligent decision based on available intelligence."""
        decision = "execute"
        reason = DecisionReason.FIRST_EXECUTION
        evidence = {}
        
        if decision_type == "dom_capture":
            decision, reason, evidence = self._decide_dom_capture(context)
        elif decision_type == "locator_generation":
            decision, reason, evidence = self._decide_locator_generation(context)
        elif decision_type == "healing":
            decision, reason, evidence = self._decide_healing(context)
        
        # Record decision
        self._record_decision(decision_type, decision, reason, evidence)
        
        return decision, reason, evidence
    
    def _decide_dom_capture(self, context: Dict[str, Any]) -> Tuple[str, DecisionReason, Dict[str, Any]]:
        """Decide whether to capture new DOM or reuse from permanent storage."""
        # Use DOM Snapshot Manager for permanent storage decisions
        if self.dom_snapshot_manager:
            url = context.get("url")
            project = context.get("project_name", self.project_name)
            page = context.get("page_name", self.test_name)
            current_dom = context.get("current_dom")
            
            if not url:
                return "capture", DecisionReason.FIRST_EXECUTION, {}
            
            # Make reuse decision using permanent storage
            reuse_decision = self.dom_snapshot_manager.should_reuse_dom(
                url=url,
                project=project,
                page=page,
                current_dom=current_dom
            )
            
            if reuse_decision.decision == "REUSE":
                self.runtime_evidence.artifacts_reused.append("dom_snapshot")
                self.runtime_evidence.cache_hits += 1
                self.runtime_evidence.dom_reuse_count += 1
                self.runtime_evidence.time_saved_ms += reuse_decision.time_saved_ms
                self.runtime_evidence.mcp_calls_saved += 1
                
                # Record time saved in metrics
                if self.metrics_collector:
                    self.metrics_collector.record_time_saved(reuse_decision.time_saved_ms)
                
                return "reuse", DecisionReason.CACHE_HIT, {
                    "time_saved_ms": reuse_decision.time_saved_ms,
                    "reason": reuse_decision.reason,
                    "previous_hash": reuse_decision.previous_hash
                }
            else:
                self.runtime_evidence.cache_misses += 1
                self.runtime_evidence.dom_generation_count += 1
                
                return "capture", DecisionReason.CACHE_MISS, {
                    "reason": reuse_decision.reason,
                    "previous_hash": reuse_decision.previous_hash
                }
        
        # Fallback to in-memory cache
        if not self.dom_cache:
            return "capture", DecisionReason.FIRST_EXECUTION, {}
        
        url = context.get("url")
        current_dom = context.get("current_dom")
        
        if not url:
            return "capture", DecisionReason.FIRST_EXECUTION, {}
        
        # Check cache
        cached_dom, cache_status = self.dom_cache.get(url, current_dom=current_dom)
        
        if cache_status.status == "HIT":
            self.runtime_evidence.artifacts_reused.append("dom_cache")
            self.runtime_evidence.cache_hits += 1
            self.runtime_evidence.dom_reuse_count += 1
            self.runtime_evidence.time_saved_ms += cache_status.duration_ms
            self.runtime_evidence.mcp_calls_saved += 1
            
            # Record time saved in metrics
            if self.metrics_collector:
                self.metrics_collector.record_time_saved(cache_status.duration_ms)
            
            return "reuse", DecisionReason.CACHE_HIT, {
                "time_saved_ms": cache_status.duration_ms,
                "cache_age": cache_status.reason
            }
        else:
            self.runtime_evidence.cache_misses += 1
            self.runtime_evidence.dom_generation_count += 1
            
            return "capture", DecisionReason.CACHE_MISS, {
                "reason": cache_status.reason
            }
    
    def _decide_locator_generation(self, context: Dict[str, Any]) -> Tuple[str, DecisionReason, Dict[str, Any]]:
        """Decide whether to generate new locator or reuse existing.
        
        Priority 22: Use component intelligence for locator selection when available.
        """
        if not self.locator_repository:
            return "generate", DecisionReason.FIRST_EXECUTION, {}
        
        project_name = context.get("project_name", self.project_name)
        page_name = context.get("page_name")
        element_name = context.get("element_name")
        min_confidence = context.get("min_confidence", 0.7)
        
        # Priority 22: Check if component intelligence is available
        component = context.get("semantic_component")
        if component and hasattr(component, 'locator_candidates') and component.locator_candidates:
            # Use Priority 22 locator intelligence
            self.runtime_evidence.artifacts_reused.append("component_intelligence")
            self.runtime_evidence.locator_reuse_count += 1
            self.runtime_evidence.llm_calls_saved += 1
            
            time_saved = 1000.0  # Component intelligence is faster than LLM
            self.runtime_evidence.time_saved_ms += time_saved
            
            if self.headed_mode:
                logger.info(f"[HEADED MODE] [COMPONENT INTELLIGENCE] Using locator from component: {component.selected_locator}")
                logger.info(f"[HEADED MODE] [COMPONENT INTELLIGENCE] Locator confidence: {component.locator_confidence:.2f}")
                logger.info(f"[HEADED MODE] [COMPONENT INTELLIGENCE] Component purpose: {component.semantic_purpose}")
            
            if self.metrics_collector:
                self.metrics_collector.record_time_saved(time_saved)
            
            return "reuse", DecisionReason.LOCATOR_HIGH_CONFIDENCE, {
                "confidence": component.locator_confidence,
                "locator": component.selected_locator,
                "strategy": "component_intelligence",
                "time_saved_ms": time_saved
            }
        
        # Fallback to standard repository lookup
        if not all([page_name, element_name]):
            return "generate", DecisionReason.FIRST_EXECUTION, {}
        
        # Check repository
        locator = self.locator_repository.get_locator(
            project_name, page_name, element_name, min_confidence
        )
        
        if locator:
            self.runtime_evidence.artifacts_reused.append("locator_repository")
            self.runtime_evidence.locator_reuse_count += 1
            self.runtime_evidence.llm_calls_saved += 1
            
            # Assume 1-2 seconds saved per locator reuse
            time_saved = 1500.0  # Average LLM call time
            self.runtime_evidence.time_saved_ms += time_saved
            
            # Record time saved in metrics
            if self.metrics_collector:
                self.metrics_collector.record_time_saved(time_saved)
            
            return "reuse", DecisionReason.LOCATOR_HIGH_CONFIDENCE, {
                "confidence": locator.confidence,
                "success_count": locator.success_count,
                "locator": locator.locator,
                "time_saved_ms": time_saved
            }
        else:
            self.runtime_evidence.locator_generation_count += 1
            
            return "generate", DecisionReason.LOCATOR_NOT_FOUND, {
                "reason": "Locator not found in repository"
            }
    
    def _decide_healing(self, context: Dict[str, Any]) -> Tuple[str, DecisionReason, Dict[str, Any]]:
        """Decide whether to attempt healing."""
        if not self.healing_engine:
            return "skip", DecisionReason.HEALING_NOT_AVAILABLE, {}
        
        # Always attempt healing if enabled
        return "attempt", DecisionReason.HEALING_AVAILABLE, {
            "enabled": True
        }
    
    def _record_decision(self, decision_type: str, decision: str, reason: DecisionReason, evidence: Dict[str, Any]):
        """Record an intelligent decision."""
        decision_record = IntelligentDecision(
            decision_type=decision_type,
            decision=decision,
            reason=reason,
            evidence=evidence
        )
        self.runtime_evidence.decisions.append(decision_record)
    
    def record_artifact(self, artifact_type: str, action: str, path: str):
        """Record artifact action (loaded, reused, updated, created)."""
        if action == "loaded":
            self.runtime_evidence.artifacts_loaded.append(path)
        elif action == "reused":
            self.runtime_evidence.artifacts_reused.append(path)
        elif action == "updated":
            self.runtime_evidence.artifacts_updated.append(path)
        elif action == "created":
            self.runtime_evidence.artifacts_created.append(path)
    
    def end_execution(self, status: str = "passed") -> RuntimeEvidence:
        """End execution and generate complete runtime evidence."""
        logger.info(f"[INTELLIGENT RUNTIME] Ending execution with status: {status}")
        logger.info(f"[INTELLIGENT RUNTIME] Final evidence - dom_reuse_count: {self.runtime_evidence.dom_reuse_count}, dom_generation_count: {self.runtime_evidence.dom_generation_count}")
        logger.info(f"[INTELLIGENT RUNTIME] Final evidence - cache_hits: {self.runtime_evidence.cache_hits}, cache_misses: {self.runtime_evidence.cache_misses}")
        
        # Calculate ratios
        total_cache_ops = self.runtime_evidence.cache_hits + self.runtime_evidence.cache_misses
        if total_cache_ops > 0:
            self.runtime_evidence.cache_hit_ratio = self.runtime_evidence.cache_hits / total_cache_ops
        
        total_locator_ops = self.runtime_evidence.locator_reuse_count + self.runtime_evidence.locator_generation_count
        if total_locator_ops > 0:
            self.runtime_evidence.locator_reuse_ratio = self.runtime_evidence.locator_reuse_count / total_locator_ops
        
        total_dom_ops = self.runtime_evidence.dom_reuse_count + self.runtime_evidence.dom_generation_count
        if total_dom_ops > 0:
            self.runtime_evidence.dom_reuse_ratio = self.runtime_evidence.dom_reuse_count / total_dom_ops
        
        total_healing = self.runtime_evidence.healing_attempts
        if total_healing > 0:
            self.runtime_evidence.healing_success_rate = self.runtime_evidence.healing_successes / total_healing
        
        # Calculate time saved percentage (assume 5s baseline per DOM capture)
        baseline_time = (self.runtime_evidence.dom_generation_count + self.runtime_evidence.dom_reuse_count) * 5000
        if baseline_time > 0:
            self.runtime_evidence.time_saved_percentage = (self.runtime_evidence.time_saved_ms / baseline_time) * 100
        
        # Calculate scores
        self.runtime_evidence.confidence_score = (
            self.runtime_evidence.cache_hit_ratio * 0.3 +
            self.runtime_evidence.locator_reuse_ratio * 0.3 +
            self.runtime_evidence.healing_success_rate * 0.2 +
            self.runtime_evidence.dom_reuse_ratio * 0.2
        ) * 100
        
        self.runtime_evidence.automation_score = (
            self.runtime_evidence.cache_hit_ratio * 0.25 +
            self.runtime_evidence.locator_reuse_ratio * 0.35 +
            self.runtime_evidence.healing_success_rate * 0.2 +
            self.runtime_evidence.dom_reuse_ratio * 0.2
        ) * 100
        
        # Generate execution delta if previous execution exists
        if self.previous_execution:
            self.runtime_evidence.execution_delta = ExecutionDelta(
                previous_execution_id=self.previous_execution.get("execution_id"),
                current_execution_id=self.execution_id,
                time_saved_ms=self.runtime_evidence.time_saved_ms,
                dom_cache_hit_count=self.runtime_evidence.cache_hits,
                dom_cache_miss_count=self.runtime_evidence.cache_misses,
                locator_reuse_count=self.runtime_evidence.locator_reuse_count,
                locator_generation_count=self.runtime_evidence.locator_generation_count,
                healing_attempts=self.runtime_evidence.healing_attempts,
                healing_successes=self.runtime_evidence.healing_successes,
                mcp_calls_saved=self.runtime_evidence.mcp_calls_saved,
                llm_calls_saved=self.runtime_evidence.llm_calls_saved,
                improvement_percentage=self.runtime_evidence.automation_score
            )
        
        # End tracking
        if self.timeline_tracker:
            self.timeline_tracker.end_timeline(status=status)
        
        if self.metrics_collector:
            self.metrics_collector.end_collection(status=status)
            
            # Add metrics to evidence
            metrics = self.metrics_collector.get_metrics()
            if metrics:
                # Calculate time saved percentage from runtime evidence
                if metrics.total_execution_time_ms > 0:
                    self.runtime_evidence.time_saved_percentage = (
                        (self.runtime_evidence.time_saved_ms / metrics.total_execution_time_ms * 100)
                    )
        
        # End flow discovery and discover business flows (Priority 21)
        if self.flow_discovery:
            discovered_flows = self.flow_discovery.end_execution()
            logger.info(f"[INTELLIGENT RUNTIME] Flow Discovery ended - discovered {len(discovered_flows)} flows")
            
            # Add flow discovery to evidence
            if discovered_flows:
                self.runtime_evidence.artifacts_created.append("business_flows")
        
        # Save runtime evidence
        self._save_runtime_evidence()
        
        # Save execution history
        self._save_execution_history()
        
        # Generate dashboard data
        self._generate_dashboard_data()
        
        logger.info(f"[INTELLIGENT RUNTIME] Execution ended: {self.execution_id}")
        logger.info(f"[INTELLIGENT RUNTIME] Status: {status}")
        logger.info(f"[INTELLIGENT RUNTIME] DOM Cache: {self.runtime_evidence.cache_hits} hits, {self.runtime_evidence.cache_misses} misses")
        logger.info(f"[INTELLIGENT RUNTIME] DOM Reuse: {self.runtime_evidence.dom_reuse_count} reused, {self.runtime_evidence.dom_generation_count} generated")
        logger.info(f"[INTELLIGENT RUNTIME] Time Saved: {self.runtime_evidence.time_saved_ms:.0f}ms ({self.runtime_evidence.time_saved_percentage:.1f}%)")
        logger.info(f"[INTELLIGENT RUNTIME] MCP Calls Saved: {self.runtime_evidence.mcp_calls_saved}")
        logger.info(f"[INTELLIGENT RUNTIME] LLM Calls Saved: {self.runtime_evidence.llm_calls_saved}")
        
        return self.runtime_evidence
    
    def analyze_semantic_page(
        self,
        url: str,
        title: str,
        heading: str,
        dom_content: str,
        dom_elements: List[Dict[str, Any]],
        text_content: str = "",
    ) -> Optional[Any]:
        """Perform semantic analysis of a page (Priority 20).
        
        Args:
            url: Page URL
            title: Page title
            heading: Main heading
            dom_content: Full DOM content
            dom_elements: List of DOM element dictionaries
            text_content: Page text content
            
        Returns:
            SemanticPage or None if semantic analysis is disabled
        """
        if not self.semantic_integrator:
            logger.debug("[INTELLIGENT RUNTIME] Semantic analysis disabled")
            return None
        
        logger.info(f"[INTELLIGENT RUNTIME] Performing semantic analysis for: {url}")
        
        try:
            # Perform semantic analysis
            semantic_page = self.semantic_integrator.analyze_page(
                url=url,
                title=title,
                heading=heading,
                dom_content=dom_content,
                dom_elements=dom_elements,
                text_content=text_content,
                project_name=self.project_name,
                test_name=self.test_name or "unknown",
                execution_id=self.execution_id or "",
                dom_hash=self.dom_snapshot_manager.compute_dom_hash(dom_content) if self.dom_snapshot_manager else "",
            )
            
            # Store semantic page for later use
            self.semantic_page = semantic_page
            
            # Record semantic analysis in evidence
            self.runtime_evidence.artifacts_created.append("semantic_analysis")
            
            # Record intelligent decision
            self._record_decision(
                decision_type="semantic_analysis",
                decision="Analyze page semantics",
                reason=DecisionReason.IMPROVEMENT_DETECTED,
                evidence={
                    "page_type": semantic_page.page_type.value,
                    "business_intent": semantic_page.business_intent.primary_intent.value,
                    "confidence": semantic_page.confidence,
                }
            )
            
            logger.info(f"[INTELLIGENT RUNTIME] Semantic analysis complete: {semantic_page.page_type.value}")
            
            return semantic_page
            
        except Exception as e:
            logger.warning(f"[INTELLIGENT RUNTIME] Semantic analysis failed: {e}")
            import traceback
            logger.debug(f"[INTELLIGENT RUNTIME] Semantic analysis traceback: {traceback.format_exc()}")
            return None
    
    def get_semantic_context(self) -> str:
        """Get semantic context for LLM prompts (Priority 20).
        
        Returns:
            Formatted semantic context string or empty string if not available
        """
        if not self.semantic_integrator or not self.semantic_page:
            return ""
        
        try:
            return self.semantic_integrator.get_semantic_context_for_llm(self.semantic_page)
        except Exception as e:
            logger.warning(f"[INTELLIGENT RUNTIME] Failed to get semantic context: {e}")
            return ""
    
    def _save_runtime_evidence(self):
        """Save runtime evidence to file."""
        evidence_file = self.base_dir / "runtime_reports" / f"evidence_{self.execution_id}.json"
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"[PHOENIX EVIDENCE] Saving runtime evidence")
        print(f"[PHOENIX EVIDENCE] Evidence path: {evidence_file.absolute()}")
        print(f"[PHOENIX EVIDENCE] Base directory: {self.base_dir.absolute()}")
        print(f"[PHOENIX EVIDENCE] Execution ID: {self.execution_id}")
        
        with open(evidence_file, 'w', encoding='utf-8') as f:
            # Convert to dict for JSON serialization
            evidence_dict = {
                "execution_id": self.runtime_evidence.execution_id,
                "project_name": self.runtime_evidence.project_name,
                "test_name": self.runtime_evidence.test_name,
                "timestamp": self.runtime_evidence.timestamp,
                "artifacts_loaded": self.runtime_evidence.artifacts_loaded,
                "artifacts_reused": self.runtime_evidence.artifacts_reused,
                "artifacts_updated": self.runtime_evidence.artifacts_updated,
                "artifacts_created": self.runtime_evidence.artifacts_created,
                "cache_hits": self.runtime_evidence.cache_hits,
                "cache_misses": self.runtime_evidence.cache_misses,
                "cache_hit_ratio": self.runtime_evidence.cache_hit_ratio,
                "locator_reuse_count": self.runtime_evidence.locator_reuse_count,
                "locator_generation_count": self.runtime_evidence.locator_generation_count,
                "locator_reuse_ratio": self.runtime_evidence.locator_reuse_ratio,
                "healing_attempts": self.runtime_evidence.healing_attempts,
                "healing_successes": self.runtime_evidence.healing_successes,
                "healing_failures": self.runtime_evidence.healing_failures,
                "healing_success_rate": self.runtime_evidence.healing_success_rate,
                "dom_reuse_count": self.runtime_evidence.dom_reuse_count,
                "dom_generation_count": self.runtime_evidence.dom_generation_count,
                "dom_reuse_ratio": self.runtime_evidence.dom_reuse_ratio,
                "time_saved_ms": self.runtime_evidence.time_saved_ms,
                "time_saved_percentage": self.runtime_evidence.time_saved_percentage,
                "mcp_calls_saved": self.runtime_evidence.mcp_calls_saved,
                "llm_calls_saved": self.runtime_evidence.llm_calls_saved,
                "confidence_score": self.runtime_evidence.confidence_score,
                "automation_score": self.runtime_evidence.automation_score,
                "decisions": [
                    {
                        "decision_type": d.decision_type,
                        "decision": d.decision,
                        "reason": d.reason.value if hasattr(d.reason, 'value') else str(d.reason),
                        "evidence": d.evidence,
                        "timestamp": d.timestamp
                    }
                    for d in self.runtime_evidence.decisions
                ]
            }
            json.dump(evidence_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[INTELLIGENT RUNTIME] Saved runtime evidence to {evidence_file}")
        print(f"[PHOENIX EVIDENCE] Runtime evidence saved successfully")
        print(f"[PHOENIX EVIDENCE] Cache hits: {self.runtime_evidence.cache_hits}")
        print(f"[PHOENIX EVIDENCE] Cache misses: {self.runtime_evidence.cache_misses}")
        print(f"[PHOENIX EVIDENCE] DOM reuse count: {self.runtime_evidence.dom_reuse_count}")
        print(f"[PHOENIX EVIDENCE] DOM generation count: {self.runtime_evidence.dom_generation_count}")
        print(f"[PHOENIX EVIDENCE] Time saved: {self.runtime_evidence.time_saved_ms:.2f}ms")
        
        # Also save to a known location for TestRunner to load
        evidence_sync_file = self.base_dir / ".runtime_evidence_sync.json"
        print(f"[PHOENIX EVIDENCE] Evidence sync path: {evidence_sync_file.absolute()}")
        with open(evidence_sync_file, 'w', encoding='utf-8') as f:
            json.dump(evidence_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[INTELLIGENT RUNTIME] Saved runtime evidence sync to {evidence_sync_file}")
        print(f"[PHOENIX EVIDENCE] Evidence sync saved successfully")
    
    def _save_execution_history(self):
        """Save execution to history."""
        history_file = self.base_dir / "execution_history" / f"{self.execution_id}.json"
        
        history_dict = {
            "execution_id": self.execution_id,
            "project_name": self.project_name,
            "test_name": self.test_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_hit_ratio": self.runtime_evidence.cache_hit_ratio,
            "locator_reuse_ratio": self.runtime_evidence.locator_reuse_ratio,
            "healing_success_rate": self.runtime_evidence.healing_success_rate,
            "time_saved_ms": self.runtime_evidence.time_saved_ms,
            "confidence_score": self.runtime_evidence.confidence_score,
            "automation_score": self.runtime_evidence.automation_score
        }
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_dict, f, indent=2)
    
    def _generate_dashboard_data(self):
        """Generate dashboard summary data."""
        dashboard_file = self.base_dir / "intelligence_dashboard" / "runtime_summary.json"
        
        # Load existing dashboard data
        existing_data = {}
        if dashboard_file.exists():
            try:
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = {}
        
        # Update with current execution
        summary = {
            "execution_number": existing_data.get("execution_number", 0) + 1,
            "last_execution_id": self.execution_id,
            "last_execution_time": datetime.now(timezone.utc).isoformat(),
            "average_cache_hit_ratio": self._calculate_average(
                existing_data.get("average_cache_hit_ratio", 0),
                self.runtime_evidence.cache_hit_ratio,
                existing_data.get("execution_number", 0)
            ),
            "average_locator_reuse_ratio": self._calculate_average(
                existing_data.get("average_locator_reuse_ratio", 0),
                self.runtime_evidence.locator_reuse_ratio,
                existing_data.get("execution_number", 0)
            ),
            "average_healing_success_rate": self._calculate_average(
                existing_data.get("average_healing_success_rate", 0),
                self.runtime_evidence.healing_success_rate,
                existing_data.get("execution_number", 0)
            ),
            "total_time_saved_ms": existing_data.get("total_time_saved_ms", 0) + self.runtime_evidence.time_saved_ms,
            "total_mcp_calls_saved": existing_data.get("total_mcp_calls_saved", 0) + self.runtime_evidence.mcp_calls_saved,
            "total_llm_calls_saved": existing_data.get("total_llm_calls_saved", 0) + self.runtime_evidence.llm_calls_saved,
            "current_confidence_score": self.runtime_evidence.confidence_score,
            "current_automation_score": self.runtime_evidence.automation_score
        }
        
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
    
    def _calculate_average(self, previous_avg: float, new_value: float, count: int) -> float:
        """Calculate running average."""
        if count == 0:
            return new_value
        return (previous_avg * count + new_value) / (count + 1)
    
    def get_components(self) -> Dict[str, Any]:
        """Get all intelligent components for external use."""
        return {
            "dom_cache": self.dom_cache,
            "locator_repository": self.locator_repository,
            "dom_diff_engine": self.dom_diff_engine,
            "healing_engine": self.healing_engine,
            "metrics_collector": self.metrics_collector,
            "timeline_tracker": self.timeline_tracker,
            "artifacts_manager": self.artifacts_manager
        }
    
    def print_summary(self):
        """Print intelligent runtime execution summary."""
        if not self.runtime_evidence:
            logger.warning("No runtime evidence available for summary")
            return
        
        evidence = self.runtime_evidence
        
        print("\n" + "=" * 60)
        print("PHOENIX INTELLIGENT RUNTIME SUMMARY")
        print("=" * 60)
        
        # Component execution status
        print(f"\nComponent Execution Status:")
        print(f"  DOM Snapshot      : {'EXECUTED' if evidence.dom_reuse_count > 0 or evidence.dom_generation_count > 0 else 'NOT EXECUTED'}")
        print(f"  DOM Cache         : {'EXECUTED' if evidence.cache_hits + evidence.cache_misses > 0 else 'NOT EXECUTED'}")
        print(f"  Locator Repository: {'EXECUTED' if self.locator_repository else 'NOT EXECUTED'}")
        print(f"  Healing           : {'EXECUTED' if self.healing_engine else 'NOT EXECUTED'}")
        print(f"  Runtime Metrics   : {'EXECUTED' if self.metrics_collector else 'NOT EXECUTED'}")
        print(f"  Runtime Timeline  : {'EXECUTED' if self.timeline_tracker else 'NOT EXECUTED'}")
        
        # DOM statistics
        print(f"\nDOM Statistics:")
        print(f"  Cache Hits        : {evidence.cache_hits}")
        print(f"  Cache Misses      : {evidence.cache_misses}")
        print(f"  Cache Hit Ratio   : {evidence.cache_hit_ratio:.1%}")
        print(f"  DOM Reused        : {evidence.dom_reuse_count}")
        print(f"  DOM Generated     : {evidence.dom_generation_count}")
        print(f"  DOM Reuse Ratio   : {evidence.dom_reuse_ratio:.1%}")
        
        # Performance
        print(f"\nPerformance:")
        print(f"  Time Saved        : {evidence.time_saved_ms:.0f}ms ({evidence.time_saved_percentage:.1f}%)")
        print(f"  MCP Calls Saved   : {evidence.mcp_calls_saved}")
        print(f"  LLM Calls Saved   : {evidence.llm_calls_saved}")
        
        # Intelligence scores
        print(f"\nIntelligence Scores:")
        print(f"  Confidence Score  : {evidence.confidence_score:.1f}/100")
        print(f"  Automation Score  : {evidence.automation_score:.1f}/100")
        
        # Decisions
        if evidence.decisions:
            print(f"\nIntelligent Decisions: {len(evidence.decisions)}")
            for decision in evidence.decisions[:5]:  # Show first 5 decisions
                print(f"  - {decision.decision_type}: {decision.decision} ({decision.reason.value})")
            if len(evidence.decisions) > 5:
                print(f"  ... and {len(evidence.decisions) - 5} more decisions")
        
        print("=" * 60 + "\n")