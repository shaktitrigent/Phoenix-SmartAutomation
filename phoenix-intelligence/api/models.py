"""Pydantic models for the intelligence API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TestGenerationOptions(BaseModel):
    """Options for test generation."""

    test_type: str = Field(default="both", description="manual, automation, or both")
    risk_level: Optional[str] = Field(default=None, description="smoke, regression, edge")
    output_style: Optional[str] = Field(default=None, description="markdown or gherkin")


class TestGenerationRequest(BaseModel):
    """Request payload for test generation."""

    user_story: str
    application_url: Optional[str] = None
    acceptance_criteria: List[str] = []
    options: Optional[TestGenerationOptions] = None


class ManualTestStep(BaseModel):
    """Structured manual test step."""

    step_number: Optional[int] = None
    action: str
    expected_result: Optional[str] = None
    test_data: Optional[str] = None


class ManualTestCase(BaseModel):
    """Manual test case schema."""

    name: str
    description: str
    preconditions: Optional[str] = None
    steps: List[ManualTestStep]
    expected_result: Optional[str] = None
    postconditions: Optional[str] = None
    risk_level: Optional[str] = None
    tags: List[str] = []


class Locator(BaseModel):
    """Locator schema for UI elements."""

    element: Optional[str] = None
    selector: Optional[str] = None
    strategy: Optional[str] = None
    confidence: Optional[float] = None


class AutomationTestCase(BaseModel):
    """Automation test case schema."""

    name: str
    description: str
    test_steps: List[str] = []
    locators: List[Locator] = []
    script_template: Optional[str] = None
    script_code: Optional[str] = None
    risk_level: Optional[str] = None
    tags: List[str] = []


class ResponseMetadata(BaseModel):
    """Response metadata for tracing and versioning."""

    request_id: Optional[str] = None
    version: Optional[str] = None
    generated_at: Optional[str] = None


class TestGenerationResponse(BaseModel):
    """Response payload for test generation."""

    manual_tests: List[ManualTestCase] = []
    automation_tests: List[AutomationTestCase] = []
    metadata: Dict[str, Any] = {}


class LocatorDiscoveryRequest(BaseModel):
    """Request payload for locator discovery."""

    page_url: str
    elements: List[str]
    dom_snapshot: Optional[str] = None


class LocatorDiscoveryResponse(BaseModel):
    """Response payload for locator discovery."""

    locators: List[Locator] = []
    recommended_locator: Optional[Locator] = None
    metadata: Dict[str, Any] = {}


class FailureAnalysisRequest(BaseModel):
    """Request payload for failure analysis."""

    error_message: str
    traceback: Optional[str] = None
    test_case_id: Optional[str] = None
    test_context: Optional[Dict[str, Any]] = None


class FailureAnalysisResponse(BaseModel):
    """Response payload for failure analysis."""

    root_cause: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None
    related_locators: List[Dict[str, Any]] = []
    prevention: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AutomateRequest(BaseModel):
    """Request payload — generate automation scripts from pre-written manual tests."""

    manual_tests: List[Dict[str, Any]] = Field(
        description="Structured manual test dicts parsed from manual_tests/ directory"
    )
    application_url: Optional[str] = Field(default=None, description="Application URL under test")


class AutomateResponse(BaseModel):
    """Response payload for automation-from-manual generation."""

    automation_tests: List[AutomationTestCase] = []
    metadata: Dict[str, Any] = {}


class ScriptFixRequest(BaseModel):
    """Request payload for fixing a failing automation script."""

    script_code: str = Field(description="The full Python script that is failing")
    error_message: str = Field(description="Exact error/exception text from pytest")
    error_type: str = Field(
        default="unknown",
        description="Classified error type: locator_not_found, timeout, assertion_failure, "
                    "stale_element, navigation_failure, or unknown",
    )
    test_name: str = Field(default="unknown_test", description="Name of the failing test function")
    application_url: Optional[str] = Field(default=None, description="Application URL under test")


class ScriptFixResponse(BaseModel):
    """Response payload for a fixed script."""

    fixed_script: str = Field(description="The corrected, complete Python script")
    changed: bool = Field(description="True if the script was actually modified")
    fix_summary: str = Field(description="One-line description of what was changed")
    metadata: Dict[str, Any] = {}
