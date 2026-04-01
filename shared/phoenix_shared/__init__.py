"""Phoenix Shared — Pydantic contracts shared across phoenix-core and phoenix-intelligence."""

from phoenix_shared.models.test_case import TestCase, TestStep, RiskLevel, TestType
from phoenix_shared.models.locator import Locator, LocatorStrategy
from phoenix_shared.models.automation_script import AutomationScript
from phoenix_shared.contracts.requests import (
    TestGenerationRequest,
    LocatorDiscoveryRequest,
    FailureAnalysisRequest,
)
from phoenix_shared.contracts.responses import (
    TestGenerationResponse,
    LocatorDiscoveryResponse,
    FailureAnalysisResponse,
)

__all__ = [
    "TestCase",
    "TestStep",
    "RiskLevel",
    "TestType",
    "Locator",
    "LocatorStrategy",
    "AutomationScript",
    "TestGenerationRequest",
    "LocatorDiscoveryRequest",
    "FailureAnalysisRequest",
    "TestGenerationResponse",
    "LocatorDiscoveryResponse",
    "FailureAnalysisResponse",
]
