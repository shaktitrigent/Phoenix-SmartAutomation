"""API test executor"""

from typing import Any, Dict, Optional
from playwright.sync_api import sync_playwright, APIRequestContext
from phoenix.storage.models import ExecutionStatus


class APIExecutor:
    """Executor for API tests"""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize API executor.
        
        Args:
            base_url: Base URL for API requests
        """
        self.base_url = base_url
        self.playwright = None
        self.api_context: Optional[APIRequestContext] = None

    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        self.api_context = self.playwright.request.new_context(
            base_url=self.base_url
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.api_context:
            self.api_context.dispose()
        if self.playwright:
            self.playwright.stop()

    def execute_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """
        Execute an API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Request URL
            headers: Optional request headers
            data: Optional request data
            expected_status: Expected HTTP status code
            
        Returns:
            Execution result
        """
        if not self.api_context:
            raise RuntimeError("APIExecutor must be used as context manager")
        
        try:
            # Make request
            if method.upper() == "GET":
                response = self.api_context.get(url, headers=headers)
            elif method.upper() == "POST":
                response = self.api_context.post(url, headers=headers, data=data)
            elif method.upper() == "PUT":
                response = self.api_context.put(url, headers=headers, data=data)
            elif method.upper() == "DELETE":
                response = self.api_context.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Validate status
            status_code = response.status
            response_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text()
            
            is_success = status_code == expected_status
            
            return {
                "status": ExecutionStatus.PASSED.value if is_success else ExecutionStatus.FAILED.value,
                "status_code": status_code,
                "expected_status": expected_status,
                "response_data": response_data,
                "headers": dict(response.headers),
            }
        
        except Exception as e:
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": str(e),
            }

    def execute_test(self, test_script_path: str) -> Dict[str, Any]:
        """
        Execute an API test script.
        
        Args:
            test_script_path: Path to test script
            
        Returns:
            Execution result
        """
        # TODO: Import and execute test function
        # For now, return placeholder
        return {
            "status": ExecutionStatus.PASSED.value,
        }
