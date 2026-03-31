"""Failure analysis agent"""

from typing import Dict, Any, List, Optional
from services.agents.base import BaseAgent


class FailureAnalyzerAgent(BaseAgent):
    """Agent specialized in analyzing test failures"""

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Analyze test failure and suggest fixes.
        
        Args:
            input_data: Dictionary containing:
                - test_case_id: Test case ID
                - error_message: Error message from test failure
                - error_traceback: Full traceback (optional)
                - screenshot_path: Path to failure screenshot (optional)
                - test_logs: Test execution logs (optional)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary containing:
                - failure_reason: Identified reason for failure
                - suggested_fixes: List of suggested fixes
                - confidence: Confidence score (0-1)
                - similar_failures: Similar past failures (if any)
        """
        test_case_id = input_data.get("test_case_id")
        error_message = input_data.get("error_message", "")
        error_traceback = input_data.get("error_traceback", "")
        screenshot_path = input_data.get("screenshot_path")
        test_logs = input_data.get("test_logs", [])
        
        # Get knowledge context for failure patterns
        knowledge_context = self.get_knowledge_context(query=error_message)
        
        # Analyze failure
        result = {
            "failure_reason": self._identify_failure_reason(error_message, error_traceback),
            "suggested_fixes": [],
            "confidence": 0.0,
            "similar_failures": [],
            "metadata": {
                "test_case_id": test_case_id,
                "error_message": error_message,
                "has_screenshot": bool(screenshot_path),
                "knowledge_context_used": bool(knowledge_context),
            }
        }
        
        # Generate suggested fixes
        result["suggested_fixes"] = self._suggest_fixes(
            result["failure_reason"], error_message, knowledge_context
        )
        
        # Calculate confidence
        result["confidence"] = self._calculate_confidence(
            error_message, result["failure_reason"], result["suggested_fixes"]
        )
        
        return result

    def _identify_failure_reason(self, error_message: str, traceback: str) -> str:
        """
        Identify the reason for test failure.
        
        This will be enhanced with MCP integration.
        """
        error_lower = error_message.lower()
        
        # Common failure patterns
        if "timeout" in error_lower or "waiting" in error_lower:
            return "element_timeout"
        elif "not found" in error_lower or "locator" in error_lower:
            return "locator_not_found"
        elif "assertion" in error_lower or "assert" in error_lower:
            return "assertion_failure"
        elif "network" in error_lower or "connection" in error_lower:
            return "network_error"
        elif "javascript" in error_lower or "js error" in error_lower:
            return "javascript_error"
        else:
            return "unknown_error"

    def _suggest_fixes(
        self, failure_reason: str, error_message: str, knowledge_context: str
    ) -> List[Dict[str, Any]]:
        """
        Suggest fixes based on failure reason.
        
        This will be enhanced with MCP integration.
        """
        fixes = []
        
        if failure_reason == "element_timeout":
            fixes.append({
                "priority": 1,
                "fix": "Increase wait timeout or add explicit wait for element",
                "code_example": "page.wait_for_selector('#element', timeout=10000)",
            })
            fixes.append({
                "priority": 2,
                "fix": "Verify element locator is still valid",
                "code_example": "Check if locator strategy needs updating",
            })
        
        elif failure_reason == "locator_not_found":
            fixes.append({
                "priority": 1,
                "fix": "Update locator to use more stable strategy (data-testid or role)",
                "code_example": "Use page.get_by_role('button', name='Submit') instead of CSS selector",
            })
            fixes.append({
                "priority": 2,
                "fix": "Verify element exists on page and is visible",
                "code_example": "Check page HTML or use page.locator().is_visible()",
            })
        
        elif failure_reason == "assertion_failure":
            fixes.append({
                "priority": 1,
                "fix": "Review expected vs actual values",
                "code_example": "Add logging to see actual values before assertion",
            })
        
        elif failure_reason == "network_error":
            fixes.append({
                "priority": 1,
                "fix": "Check network connectivity and API endpoints",
                "code_example": "Verify API is accessible and responding",
            })
        
        # Add generic fix if no specific fixes found
        if not fixes:
            fixes.append({
                "priority": 1,
                "fix": "Review error message and test logs for details",
                "code_example": "Check test execution logs and screenshots",
            })
        
        return fixes

    def _calculate_confidence(
        self, error_message: str, failure_reason: str, suggested_fixes: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for the analysis"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence if we have specific fixes
        if suggested_fixes:
            confidence += 0.2
        
        # Increase confidence if failure reason is specific (not unknown)
        if failure_reason != "unknown_error":
            confidence += 0.2
        
        # Increase confidence if error message is detailed
        if len(error_message) > 50:
            confidence += 0.1
        
        return min(confidence, 1.0)
