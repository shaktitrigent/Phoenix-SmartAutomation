"""DOM Snapshot Manager - Production permanent DOM storage and reuse.

This module implements enterprise-grade DOM snapshot persistence that:
- Stores DOM snapshots permanently in structured storage
- Automatically loads and reuses DOM across executions
- Compares DOM hashes to detect changes
- Skips MCP calls when DOM is unchanged
- Provides comprehensive runtime logging
- Maintains complete metadata for all snapshots
- Integrates with runtime evidence tracking
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DOM Snapshot Models
# ---------------------------------------------------------------------------

class DOMSnapshotMetadata(BaseModel):
    """Complete metadata for a DOM snapshot."""
    url: str = Field(..., description="Page URL")
    project: str = Field(..., description="Project name")
    page: str = Field(..., description="Page name")
    execution_id: str = Field(..., description="Execution ID")
    dom_hash: str = Field(..., description="SHA256 hash of DOM content")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dom_size_bytes: int = 0
    num_elements: int = 0
    capture_source: str = "mcp"  # mcp, manual, reused
    capture_duration_ms: float = 0.0


class DOMSnapshot(BaseModel):
    """Complete DOM snapshot with content and metadata."""
    metadata: DOMSnapshotMetadata
    dom_content: str = Field(..., description="Complete DOM content")
    accessibility_tree: str = ""  # Optional accessibility tree


class DOMReuseDecision(BaseModel):
    """Decision about DOM reuse."""
    decision: str = Field(..., description="REUSE or CAPTURE")
    url: str = ""
    project: str = ""
    page: str = ""
    previous_hash: str = ""
    current_hash: str = ""
    reason: str = ""
    mcp_skipped: bool = False
    time_saved_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# DOM Snapshot Manager
# ---------------------------------------------------------------------------

class DOMSnapshotManager:
    """Production DOM snapshot manager with permanent storage and automatic reuse.
    
    Storage Structure:
    PhoenixRuntime/
        dom/
            {project}/
                {page}/
                    latest_dom.json          # Latest DOM snapshot
                    metadata.json            # Latest metadata
                    history/
                        execution_{id}.json  # Historical snapshots
    """
    
    def __init__(self, base_dir: str | Path = "PhoenixRuntime"):
        self.base_dir = Path(base_dir)
        self.dom_storage_dir = self.base_dir / "dom"
        self.dom_storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize runtime evidence tracker
        from phoenix.execution.dom_runtime_evidence import DOMRuntimeEvidenceTracker
        self.evidence_tracker = DOMRuntimeEvidenceTracker(base_dir=base_dir)
        
        logger.info(f"[DOM SNAPSHOT MANAGER] Initialized with storage: {self.dom_storage_dir}")
    
    def _get_page_storage_path(self, project: str, page: str) -> Path:
        """Get storage path for a specific project/page."""
        page_dir = self.dom_storage_dir / project / page
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "history").mkdir(exist_ok=True)
        return page_dir
    
    def compute_dom_hash(self, dom_content: str) -> str:
        """Compute SHA256 hash of DOM content."""
        return hashlib.sha256(dom_content.encode('utf-8')).hexdigest()
    
    def store_dom_snapshot(
        self,
        dom_content: str,
        url: str,
        project: str,
        page: str,
        execution_id: str,
        capture_source: str = "mcp",
        capture_duration_ms: float = 0.0,
        accessibility_tree: str = ""
    ) -> DOMSnapshot:
        """Store DOM snapshot permanently with complete metadata.
        
        Args:
            dom_content: Complete DOM content
            url: Page URL
            project: Project name
            page: Page name
            execution_id: Execution ID
            capture_source: Source of DOM (mcp, manual, reused)
            capture_duration_ms: Time taken to capture DOM
            accessibility_tree: Optional accessibility tree
            
        Returns:
            Stored DOM snapshot
        """
        logger.info(f"[DOM SNAPSHOT MANAGER] STORE DOM SNAPSHOT - Project: {project}, Page: {page}, Execution ID: {execution_id}")
        start_time = time.time()
        
        # Compute hash
        dom_hash = self.compute_dom_hash(dom_content)
        
        # Create metadata
        metadata = DOMSnapshotMetadata(
            url=url,
            project=project,
            page=page,
            execution_id=execution_id,
            dom_hash=dom_hash,
            dom_size_bytes=len(dom_content.encode('utf-8')),
            num_elements=dom_content.count('<'),
            capture_source=capture_source,
            capture_duration_ms=capture_duration_ms
        )
        
        # Create snapshot
        snapshot = DOMSnapshot(
            metadata=metadata,
            dom_content=dom_content,
            accessibility_tree=accessibility_tree
        )
        
        # Get storage path
        page_dir = self._get_page_storage_path(project, page)
        
        # Store latest snapshot
        latest_path = page_dir / "latest_dom.json"
        latest_path.write_text(snapshot.model_dump_json(indent=2), encoding='utf-8')
        
        # Store metadata separately
        metadata_path = page_dir / "metadata.json"
        metadata_path.write_text(metadata.model_dump_json(indent=2), encoding='utf-8')
        
        # Store in history
        history_path = page_dir / "history" / f"execution_{execution_id}.json"
        history_path.write_text(snapshot.model_dump_json(indent=2), encoding='utf-8')
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(f"[DOM SNAPSHOT] Stored permanently")
        logger.info(f"[DOM SNAPSHOT] Location: {latest_path}")
        logger.info(f"[DOM SNAPSHOT] URL: {url}")
        logger.info(f"[DOM SNAPSHOT] Hash: {dom_hash}")
        logger.info(f"[DOM SNAPSHOT] Size: {metadata.dom_size_bytes} bytes")
        logger.info(f"[DOM SNAPSHOT] Elements: {metadata.num_elements}")
        logger.info(f"[DOM SNAPSHOT] Source: {capture_source}")
        logger.info(f"[DOM SNAPSHOT] Storage duration: {duration_ms:.2f}ms")
        
        return snapshot
    
    def load_latest_dom_snapshot(
        self,
        project: str,
        page: str
    ) -> Optional[DOMSnapshot]:
        """Load latest DOM snapshot for a project/page.
        
        Args:
            project: Project name
            page: Page name
            
        Returns:
            Latest DOM snapshot or None if not found
        """
        page_dir = self._get_page_storage_path(project, page)
        latest_path = page_dir / "latest_dom.json"
        
        if not latest_path.exists():
            logger.info(f"[DOM SNAPSHOT] No previous snapshot found for {project}/{page}")
            return None
        
        try:
            snapshot_data = json.loads(latest_path.read_text(encoding='utf-8'))
            snapshot = DOMSnapshot(**snapshot_data)
            
            logger.info(f"[DOM SNAPSHOT] Loaded previous snapshot")
            logger.info(f"[DOM SNAPSHOT] Location: {latest_path}")
            logger.info(f"[DOM SNAPSHOT] URL: {snapshot.metadata.url}")
            logger.info(f"[DOM SNAPSHOT] Hash: {snapshot.metadata.dom_hash}")
            logger.info(f"[DOM SNAPSHOT] Timestamp: {snapshot.metadata.timestamp}")
            logger.info(f"[DOM SNAPSHOT] Execution ID: {snapshot.metadata.execution_id}")
            
            return snapshot
        except Exception as e:
            logger.warning(f"[DOM SNAPSHOT] Failed to load snapshot: {e}")
            return None
    
    def should_reuse_dom(
        self,
        url: str,
        project: str,
        page: str,
        current_dom: Optional[str] = None,
        execution_id: str = ""
    ) -> DOMReuseDecision:
        """Decide whether to reuse stored DOM or capture new DOM with evidence tracking.
        
        Args:
            url: Current page URL
            project: Project name
            page: Page name
            current_dom: Optional current DOM for hash comparison
            execution_id: Current execution ID for evidence tracking
            
        Returns:
            DOM reuse decision
        """
        start_time = time.time()
        
        # Start evidence tracking
        if execution_id:
            self.evidence_tracker.start_tracking(
                project_name=project,
                page_name=page,
                test_name=page,
                execution_id=execution_id
            )
        
        # Record snapshot search
        page_dir = self._get_page_storage_path(project, page)
        latest_path = page_dir / "latest_dom.json"
        self.evidence_tracker.record_snapshot_search(str(latest_path))
        
        # Load previous snapshot
        previous_snapshot = self.load_latest_dom_snapshot(project, page)
        
        if previous_snapshot is None:
            # No previous snapshot - must capture
            duration_ms = (time.time() - start_time) * 1000
            decision = DOMReuseDecision(
                decision="CAPTURE",
                url=url,
                project=project,
                page=page,
                reason="No previous DOM snapshot found",
                mcp_skipped=False,
                time_saved_ms=0.0
            )
            
            self.evidence_tracker.record_snapshot_not_found()
            self.evidence_tracker.record_reuse_decision("CAPTURE", decision.reason, False, 0.0)
            self.evidence_tracker.record_mcp_call(False, "No previous snapshot", 0.0)
            
            logger.info(f"[DOM SNAPSHOT] Decision: CAPTURE (no previous snapshot)")
            logger.info(f"[DOM SNAPSHOT] Reason: {decision.reason}")
            return decision
        
        # Record snapshot found
        self.evidence_tracker.record_snapshot_found(
            location=str(latest_path),
            execution_id=previous_snapshot.metadata.execution_id,
            timestamp=previous_snapshot.metadata.timestamp,
            dom_hash=previous_snapshot.metadata.dom_hash
        )
        
        # Check URL match
        if previous_snapshot.metadata.url != url:
            duration_ms = (time.time() - start_time) * 1000
            decision = DOMReuseDecision(
                decision="CAPTURE",
                url=url,
                project=project,
                page=page,
                previous_hash=previous_snapshot.metadata.dom_hash,
                reason=f"URL changed from {previous_snapshot.metadata.url}",
                mcp_skipped=False,
                time_saved_ms=0.0
            )
            
            self.evidence_tracker.record_reuse_decision("CAPTURE", decision.reason, False, 0.0)
            self.evidence_tracker.record_mcp_call(False, "URL changed", 0.0)
            
            logger.info(f"[DOM SNAPSHOT] Decision: CAPTURE (URL changed)")
            logger.info(f"[DOM SNAPSHOT] Previous URL: {previous_snapshot.metadata.url}")
            logger.info(f"[DOM SNAPSHOT] Current URL: {url}")
            return decision
        
        # If current DOM provided, compare hashes
        if current_dom is not None:
            current_hash = self.compute_dom_hash(current_dom)
            previous_hash = previous_snapshot.metadata.dom_hash
            
            self.evidence_tracker.record_hash_comparison(previous_hash, current_hash, "changed" if current_hash != previous_hash else "unchanged")
            
            if current_hash == previous_hash:
                # DOM unchanged - check if previous snapshot is valid before reusing
                previous_dom_size = len(previous_snapshot.dom_content) if previous_snapshot.dom_content else 0
                current_dom_size = len(current_dom) if current_dom else 0
                
                # Reject reuse if previous snapshot is empty or suspiciously small
                if previous_dom_size < 100 or current_dom_size < 100:
                    logger.warning(f"[DOM SNAPSHOT] Snapshot too small (previous: {previous_dom_size} bytes, current: {current_dom_size} bytes), forcing CAPTURE")
                    duration_ms = (time.time() - start_time) * 1000
                    decision = DOMReuseDecision(
                        decision="CAPTURE",
                        url=url,
                        project=project,
                        page=page,
                        previous_hash=previous_hash,
                        current_hash=current_hash,
                        reason=f"Snapshot too small (previous: {previous_dom_size} bytes, current: {current_dom_size} bytes)",
                        mcp_skipped=False,
                        time_saved_ms=0.0
                    )
                    
                    self.evidence_tracker.record_reuse_decision("CAPTURE", decision.reason, False, 0.0)
                    self.evidence_tracker.record_mcp_call(True, "", 0.0)
                    
                    logger.info(f"[DOM SNAPSHOT] Decision: CAPTURE (invalid snapshot size)")
                    logger.info(f"[DOM SNAPSHOT] Previous size: {previous_dom_size} bytes")
                    logger.info(f"[DOM SNAPSHOT] Current size: {current_dom_size} bytes")
                    logger.info(f"[DOM SNAPSHOT] MCP skipped: NO")
                    return decision
                
                # DOM unchanged and valid - can reuse
                duration_ms = (time.time() - start_time) * 1000
                decision = DOMReuseDecision(
                    decision="REUSE",
                    url=url,
                    project=project,
                    page=page,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                    reason="DOM hash unchanged - content identical",
                    mcp_skipped=True,
                    time_saved_ms=duration_ms
                )
                
                self.evidence_tracker.record_reuse_decision("REUSE", decision.reason, True, duration_ms)
                self.evidence_tracker.record_mcp_call(False, "DOM unchanged", 0.0)
                
                logger.info(f"[DOM SNAPSHOT] Decision: REUSE (DOM unchanged)")
                logger.info(f"[DOM SNAPSHOT] Hash: {current_hash}")
                logger.info(f"[DOM SNAPSHOT] Previous size: {previous_dom_size} bytes")
                logger.info(f"[DOM SNAPSHOT] MCP skipped: YES")
                logger.info(f"[DOM SNAPSHOT] Time saved: {duration_ms:.2f}ms")
                return decision
            else:
                # DOM changed - must capture
                duration_ms = (time.time() - start_time) * 1000
                decision = DOMReuseDecision(
                    decision="CAPTURE",
                    url=url,
                    project=project,
                    page=page,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                    reason="DOM hash changed - content modified",
                    mcp_skipped=False,
                    time_saved_ms=0.0
                )
                
                self.evidence_tracker.record_reuse_decision("CAPTURE", decision.reason, False, 0.0)
                self.evidence_tracker.record_mcp_call(True, "", 0.0)
                
                logger.info(f"[DOM SNAPSHOT] Decision: CAPTURE (DOM changed)")
                logger.info(f"[DOM SNAPSHOT] Previous hash: {previous_hash}")
                logger.info(f"[DOM SNAPSHOT] Current hash: {current_hash}")
                logger.info(f"[DOM SNAPSHOT] MCP skipped: NO")
                return decision
        
        # No current DOM provided - check if previous snapshot is valid before reusing
        previous_dom_size = len(previous_snapshot.dom_content) if previous_snapshot.dom_content else 0
        
        # Reject reuse if previous snapshot is empty or suspiciously small
        if previous_dom_size < 100:
            logger.warning(f"[DOM SNAPSHOT] Previous snapshot is too small ({previous_dom_size} bytes), forcing CAPTURE")
            duration_ms = (time.time() - start_time) * 1000
            decision = DOMReuseDecision(
                decision="CAPTURE",
                url=url,
                project=project,
                page=page,
                previous_hash=previous_snapshot.metadata.dom_hash,
                reason=f"Previous snapshot invalid (too small: {previous_dom_size} bytes)",
                mcp_skipped=False,
                time_saved_ms=0.0
            )
            
            self.evidence_tracker.record_reuse_decision("CAPTURE", decision.reason, False, 0.0)
            self.evidence_tracker.record_mcp_call(True, "", 0.0)
            
            logger.info(f"[DOM SNAPSHOT] Decision: CAPTURE (invalid previous snapshot)")
            logger.info(f"[DOM SNAPSHOT] Previous size: {previous_dom_size} bytes")
            logger.info(f"[DOM SNAPSHOT] MCP skipped: NO")
            return decision
        
        # Previous snapshot looks valid, allow reuse
        duration_ms = (time.time() - start_time) * 1000
        decision = DOMReuseDecision(
            decision="REUSE",
            url=url,
            project=project,
            page=page,
            previous_hash=previous_snapshot.metadata.dom_hash,
            reason="No current DOM provided - assuming unchanged",
            mcp_skipped=True,
            time_saved_ms=duration_ms
        )
        
        self.evidence_tracker.record_reuse_decision("REUSE", decision.reason, True, duration_ms)
        self.evidence_tracker.record_mcp_call(False, "No current DOM for comparison", 0.0)
        
        logger.info(f"[DOM SNAPSHOT] Decision: REUSE (no current DOM for comparison)")
        logger.info(f"[DOM SNAPSHOT] Previous hash: {previous_snapshot.metadata.dom_hash}")
        logger.info(f"[DOM SNAPSHOT] Previous size: {previous_dom_size} bytes")
        logger.info(f"[DOM SNAPSHOT] MCP skipped: YES")
        logger.info(f"[DOM SNAPSHOT] Time saved: {duration_ms:.2f}ms")
        return decision
    
    def get_dom_with_automatic_reuse(
        self,
        url: str,
        project: str,
        page: str,
        execution_id: str,
        capture_func: callable,
        current_dom: Optional[str] = None
    ) -> Tuple[str, DOMReuseDecision]:
        """Get DOM with automatic reuse decision and evidence tracking.
        
        This is the main entry point for automatic DOM reuse in runtime.
        
        Args:
            url: Page URL
            project: Project name
            page: Page name
            execution_id: Execution ID
            capture_func: Function to call to capture DOM if needed
            current_dom: Optional current DOM for hash comparison
            
        Returns:
            Tuple of (dom_content, reuse_decision)
        """
        logger.info(f"[DOM SNAPSHOT] Automatic DOM reuse check started")
        logger.info(f"[DOM SNAPSHOT] URL: {url}")
        logger.info(f"[DOM SNAPSHOT] Project: {project}")
        logger.info(f"[DOM SNAPSHOT] Page: {page}")
        logger.info(f"[DOM SNAPSHOT] Execution ID: {execution_id}")
        
        # Make reuse decision with evidence tracking
        decision = self.should_reuse_dom(url, project, page, current_dom, execution_id)
        
        if decision.decision == "REUSE":
            # Load and reuse stored DOM
            previous_snapshot = self.load_latest_dom_snapshot(project, page)
            if previous_snapshot:
                logger.info(f"[DOM SNAPSHOT] Reusing stored DOM snapshot")
                logger.info(f"[DOM SNAPSHOT] Skipping MCP call")
                logger.info(f"[DOM SNAPSHOT] Time saved: {decision.time_saved_ms:.2f}ms")
                
                # Record MCP call in evidence
                self.evidence_tracker.record_mcp_call(False, "DOM reused", 0.0)
                
                # Finalize evidence and save
                evidence = self.evidence_tracker.finalize_tracking()
                if evidence:
                    self.evidence_tracker.save_evidence(evidence)
                
                return previous_snapshot.dom_content, decision
            else:
                # Fallback to capture if load fails
                logger.warning(f"[DOM SNAPSHOT] Failed to load stored DOM, capturing new")
                decision.decision = "CAPTURE"
                decision.reason = "Failed to load stored DOM"
                decision.mcp_skipped = False
        
        # Capture new DOM
        logger.info(f"[DOM SNAPSHOT] Capturing new DOM via MCP")
        capture_start = time.time()
        dom_content, accessibility_tree = capture_func(url)
        capture_duration_ms = (time.time() - capture_start) * 1000
        
        # Record MCP call in evidence
        self.evidence_tracker.record_mcp_call(True, "", capture_duration_ms)
        
        # Store new snapshot
        self.store_dom_snapshot(
            dom_content=dom_content,
            url=url,
            project=project,
            page=page,
            execution_id=execution_id,
            capture_source="mcp",
            capture_duration_ms=capture_duration_ms,
            accessibility_tree=accessibility_tree
        )
        
        logger.info(f"[DOM SNAPSHOT] New DOM captured and stored")
        logger.info(f"[DOM SNAPSHOT] Capture duration: {capture_duration_ms:.2f}ms")
        
        # Finalize evidence and save
        evidence = self.evidence_tracker.finalize_tracking()
        if evidence:
            self.evidence_tracker.save_evidence(evidence)
        
        return dom_content, decision
    
    def record_dom_consumer(
        self,
        module_name: str,
        dom_hash: str,
        purpose: str,
        success: bool = True
    ):
        """Record that a downstream module consumed DOM.
        
        Args:
            module_name: Name of consuming module (e.g., "LocatorGenerator", "TestGenerator")
            dom_hash: Hash of DOM being consumed
            purpose: Purpose of consumption (e.g., "locator_generation", "test_generation")
            success: Whether consumption was successful
        """
        self.evidence_tracker.record_consumer(module_name, dom_hash, purpose, success)
        logger.info(f"[DOM SNAPSHOT] DOM consumed by {module_name} for {purpose}")
    
    def get_latest_evidence(self) -> Optional[DOMRuntimeEvidence]:
        """Get the latest runtime evidence."""
        return self.evidence_tracker.finalize_tracking()
