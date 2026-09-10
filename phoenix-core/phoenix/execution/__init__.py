"""Test execution engine"""

from phoenix.execution.runner import TestRunner

# Intelligent Runtime components
try:
    from phoenix.execution.intelligent_runtime import IntelligentRuntime
    from phoenix.execution.intelligent_page import IntelligentPage, create_intelligent_page
    from phoenix.execution.dom_snapshot_manager import DOMSnapshotManager
    from phoenix.execution.locator_repository import LocatorRepository
    from phoenix.execution.runtime_metrics import RuntimeMetricsCollector
    from phoenix.execution.runtime_timeline import RuntimeTimelineTracker
    __all__ = [
        "TestRunner",
        "IntelligentRuntime",
        "IntelligentPage",
        "create_intelligent_page",
        "DOMSnapshotManager",
        "LocatorRepository",
        "RuntimeMetricsCollector",
        "RuntimeTimelineTracker",
    ]
except ImportError:
    __all__ = ["TestRunner"]
