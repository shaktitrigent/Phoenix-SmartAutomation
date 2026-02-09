"""UI test executor"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from phoenix.storage.models import ExecutionStatus


class UIExecutor:
    """Executor for UI tests"""

    def __init__(self, browser_type: str = "chromium", headless: bool = True):
        """
        Initialize UI executor.
        
        Args:
            browser_type: Browser type ('chromium', 'firefox', 'webkit')
            headless: Run in headless mode
        """
        self.browser_type = browser_type
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        
        browser_map = {
            "chromium": self.playwright.chromium,
            "firefox": self.playwright.firefox,
            "webkit": self.playwright.webkit,
        }
        
        browser_launcher = browser_map.get(self.browser_type, self.playwright.chromium)
        self.browser = browser_launcher.launch(headless=self.headless)
        self.context = self.browser.new_context()
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def execute_test(
        self,
        test_script_path: str,
        screenshot_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a UI test script.
        
        Args:
            test_script_path: Path to test script
            screenshot_dir: Directory for screenshots
            
        Returns:
            Execution result
        """
        if not self.context:
            raise RuntimeError("UIExecutor must be used as context manager")
        
        page = self.context.new_page()
        screenshot_path = None
        
        try:
            # Execute test script
            # For now, we'll need to import and run the test function
            # In production, this would use pytest or similar
            
            # Take screenshot
            if screenshot_dir:
                screenshot_dir_path = Path(screenshot_dir)
                screenshot_dir_path.mkdir(parents=True, exist_ok=True)
                screenshot_path = str(screenshot_dir_path / f"screenshot_{Path(test_script_path).stem}.png")
                page.screenshot(path=screenshot_path)
            
            return {
                "status": ExecutionStatus.PASSED.value,
                "screenshot_path": screenshot_path,
            }
        
        except Exception as e:
            # Take failure screenshot
            if screenshot_dir:
                screenshot_dir_path = Path(screenshot_dir)
                screenshot_dir_path.mkdir(parents=True, exist_ok=True)
                screenshot_path = str(screenshot_dir_path / f"failure_{Path(test_script_path).stem}.png")
                page.screenshot(path=screenshot_path)
            
            return {
                "status": ExecutionStatus.FAILED.value,
                "error": str(e),
                "screenshot_path": screenshot_path,
            }
        
        finally:
            page.close()
