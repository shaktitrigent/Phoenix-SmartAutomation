"""API response contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from phoenix_shared.models.locator import Locator


class ResponseMetadata(BaseModel):
    generated_at: str
    version: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class TestGenerationResponse(BaseModel):
    manual_tests: List[Dict[str, Any]] = []
    automation_tests: List[Dict[str, Any]] = []
    metadata: Optional[Dict[str, Any]] = None


class LocatorDiscoveryResponse(BaseModel):
    locators: List[Dict[str, Any]] = []
    recommended_locator: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class FailureAnalysisResponse(BaseModel):
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence: float = 0.0
    related_locators: List[Dict[str, Any]] = []
    metadata: Optional[Dict[str, Any]] = None
