"""Runtime Artifacts Manager - Real evidence pipeline for Phoenix runtime.

This module provides comprehensive artifact storage for all runtime activities,
ensuring every operation produces verifiable evidence for debugging and demos.
"""

from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic schemas for artifacts
# ---------------------------------------------------------------------------

class DOMMetadata(BaseModel):
    """Metadata for DOM snapshot."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    url: str = ""
    title: str = ""
    dom_size_bytes: int = 0
    num_elements: int = 0
    num_forms: int = 0
    num_buttons: int = 0
    num_inputs: int = 0
    num_links: int = 0
    dom_hash: str = ""


class PageMetadata(BaseModel):
    """Page execution metadata."""
    current_url: str = ""
    final_url: str = ""
    title: str = ""
    browser: str = ""
    viewport: str = ""
    execution_time_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LocatorRecord(BaseModel):
    """Single locator record with full metadata."""
    element_name: str = ""
    locator: str = ""
    locator_type: str = ""  # get_by_role, get_by_text, etc.
    priority: int = 0
    confidence: float = 0.0
    source: str = ""  # mcp, manual, healing
    generated_by: str = ""
    validation_result: str = ""  # found, not_found, duplicate, etc.
    reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MCPResponseRecord(BaseModel):
    """Raw MCP response record."""
    url: str = ""
    snapshot_text: str = ""
    snapshot_size_bytes: int = 0
    duration_seconds: float = 0.0
    success: bool = True
    error_message: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerationContext(BaseModel):
    """LLM generation context."""
    user_story: str = ""
    dom_length: int = 0
    dom_hash: str = ""
    mcp_enabled: bool = False
    prompt_sent: str = ""
    model_used: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionEvidence(BaseModel):
    """Complete execution evidence."""
    current_url: str = ""
    final_url: str = ""
    title: str = ""
    browser: str = ""
    viewport: str = ""
    execution_time_seconds: float = 0.0
    failures: List[str] = Field(default_factory=list)
    retries: int = 0
    healing_applied: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HealingAttempt(BaseModel):
    """Single healing attempt record."""
    original_locator: str = ""
    failure_reason: str = ""
    alternative_locator: str = ""
    success: bool = False
    strategy: str = ""
    duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HealingReport(BaseModel):
    """Complete healing report."""
    element_name: str = ""
    attempts: List[HealingAttempt] = Field(default_factory=list)
    final_locator: str = ""
    total_attempts: int = 0
    successful: bool = False
    total_duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LocatorValidationReport(BaseModel):
    """Locator validation report."""
    element_name: str = ""
    locator: str = ""
    found: bool = False
    not_found: bool = False
    duplicate: bool = False
    multiple_matches: bool = False
    invisible: bool = False
    disabled: bool = False
    match_count: int = 0
    validation_time_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Runtime Artifacts Manager
# ---------------------------------------------------------------------------

class RuntimeArtifactsManager:
    """Manages all runtime artifacts with real evidence tracking.
    
    This manager ensures that every runtime operation produces verifiable
    artifacts that can be inspected during debugging and demos.
    """
    
    def __init__(self, base_dir: str | Path = "logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.current_run_id: Optional[str] = None
        self.current_run_dir: Optional[Path] = None
        
    def start_run(self, run_id: Optional[str] = None) -> str:
        """Start a new run and create run-specific directory.
        
        Args:
            run_id: Optional run ID. If not provided, generates one.
            
        Returns:
            The run ID
        """
        if run_id is None:
            run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hash(int(time.time())) % 10000:04d}"
        
        self.current_run_id = run_id
        self.current_run_dir = self.base_dir / run_id
        self.current_run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.current_run_dir / "dom").mkdir(exist_ok=True)
        (self.current_run_dir / "locators").mkdir(exist_ok=True)
        (self.current_run_dir / "mcp").mkdir(exist_ok=True)
        (self.current_run_dir / "healing").mkdir(exist_ok=True)
        
        return run_id
    
    def _ensure_run(self) -> Path:
        """Ensure a run is active and return run directory."""
        if self.current_run_dir is None:
            self.start_run()
        return self.current_run_dir
    
    def save_dom_snapshot(
        self,
        html_content: str,
        json_content: str,
        accessibility_content: str,
        metadata: DOMMetadata
    ) -> Dict[str, Path]:
        """Save DOM snapshot with all formats.
        
        Args:
            html_content: Raw HTML content
            json_content: JSON representation of DOM
            accessibility_content: Accessibility tree
            metadata: DOM metadata
            
        Returns:
            Dictionary with paths to saved files
        """
        run_dir = self._ensure_run()
        dom_dir = run_dir / "dom"
        
        # Save HTML
        html_path = dom_dir / "dom_snapshot.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # Save JSON
        json_path = dom_dir / "dom_snapshot.json"
        json_path.write_text(json_content, encoding='utf-8')
        
        # Save accessibility
        a11y_path = dom_dir / "accessibility_snapshot.json"
        a11y_path.write_text(accessibility_content, encoding='utf-8')
        
        # Save metadata
        metadata_path = dom_dir / "page_metadata.json"
        metadata_path.write_text(metadata.model_dump_json(indent=2), encoding='utf-8')
        
        return {
            "html": html_path,
            "json": json_path,
            "accessibility": a11y_path,
            "metadata": metadata_path
        }
    
    def save_mcp_response(self, response: MCPResponseRecord) -> Path:
        """Save raw MCP response.
        
        Args:
            response: MCP response record
            
        Returns:
            Path to saved response
        """
        run_dir = self._ensure_run()
        mcp_dir = run_dir / "mcp"
        
        response_path = mcp_dir / "mcp_response.json"
        response_path.write_text(response.model_dump_json(indent=2), encoding='utf-8')
        
        return response_path
    
    def save_locators(self, element_name: str, locators: List[LocatorRecord]) -> Path:
        """Save generated locators with full metadata.
        
        Args:
            element_name: Name of the element
            locators: List of locator records
            
        Returns:
            Path to saved locators file
        """
        run_dir = self._ensure_run()
        locators_dir = run_dir / "locators"
        
        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in element_name)
        locators_path = locators_dir / f"{safe_name}_locators.json"
        
        locators_data = {
            "element_name": element_name,
            "locators": [locator.model_dump() for locator in locators],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        locators_path.write_text(json.dumps(locators_data, indent=2), encoding='utf-8')
        
        return locators_path
    
    def save_locator_validation(self, validation: LocatorValidationReport) -> Path:
        """Save locator validation report.
        
        Args:
            validation: Validation report
            
        Returns:
            Path to saved validation report
        """
        run_dir = self._ensure_run()
        validation_path = run_dir / "locator_validation.json"
        
        # Append to existing or create new
        validations = []
        if validation_path.exists():
            try:
                existing = json.loads(validation_path.read_text(encoding='utf-8'))
                validations = existing.get("validations", [])
            except:
                pass
        
        validations.append(validation.model_dump())
        
        validation_data = {
            "validations": validations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        validation_path.write_text(json.dumps(validation_data, indent=2), encoding='utf-8')
        
        return validation_path
    
    def save_generation_context(self, context: GenerationContext) -> Path:
        """Save LLM generation context.
        
        Args:
            context: Generation context
            
        Returns:
            Path to saved context
        """
        run_dir = self._ensure_run()
        context_path = run_dir / "generation_context.json"
        
        context_path.write_text(context.model_dump_json(indent=2), encoding='utf-8')
        
        return context_path
    
    def save_execution_evidence(self, evidence: ExecutionEvidence) -> Path:
        """Save runtime execution evidence.
        
        Args:
            evidence: Execution evidence
            
        Returns:
            Path to saved evidence
        """
        run_dir = self._ensure_run()
        evidence_path = run_dir / "execution.json"
        
        evidence_path.write_text(evidence.model_dump_json(indent=2), encoding='utf-8')
        
        return evidence_path
    
    def save_healing_report(self, report: HealingReport) -> Path:
        """Save healing report.
        
        Args:
            report: Healing report
            
        Returns:
            Path to saved healing report
        """
        run_dir = self._ensure_run()
        healing_dir = run_dir / "healing"
        
        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in report.element_name)
        report_path = healing_dir / f"{safe_name}_healing.json"
        
        report_path.write_text(report.model_dump_json(indent=2), encoding='utf-8')
        
        return report_path
    
    def compute_dom_hash(self, content: str) -> str:
        """Compute hash of DOM content for change detection.
        
        Args:
            content: DOM content
            
        Returns:
            SHA256 hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def count_dom_elements(self, html_content: str) -> Dict[str, int]:
        """Count elements in DOM for metadata.
        
        Args:
            html_content: HTML content
            
        Returns:
            Dictionary with element counts
        """
        import re
        
        # Simple regex-based counting
        forms = len(re.findall(r'<form[^>]*>', html_content, re.IGNORECASE))
        buttons = len(re.findall(r'<button[^>]*>', html_content, re.IGNORECASE))
        inputs = len(re.findall(r'<input[^>]*>', html_content, re.IGNORECASE))
        links = len(re.findall(r'<a[^>]*>', html_content, re.IGNORECASE))
        all_elements = len(re.findall(r'<[^>]+>', html_content))
        
        return {
            "num_elements": all_elements,
            "num_forms": forms,
            "num_buttons": buttons,
            "num_inputs": inputs,
            "num_links": links
        }
    
    def get_run_directory(self) -> Optional[Path]:
        """Get current run directory."""
        return self.current_run_dir
    
    def list_runs(self) -> List[Dict[str, Any]]:
        """List all runs with metadata.
        
        Returns:
            List of run information
        """
        runs = []
        for run_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if run_dir.is_dir():
                # Try to read execution.json for metadata
                exec_path = run_dir / "execution.json"
                metadata = {"run_id": run_dir.name}
                if exec_path.exists():
                    try:
                        exec_data = json.loads(exec_path.read_text(encoding='utf-8'))
                        metadata.update(exec_data)
                    except:
                        pass
                runs.append(metadata)
        return runs


# Global instance
_global_artifacts_manager: Optional[RuntimeArtifactsManager] = None


def get_artifacts_manager(base_dir: str | Path = "logs") -> RuntimeArtifactsManager:
    """Get global artifacts manager instance.
    
    Args:
        base_dir: Base directory for artifacts
        
    Returns:
        RuntimeArtifactsManager instance
    """
    global _global_artifacts_manager
    if _global_artifacts_manager is None:
        _global_artifacts_manager = RuntimeArtifactsManager(base_dir)
    return _global_artifacts_manager