"""TestCase and related Pydantic v2 models."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class RiskLevel(str, Enum):
    SMOKE = "smoke"
    REGRESSION = "regression"
    EDGE = "edge"


class TestType(str, Enum):
    MANUAL = "manual"
    AUTOMATION = "automation"


class TestStep(BaseModel):
    """A single numbered test step with an action and expected outcome."""

    step_number: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)
    test_data: Optional[str] = None

    @field_validator("action", "expected_result", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


class TestCase(BaseModel):
    """Structured test case — used for both manual docs and automation metadata."""

    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    test_type: TestType
    risk_level: Optional[RiskLevel] = None
    preconditions: Optional[str] = None
    steps: List[TestStep] = Field(default_factory=list)
    expected_result: Optional[str] = None
    postconditions: Optional[str] = None
    user_story: Optional[str] = None
    acceptance_criteria: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Automation-specific
    script_path: Optional[str] = None
    locators: List[str] = Field(default_factory=list)

    # Manual test-specific
    file_path: Optional[str] = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def check_steps_or_expected(self) -> "TestCase":
        if not self.steps and not self.expected_result:
            raise ValueError("TestCase must have at least one step or an expected_result")
        return self

    def to_markdown(self, application_url: Optional[str] = None) -> str:
        """Render this test case as a Markdown document."""
        from datetime import datetime, timezone

        risk = (self.risk_level.value if self.risk_level else "regression").upper()
        tags_str = ", ".join(f"`{t}`" for t in self.tags)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines: List[str] = [
            f"# {self.name}",
            "",
            "## Overview",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| **Risk Level** | {risk} |",
            f"| **Tags** | {tags_str} |",
            f"| **Generated** | {generated_at} |",
        ]
        if application_url:
            lines.append(f"| **Application URL** | {application_url} |")

        lines += ["", "## Description", "", self.description]

        if self.preconditions:
            lines += ["", "## Preconditions", "", self.preconditions]

        lines += [
            "",
            "## Test Steps",
            "",
            "| # | Action | Expected Result | Test Data |",
            "|---|--------|----------------|-----------|",
        ]
        for step in self.steps:
            data = step.test_data or ""
            lines.append(
                f"| {step.step_number} | {step.action} | {step.expected_result} | {data} |"
            )

        if self.expected_result:
            lines += ["", "## Expected Result", "", self.expected_result]

        if self.postconditions:
            lines += ["", "## Postconditions", "", self.postconditions]

        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

class QualityViolation(BaseModel):
    field: str
    message: str


class TestCaseQualityGate:
    """Validates TestCase instances before they are committed to disk or DB.

    Rules (all must pass for a test case to be accepted):
      1. name       — non-empty, ≥ 5 chars, no placeholder words
      2. description — non-empty, ≥ 10 chars
      3. steps       — at least 2 steps for manual tests
      4. each step   — action ≥ 5 chars, expected_result ≥ 5 chars
      5. expected_result — present at the test-case level (overall outcome)
      6. No placeholder bodies (TODO, FIXME, TBD, <placeholder>)
    """

    _PLACEHOLDER_RE = __import__("re").compile(
        r"\b(TODO|FIXME|TBD|placeholder|lorem ipsum|xxx)\b", __import__("re").IGNORECASE
    )
    _MIN_NAME_LEN = 5
    _MIN_DESC_LEN = 10
    _MIN_STEP_TEXT = 5
    _MIN_STEPS_MANUAL = 2

    def validate(self, tc: TestCase) -> List[QualityViolation]:
        violations: List[QualityViolation] = []

        if len(tc.name) < self._MIN_NAME_LEN:
            violations.append(
                QualityViolation(
                    field="name",
                    message=f"Name too short ({len(tc.name)} chars, need ≥ {self._MIN_NAME_LEN})",
                )
            )
        if self._PLACEHOLDER_RE.search(tc.name):
            violations.append(
                QualityViolation(field="name", message="Name contains placeholder text")
            )

        if len(tc.description) < self._MIN_DESC_LEN:
            violations.append(
                QualityViolation(
                    field="description",
                    message=f"Description too short ({len(tc.description)} chars, need ≥ {self._MIN_DESC_LEN})",
                )
            )

        if tc.test_type == TestType.MANUAL and len(tc.steps) < self._MIN_STEPS_MANUAL:
            violations.append(
                QualityViolation(
                    field="steps",
                    message=f"Manual test needs ≥ {self._MIN_STEPS_MANUAL} steps, got {len(tc.steps)}",
                )
            )

        for i, step in enumerate(tc.steps, 1):
            if len(step.action) < self._MIN_STEP_TEXT:
                violations.append(
                    QualityViolation(
                        field=f"steps[{i}].action",
                        message=f"Step {i} action too short",
                    )
                )
            if len(step.expected_result) < self._MIN_STEP_TEXT:
                violations.append(
                    QualityViolation(
                        field=f"steps[{i}].expected_result",
                        message=f"Step {i} expected_result too short",
                    )
                )
            if self._PLACEHOLDER_RE.search(step.action) or self._PLACEHOLDER_RE.search(
                step.expected_result
            ):
                violations.append(
                    QualityViolation(
                        field=f"steps[{i}]",
                        message=f"Step {i} contains placeholder text",
                    )
                )

        if not tc.expected_result:
            violations.append(
                QualityViolation(
                    field="expected_result",
                    message="Missing overall expected_result",
                )
            )

        return violations

    def passes(self, tc: TestCase) -> bool:
        return not self.validate(tc)

    def assert_passes(self, tc: TestCase) -> None:
        violations = self.validate(tc)
        if violations:
            msgs = "; ".join(f"{v.field}: {v.message}" for v in violations)
            raise ValueError(f"TestCase '{tc.name}' failed quality gate — {msgs}")
