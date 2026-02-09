"""Test generation layer"""

from phoenix.generators.manual import ManualTestGenerator
from phoenix.generators.automation import AutomationTestGenerator
from phoenix.generators.locator import LocatorDiscovery

__all__ = [
    "ManualTestGenerator",
    "AutomationTestGenerator",
    "LocatorDiscovery",
]
