"""Phoenix framework exception hierarchy."""

from __future__ import annotations

from typing import List


class PhoenixError(Exception):
    """Base exception for the Phoenix framework."""


class LocatorResolutionError(PhoenixError):
    """Raised when a UI element locator cannot be resolved."""


class QualityGateFailedError(PhoenixError):
    """Raised when a test case fails the quality gate validation.

    Attributes:
        errors: List of blocking error messages that caused the failure.
    """

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        summary = "; ".join(errors[:3])
        if len(errors) > 3:
            summary += f" (and {len(errors) - 3} more)"
        super().__init__(f"Quality gate failed: {summary}")


class MappingConfidenceLowError(PhoenixError):
    """Raised when action-mapping confidence is below the required threshold."""


class DOMAnalysisError(PhoenixError):
    """Raised when DOM analysis fails or produces an incomplete result."""


class ManualTestNotFoundError(PhoenixError):
    """Raised when no manual test files can be located."""


class ScriptGenerationError(PhoenixError):
    """Raised when the intelligence server fails to produce a valid script."""
