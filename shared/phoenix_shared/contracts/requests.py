"""API request contracts."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class GenerationOptions(BaseModel):
    test_type: str = "both"
    risk_level: Optional[str] = None


class TestGenerationRequest(BaseModel):
    user_story: str
    application_url: Optional[str] = None
    acceptance_criteria: List[str] = []
    options: Optional[GenerationOptions] = None


class LocatorDiscoveryRequest(BaseModel):
    page_url: str
    elements: List[str]
    dom_snapshot: Optional[str] = None


class FailureAnalysisRequest(BaseModel):
    error_message: str
    traceback: Optional[str] = None
    test_case_id: Optional[str] = None
    screenshot_path: Optional[str] = None
