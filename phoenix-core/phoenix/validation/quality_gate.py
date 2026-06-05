"""Quality Gate — validates parsed test cases before automation generation.

Blocks generation when tests contain unresolved issues that would produce
broken or non-executable Playwright scripts.
"""

from __future__ import annotations

import re
from typing import Dict, List

from pydantic import BaseModel

from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class QualityGateResult(BaseModel):
    passed: bool
    blocking_errors: List[str]
    warnings: List[str]
    confidence_score: float
    automatable_steps: int
    total_steps: int

    @property
    def pass_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.automatable_steps / self.total_steps


# ---------------------------------------------------------------------------
# Business-text URL detection helpers
# ---------------------------------------------------------------------------

# Patterns that indicate the expected_state is derived from business text,
# not a real URL path.
_BUSINESS_TEXT_PATTERNS: List[re.Pattern] = [
    re.compile(r"page\s+is\s+visible", re.IGNORECASE),
    re.compile(r"should\s+be\s+displayed", re.IGNORECASE),
    re.compile(r"is\s+shown", re.IGNORECASE),
    re.compile(r"\bappears?\b", re.IGNORECASE),
    re.compile(r"[A-Z][a-z]+\s+[A-Z][a-z]+\s+page", re.IGNORECASE),  # "Add Employee page"
    re.compile(r"\b(?:page|screen|view)\s+(?:is|should|must)\b", re.IGNORECASE),
]

# Patterns that look like real URL paths (not business text)
_URL_PATH_PATTERN = re.compile(r"[./]")


def _looks_like_business_text(text: str) -> bool:
    """Return True if *text* looks like business language, not a URL."""
    # Has word spaces but no URL path characters → business text
    word_count = len(text.split())
    has_path = bool(_URL_PATH_PATTERN.search(text))
    if any(p.search(text) for p in _BUSINESS_TEXT_PATTERNS):
        return True
    if word_count > 3 and not has_path:
        return True
    return False


# ---------------------------------------------------------------------------
# Required test data field patterns
# ---------------------------------------------------------------------------

_FILL_REQUIRES_DATA = {
    "username_field": "username",
    "password_field": "password",
    "login_form": "username",
}

_MANUAL_REVIEW_MARKERS = re.compile(
    r"\[needs?\s+manual\s+review\]|\[manual\s+review\]",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------

class QualityGate:
    """Validates parsed test cases before automation generation."""

    CONFIDENCE_THRESHOLD = 0.6

    BLOCKING_CONDITIONS = [
        "contains_manual_review_marker",
        "has_unresolved_locators",
        "has_unknown_actions",
        "has_invalid_assertions",
        "confidence_below_threshold",
        "missing_required_test_data",
    ]

    def validate(
        self, parsed_case: ParsedTestCase, test_data: Dict | None = None
    ) -> QualityGateResult:
        """Run all validations and return a result with pass/fail details."""
        test_data = test_data or {}
        blocking_errors: List[str] = []
        warnings: List[str] = []

        for step in parsed_case.steps:
            # 1. Manual review markers
            if _MANUAL_REVIEW_MARKERS.search(step.raw_text):
                blocking_errors.append(
                    f"manual_review_marker: Step contains [NEEDS MANUAL REVIEW]: "
                    f"{step.raw_text!r}"
                )

            # 2. Unknown actions
            if step.action == ActionType.UNKNOWN:
                blocking_errors.append(
                    f"has_unknown_actions: Cannot determine action for: {step.raw_text!r}"
                )

            # 3. Unresolved locators for action steps
            if (
                step.action in (ActionType.CLICK, ActionType.FILL, ActionType.SELECT)
                and not step.target_element
                and not step.target_locator
            ):
                blocking_errors.append(
                    f"has_unresolved_locators: No element resolved for action step: "
                    f"{step.raw_text!r}"
                )

            # 4. Invalid assertions
            errors = self._check_assertion_validity(step)
            blocking_errors.extend(errors)

            # 5. Step-level validation errors bubble up as blocking
            for err in step.validation_errors:
                if err not in blocking_errors:
                    blocking_errors.append(err)

        # 6. Overall confidence gate
        if parsed_case.overall_confidence < self.CONFIDENCE_THRESHOLD:
            blocking_errors.append(
                f"confidence_below_threshold: Overall confidence "
                f"{parsed_case.overall_confidence:.2f} < {self.CONFIDENCE_THRESHOLD}"
            )

        # 7. Required test data check
        missing_data = self._check_required_test_data(parsed_case, test_data)
        for field in missing_data:
            warnings.append(
                f"missing_required_test_data: test_data['{field}'] is missing"
            )

        # De-duplicate while preserving order
        blocking_errors = list(dict.fromkeys(blocking_errors))
        warnings = list(dict.fromkeys(warnings))

        automatable = sum(
            1 for s in parsed_case.steps if not s.is_blocking
        )

        return QualityGateResult(
            passed=len(blocking_errors) == 0,
            blocking_errors=blocking_errors,
            warnings=warnings,
            confidence_score=parsed_case.overall_confidence,
            automatable_steps=automatable,
            total_steps=len(parsed_case.steps),
        )

    def _check_assertion_validity(self, intent: SemanticIntent) -> List[str]:
        """Check that assertion steps are grounded in DOM, not business text."""
        errors: List[str] = []

        if intent.action != ActionType.ASSERT_URL:
            return errors

        expected = intent.expected_state or ""
        if not expected:
            return errors

        if self._is_invalid_url_assertion(expected):
            errors.append(
                f"has_invalid_assertions: URL assertion contains business text, "
                f"not a real URL path: {expected!r} — "
                f"use a real path like r'.*/leave/apply'"
            )

        return errors

    def _is_invalid_url_assertion(self, expected: str) -> bool:
        """Detect assertions generated from business text rather than real URL paths."""
        return _looks_like_business_text(expected)

    def _check_required_test_data(
        self, parsed_case: ParsedTestCase, test_data: Dict
    ) -> List[str]:
        """Return field names that are required but missing from test_data."""
        missing: List[str] = []
        for step in parsed_case.steps:
            if step.target_element in _FILL_REQUIRES_DATA:
                required_key = _FILL_REQUIRES_DATA[step.target_element]
                if required_key not in test_data:
                    missing.append(required_key)
        return missing
