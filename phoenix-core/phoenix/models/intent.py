"""Structured Semantic Intent Model.

Transforms flat acceptance-criteria text into typed, validated data structures
that downstream generators and quality gates can reason about.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_TEXT = "assert_text"
    ASSERT_URL = "assert_url"
    WAIT = "wait"
    UNKNOWN = "unknown"


class LocatorValue(BaseModel):
    """Lightweight locator reference resolved from the registry."""

    element_name: str
    strategy: str = "css"
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def to_playwright(self) -> str:
        strategy_map = {
            "role": lambda: f'page.get_by_role("{self.value}")',
            "label": lambda: f'page.get_by_label("{self.value}")',
            "placeholder": lambda: f'page.get_by_placeholder("{self.value}")',
            "text": lambda: f'page.get_by_text("{self.value}")',
            "test-id": lambda: f'page.get_by_test_id("{self.value}")',
            "css": lambda: f'page.locator("{self.value}")',
            "xpath": lambda: f'page.locator("{self.value}")',
        }
        fn = strategy_map.get(self.strategy, strategy_map["css"])
        return fn()


class SemanticIntent(BaseModel):
    """Structured representation of a single test step."""

    raw_text: str
    intent_type: Literal["precondition", "action", "assertion"]
    action: ActionType = ActionType.UNKNOWN
    target_page: Optional[str] = None
    target_element: Optional[str] = None
    target_locator: Optional[LocatorValue] = None
    input_value: Optional[str] = None
    expected_state: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_review: bool = False
    validation_errors: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _apply_review_flag(self) -> "SemanticIntent":
        if self.confidence < 0.5 and not self.requires_review:
            self.requires_review = True
        return self

    @property
    def is_blocking(self) -> bool:
        """True when this step would prevent automation from running."""
        return bool(self.validation_errors) or self.action == ActionType.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ParsedTestCase(BaseModel):
    """A complete test case with all steps parsed into semantic intents."""

    id: str = ""
    title: str
    source_format: Literal["gherkin", "plain_english", "markdown"] = "plain_english"
    steps: List[SemanticIntent] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_automatable: bool = True
    blocking_issues: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_automatable(self) -> "ParsedTestCase":
        issues = []
        for step in self.steps:
            issues.extend(step.validation_errors)
            if step.action == ActionType.UNKNOWN:
                issues.append(f"Unknown action in step: {step.raw_text!r}")
        self.blocking_issues = list(dict.fromkeys(issues))
        self.is_automatable = len(self.blocking_issues) == 0
        if self.steps:
            self.overall_confidence = sum(s.confidence for s in self.steps) / len(self.steps)
        return self
