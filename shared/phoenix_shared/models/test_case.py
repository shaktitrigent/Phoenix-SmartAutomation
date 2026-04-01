"""TestCase and related Pydantic models."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    SMOKE = "smoke"
    REGRESSION = "regression"
    EDGE = "edge"


class TestType(str, Enum):
    MANUAL = "manual"
    AUTOMATION = "automation"


class TestStep(BaseModel):
    step_number: int
    action: str
    expected_result: str
    test_data: Optional[str] = None


class TestCase(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    test_type: TestType
    risk_level: Optional[RiskLevel] = None
    steps: List[TestStep] = Field(default_factory=list)
    expected_result: Optional[str] = None
    user_story: Optional[str] = None
    acceptance_criteria: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    # Automation-specific
    script_path: Optional[str] = None
    locators: List[str] = Field(default_factory=list)
    # Manual test-specific
    file_path: Optional[str] = None
    preconditions: Optional[str] = None
    postconditions: Optional[str] = None
