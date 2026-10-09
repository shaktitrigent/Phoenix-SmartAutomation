"""DOM Runtime Evidence - Complete tracking of DOM lifecycle in production runtime.

This module provides comprehensive evidence tracking for DOM operations:
- Where DOM was loaded from
- Why MCP was skipped or executed
- Which execution produced the DOM
- Which downstream modules consumed DOM
- Complete decision audit trail
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DOM Runtime Evidence Models
# ---------------------------------------------------------------------------

class DOMConsumerRecord(BaseModel):
    """Record of a downstream module consuming DOM."""
    module_name: str = Field(..., description="Name of consuming module")
    consumption_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dom_hash: str = ""
    purpose: str = ""  # locator_generation, test_generation, etc.
    success: bool = True


class DOMRuntimeEvidence(BaseModel):
    """Complete runtime evidence for DOM operations."""
    
    # Snapshot Information
    snapshot_location: str = ""
    execution_loaded: str = ""  # Execution ID that produced the snapshot
    snapshot_timestamp: str = ""
    
    # Hash Information
    previous_hash: str = ""
    current_hash: str = ""
    hash_comparison_result: str = ""  # unchanged, changed, no_previous
    
    # Reuse Decision
    reuse_decision: str = ""  # REUSE or CAPTURE
    reuse_reason: str = ""
    
    # MCP Call Information
    mcp_called: bool = False
    mcp_skipped: bool = False
    mcp_skip_reason: str = ""
    mcp_duration_ms: float = 0.0
    
    # Performance
    execution_time_saved_ms: float = 0.0
    total_decision_time_ms: float = 0.0
    
    # Downstream Consumers
    downstream_consumers: List[DOMConsumerRecord] = Field(default_factory=list)
    
    # Runtime Context
    runtime_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    project_name: str = ""
    page_name: str = ""
    test_name: str = ""
    current_execution_id: str = ""
    
    # Audit Trail
    decision_audit_log: List[str] = Field(default_factory=list)


class DOMRuntimeEvidenceTracker:
    """Tracks complete DOM lifecycle evidence during runtime execution.
    
    This tracker provides:
    - Automatic evidence collection during DOM operations
    - Downstream consumption tracking
    - Complete audit trail
    - Runtime evidence file generation
    """
    
    def __init__(self, base_dir: str | Path = "PhoenixRuntime"):
        self.base_dir = Path(base_dir)
        self.runtime_reports_dir = self.base_dir / "runtime_reports"
        self.runtime_reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_evidence: Optional[DOMRuntimeEvidence] = None
        self.decision_start_time: Optional[float] = None
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Initialized with storage: {self.runtime_reports_dir}")
    
    def start_tracking(
        self,
        project_name: str,
        page_name: str,
        test_name: str,
        execution_id: str
    ):
        """Start tracking a new DOM operation."""
        self.decision_start_time = time.time()
        
        self.current_evidence = DOMRuntimeEvidence(
            project_name=project_name,
            page_name=page_name,
            test_name=test_name,
            current_execution_id=execution_id
        )
        
        self._log_audit("Started DOM tracking", {
            "project": project_name,
            "page": page_name,
            "test": test_name,
            "execution_id": execution_id
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Started tracking for {project_name}/{page_name}")
    
    def record_snapshot_search(self, location: str):
        """Record that a snapshot search was performed."""
        if not self.current_evidence:
            return
        
        self.current_evidence.snapshot_location = location
        self._log_audit("Searched for previous snapshot", {"location": location})
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Searching previous snapshot: {location}")
    
    def record_snapshot_found(
        self,
        location: str,
        execution_id: str,
        timestamp: str,
        dom_hash: str
    ):
        """Record that a previous snapshot was found."""
        if not self.current_evidence:
            return
        
        self.current_evidence.snapshot_location = location
        self.current_evidence.execution_loaded = execution_id
        self.current_evidence.snapshot_timestamp = timestamp
        self.current_evidence.previous_hash = dom_hash
        
        self._log_audit("Previous snapshot found", {
            "location": location,
            "execution_id": execution_id,
            "timestamp": timestamp,
            "hash": dom_hash
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Previous snapshot found")
        logger.info(f"[DOM RUNTIME EVIDENCE] Location: {location}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Execution: {execution_id}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Hash: {dom_hash}")
    
    def record_snapshot_not_found(self):
        """Record that no previous snapshot was found."""
        if not self.current_evidence:
            return
        
        self._log_audit("No previous snapshot found", {})
        
        logger.info(f"[DOM RUNTIME EVIDENCE] No previous snapshot found")
    
    def record_hash_comparison(
        self,
        previous_hash: str,
        current_hash: str,
        result: str
    ):
        """Record hash comparison result."""
        if not self.current_evidence:
            return
        
        self.current_evidence.previous_hash = previous_hash
        self.current_evidence.current_hash = current_hash
        self.current_evidence.hash_comparison_result = result
        
        self._log_audit("Hash comparison performed", {
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "result": result
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Hash comparison: {result}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Previous hash: {previous_hash}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Current hash: {current_hash}")
    
    def record_reuse_decision(
        self,
        decision: str,
        reason: str,
        mcp_skipped: bool,
        time_saved_ms: float = 0.0
    ):
        """Record DOM reuse decision."""
        if not self.current_evidence:
            return
        
        self.current_evidence.reuse_decision = decision
        self.current_evidence.reuse_reason = reason
        self.current_evidence.mcp_skipped = mcp_skipped
        self.current_evidence.execution_time_saved_ms = time_saved_ms
        
        self._log_audit("Reuse decision made", {
            "decision": decision,
            "reason": reason,
            "mcp_skipped": mcp_skipped,
            "time_saved_ms": time_saved_ms
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Reuse decision: {decision}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Reason: {reason}")
        logger.info(f"[DOM RUNTIME EVIDENCE] MCP skipped: {mcp_skipped}")
        if time_saved_ms > 0:
            logger.info(f"[DOM RUNTIME EVIDENCE] Time saved: {time_saved_ms:.2f}ms")
    
    def record_mcp_call(
        self,
        called: bool,
        skip_reason: str = "",
        duration_ms: float = 0.0
    ):
        """Record MCP call information."""
        if not self.current_evidence:
            return
        
        self.current_evidence.mcp_called = called
        self.current_evidence.mcp_skipped = not called
        self.current_evidence.mcp_skip_reason = skip_reason
        self.current_evidence.mcp_duration_ms = duration_ms
        
        self._log_audit("MCP call recorded", {
            "called": called,
            "skip_reason": skip_reason,
            "duration_ms": duration_ms
        })
        
        if called:
            logger.info(f"[DOM RUNTIME EVIDENCE] MCP called")
            logger.info(f"[DOM RUNTIME EVIDENCE] Duration: {duration_ms:.2f}ms")
        else:
            logger.info(f"[DOM RUNTIME EVIDENCE] MCP skipped")
            logger.info(f"[DOM RUNTIME EVIDENCE] Skip reason: {skip_reason}")
    
    def record_consumer(
        self,
        module_name: str,
        dom_hash: str,
        purpose: str,
        success: bool = True
    ):
        """Record that a downstream module consumed DOM."""
        if not self.current_evidence:
            return
        
        consumer_record = DOMConsumerRecord(
            module_name=module_name,
            dom_hash=dom_hash,
            purpose=purpose,
            success=success
        )
        
        self.current_evidence.downstream_consumers.append(consumer_record)
        
        self._log_audit("DOM consumed by module", {
            "module": module_name,
            "hash": dom_hash,
            "purpose": purpose,
            "success": success
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] DOM consumed by: {module_name}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Purpose: {purpose}")
        logger.info(f"[DOM RUNTIME EVIDENCE] Hash: {dom_hash}")
    
    def finalize_tracking(self) -> DOMRuntimeEvidence:
        """Finalize tracking and return complete evidence."""
        if not self.current_evidence:
            return None
        
        # Calculate total decision time
        if self.decision_start_time:
            self.current_evidence.total_decision_time_ms = (time.time() - self.decision_start_time) * 1000
        
        self._log_audit("Tracking finalized", {
            "total_time_ms": self.current_evidence.total_decision_time_ms,
            "total_consumers": len(self.current_evidence.downstream_consumers)
        })
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Tracking finalized")
        logger.info(f"[DOM RUNTIME EVIDENCE] Total decision time: {self.current_evidence.total_decision_time_ms:.2f}ms")
        logger.info(f"[DOM RUNTIME EVIDENCE] Total consumers: {len(self.current_evidence.downstream_consumers)}")
        
        return self.current_evidence
    
    def save_evidence(self, evidence: DOMRuntimeEvidence) -> Path:
        """Save runtime evidence to file."""
        if not evidence:
            return None
        
        # Create evidence file path
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        evidence_path = self.runtime_reports_dir / f"dom_runtime_evidence_{timestamp}.json"
        
        # Save evidence
        evidence_path.write_text(evidence.model_dump_json(indent=2), encoding='utf-8')
        
        logger.info(f"[DOM RUNTIME EVIDENCE] Evidence saved: {evidence_path}")
        
        return evidence_path
    
    def _log_audit(self, action: str, details: Dict[str, Any]):
        """Add entry to audit log."""
        if not self.current_evidence:
            return
        
        audit_entry = f"{datetime.now(timezone.utc).isoformat()} - {action}"
        if details:
            audit_entry += f" - {json.dumps(details, default=str)}"
        
        self.current_evidence.decision_audit_log.append(audit_entry)
