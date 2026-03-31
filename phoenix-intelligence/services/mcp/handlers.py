"""MCP response helpers.

With the new stdio-based MCPClient the heavy lifting (navigate, snapshot) is
done inside the client itself.  This module is kept for any future response
post-processing but currently just re-exports convenience utilities.
"""

from typing import Dict, Any, List


def extract_text_from_snapshot(snapshot_text: str) -> str:
    """Return the snapshot text trimmed and ready for prompt injection."""
    return snapshot_text.strip()


def extract_test_steps(test_case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract test steps from a test case dictionary."""
    return test_case.get("steps", [])


def extract_locators(test_case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract locators from a test case dictionary."""
    return test_case.get("locators", [])
