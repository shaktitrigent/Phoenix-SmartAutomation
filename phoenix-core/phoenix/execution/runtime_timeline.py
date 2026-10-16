"""Runtime Timeline - Event sequence tracking with real timestamps.

This module implements timeline tracking that:
- Records events in chronological order
- Uses real timestamps only
- Captures event duration and relationships
- Provides execution flow visualization
- Generates verifiable timeline artifacts
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Timeline Models
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """Types of timeline events."""
    BROWSER_START = "browser_start"
    BROWSER_END = "browser_end"
    MCP_START = "mcp_start"
    MCP_END = "mcp_end"
    DOM_CAPTURE_START = "dom_capture_start"
    DOM_CAPTURE_END = "dom_capture_end"
    DOM_CACHE_HIT = "dom_cache_hit"
    DOM_CACHE_MISS = "dom_cache_miss"
    LOCATOR_LOAD_START = "locator_load_start"
    LOCATOR_LOAD_END = "locator_load_end"
    LOCATOR_GENERATION_START = "locator_generation_start"
    LOCATOR_GENERATION_END = "locator_generation_end"
    VALIDATION_START = "validation_start"
    VALIDATION_END = "validation_end"
    HEALING_START = "healing_start"
    HEALING_END = "healing_end"
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"
    TEST_START = "test_start"
    TEST_END = "test_end"
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class TimelineEvent(BaseModel):
    """Single timeline event."""
    event_type: str = Field(..., description="Type of event")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)
    parent_event_id: Optional[str] = None
    event_id: str = Field(default_factory=lambda: f"evt_{int(time.time() * 1000000)}")


class Timeline(BaseModel):
    """Complete execution timeline."""
    run_id: str = ""
    test_name: str = ""
    events: List[TimelineEvent] = Field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    total_duration_ms: float = 0.0
    status: str = ""  # passed, failed, error
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Runtime Timeline Tracker
# ---------------------------------------------------------------------------

class RuntimeTimelineTracker:
    """Tracks execution timeline with real timestamps.
    
    Features:
    - Event-based tracking
    - Real timestamps only
    - Parent-child event relationships
    - Duration calculation
    - Artifact integration
    """
    
    def __init__(self, artifacts_manager=None):
        self.artifacts_manager = artifacts_manager
        self.timeline: Optional[Timeline] = None
        self._event_stack: List[str] = []
        self._event_start_times: Dict[str, float] = {}
    
    def start_timeline(self, run_id: str, test_name: str = "") -> None:
        """Start timeline tracking.
        
        Args:
            run_id: Run identifier
            test_name: Test name
        """
        self.timeline = Timeline(
            run_id=run_id,
            test_name=test_name,
            start_time=datetime.now(timezone.utc).isoformat()
        )
        
        # Record test start event
        self.record_event(
            EventType.TEST_START,
            details={"test_name": test_name}
        )
    
    def end_timeline(self, status: str = "passed") -> None:
        """End timeline tracking and finalize.
        
        Args:
            status: Final status (passed, failed, error)
        """
        if not self.timeline:
            return
        
        # Record test end event
        self.record_event(
            EventType.PASS if status == "passed" else EventType.FAIL if status == "failed" else EventType.ERROR,
            details={"status": status}
        )
        
        self.timeline.end_time = datetime.now(timezone.utc).isoformat()
        self.timeline.status = status
        
        # Calculate total duration
        if self.timeline.start_time:
            start = datetime.fromisoformat(self.timeline.start_time)
            end = datetime.fromisoformat(self.timeline.end_time)
            self.timeline.total_duration_ms = (end - start).total_seconds() * 1000
        
        # Save timeline if artifacts manager available
        if self.artifacts_manager:
            self._save_timeline()
    
    def record_event(
        self,
        event_type: EventType | str,
        details: Dict[str, Any] = None,
        duration_ms: float = 0.0
    ) -> TimelineEvent:
        """Record a timeline event.
        
        Args:
            event_type: Type of event
            details: Event details
            duration_ms: Event duration (if known)
            
        Returns:
            Created event
        """
        if not self.timeline:
            return TimelineEvent(event_type=str(event_type))
        
        # Convert enum to string if needed
        if isinstance(event_type, EventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        # Get parent event ID from stack
        parent_id = self._event_stack[-1] if self._event_stack else None
        
        event = TimelineEvent(
            event_type=event_type_str,
            details=details or {},
            parent_event_id=parent_id,
            duration_ms=duration_ms
        )
        
        self.timeline.events.append(event)
        
        return event
    
    def start_phase(
        self,
        event_type: EventType | str,
        details: Dict[str, Any] = None
    ) -> str:
        """Start a phase event.
        
        Args:
            event_type: Type of event
            details: Event details
            
        Returns:
            Event ID
        """
        if not self.timeline:
            return ""
        
        # Convert enum to string if needed
        if isinstance(event_type, EventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        # Record start event
        event = self.record_event(event_type_str, details)
        
        # Push to stack
        self._event_stack.append(event.event_id)
        self._event_start_times[event.event_id] = time.time()
        
        return event.event_id
    
    def end_phase(
        self,
        event_type: EventType | str,
        success: bool = True,
        details: Dict[str, Any] = None
    ) -> None:
        """End a phase event.
        
        Args:
            event_type: Type of event
            success: Whether phase succeeded
            details: Additional details
        """
        if not self.timeline:
            return
        
        # Pop from stack
        if not self._event_stack:
            return
        
        event_id = self._event_stack.pop()
        start_time = self._event_start_times.get(event_id)
        
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            
            # Find the event and update duration
            for event in self.timeline.events:
                if event.event_id == event_id:
                    event.duration_ms = duration_ms
                    if details:
                        event.details.update(details)
                    event.details["success"] = success
                    break
            
            # Clean up
            if event_id in self._event_start_times:
                del self._event_start_times[event_id]
    
    def record_browser_start(self, details: Dict[str, Any] = None) -> None:
        """Record browser start event."""
        self.start_phase(EventType.BROWSER_START, details)
    
    def record_browser_end(self, success: bool = True, details: Dict[str, Any] = None) -> None:
        """Record browser end event."""
        self.end_phase(EventType.BROWSER_END, success, details)
    
    def record_mcp_start(self, url: str = "", details: Dict[str, Any] = None) -> None:
        """Record MCP start event."""
        if details is None:
            details = {}
        details["url"] = url
        self.start_phase(EventType.MCP_START, details)
    
    def record_mcp_end(self, success: bool = True, details: Dict[str, Any] = None) -> None:
        """Record MCP end event."""
        self.end_phase(EventType.MCP_END, success, details)
    
    def record_dom_capture_start(self, url: str = "") -> None:
        """Record DOM capture start event."""
        self.start_phase(EventType.DOM_CAPTURE_START, {"url": url})
    
    def record_dom_capture_end(self, success: bool = True, size_bytes: int = 0) -> None:
        """Record DOM capture end event."""
        self.end_phase(EventType.DOM_CAPTURE_END, success, {"size_bytes": size_bytes})
    
    def record_cache_hit(self, url: str = "", saved_ms: float = 0.0) -> None:
        """Record cache hit event."""
        self.record_event(
            EventType.DOM_CACHE_HIT,
            details={"url": url, "time_saved_ms": saved_ms}
        )
    
    def record_cache_miss(self, url: str = "", reason: str = "") -> None:
        """Record cache miss event."""
        self.record_event(
            EventType.DOM_CACHE_MISS,
            details={"url": url, "reason": reason}
        )
    
    def record_locator_load_start(self, element_name: str = "") -> None:
        """Record locator load start event."""
        self.start_phase(EventType.LOCATOR_LOAD_START, {"element_name": element_name})
    
    def record_locator_load_end(self, success: bool = True, count: int = 0) -> None:
        """Record locator load end event."""
        self.end_phase(EventType.LOCATOR_LOAD_END, success, {"count": count})
    
    def record_locator_generation_start(self, element_name: str = "") -> None:
        """Record locator generation start event."""
        self.start_phase(EventType.LOCATOR_GENERATION_START, {"element_name": element_name})
    
    def record_locator_generation_end(self, success: bool = True, count: int = 0) -> None:
        """Record locator generation end event."""
        self.end_phase(EventType.LOCATOR_GENERATION_END, success, {"count": count})
    
    def record_validation_start(self, locator: str = "") -> None:
        """Record validation start event."""
        self.start_phase(EventType.VALIDATION_START, {"locator": locator})
    
    def record_validation_end(self, success: bool = True, result: str = "") -> None:
        """Record validation end event."""
        self.end_phase(EventType.VALIDATION_END, success, {"result": result})
    
    def record_healing_start(self, element_name: str = "", locator: str = "") -> None:
        """Record healing start event."""
        self.start_phase(EventType.HEALING_START, {
            "element_name": element_name,
            "locator": locator
        })
    
    def record_healing_end(self, success: bool = True, attempts: int = 0) -> None:
        """Record healing end event."""
        self.end_phase(EventType.HEALING_END, success, {"attempts": attempts})
    
    def record_execution_start(self, action: str = "") -> None:
        """Record execution start event."""
        self.start_phase(EventType.EXECUTION_START, {"action": action})
    
    def record_execution_end(self, success: bool = True, details: Dict[str, Any] = None) -> None:
        """Record execution end event."""
        self.end_phase(EventType.EXECUTION_END, success, details)
    
    def _save_timeline(self) -> None:
        """Save timeline to artifacts."""
        if not self.artifacts_manager or not self.timeline:
            return
        
        try:
            run_dir = self.artifacts_manager.get_run_directory()
            if run_dir:
                timeline_path = run_dir / "timeline.json"
                timeline_path.write_text(self.timeline.model_dump_json(indent=2), encoding='utf-8')
        except Exception as e:
            pass  # Don't fail if artifact saving fails
    
    def get_timeline(self) -> Optional[Timeline]:
        """Get current timeline.
        
        Returns:
            Current timeline or None
        """
        return self.timeline