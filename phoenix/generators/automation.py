"""Automation script generator"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from phoenix.storage.models import TestType
from phoenix.agents.registry import AgentRegistry


class AutomationTestGenerator:
    """Generator for automation test scripts"""

    def __init__(self, agent_registry: AgentRegistry, output_dir: str = "./test_results"):
        """
        Initialize automation test generator.
        
        Args:
            agent_registry: Agent registry instance
            output_dir: Directory to save generated scripts
        """
        self.agent_registry = agent_registry
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        user_story: str,
        application_url: Optional[str] = None,
        acceptance_criteria: List[str] = None,
        test_type: str = "ui",  # 'ui' or 'api'
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate automation test scripts.
        
        Args:
            user_story: User story text
            application_url: Application URL to test
            acceptance_criteria: List of acceptance criteria
            test_type: Type of test ('ui' or 'api')
            **kwargs: Additional parameters
            
        Returns:
            List of automation test dictionaries with script paths
        """
        # Use test generator agent
        # Remove test_type from kwargs to avoid conflict
        agent_kwargs = {k: v for k, v in kwargs.items() if k != "test_type"}
        result = self.agent_registry.generate_tests(
            user_story=user_story,
            application_url=application_url,
            acceptance_criteria=acceptance_criteria or [],
            test_type="automation",
            **agent_kwargs
        )
        
        automation_tests = result.get("automation_tests", []) or result.get("tests", [])
        
        # Generate Playwright scripts
        formatted_tests = []
        for idx, test in enumerate(automation_tests, 1):
            script_path = self._generate_playwright_script(
                test, user_story, application_url, acceptance_criteria or [], test_type, idx
            )
            
            formatted_test = {
                "name": test.get("name", f"Automation Test {idx}"),
                "description": test.get("description", user_story),
                "script_path": str(script_path),
                "test_type": TestType.AUTOMATION.value,
                "test_category": test_type,  # 'ui' or 'api'
                "locators": test.get("locators", []),
                "tags": test.get("tags", ["automation", "generated"]),
            }
            formatted_tests.append(formatted_test)
        
        return formatted_tests

    def _generate_playwright_script(
        self,
        test: Dict[str, Any],
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        test_category: str,
        test_index: int
    ) -> Path:
        """
        Generate Playwright Python script.
        
        Args:
            test: Test case dictionary
            user_story: User story text
            acceptance_criteria: Acceptance criteria
            test_category: Test category ('ui' or 'api')
            test_index: Test index number
            
        Returns:
            Path to generated script
        """
        # Generate safe filename
        safe_name = "".join(c for c in test.get("name", f"test_{test_index}") if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_').lower()
        script_filename = f"test_{test_index:03d}_{safe_name}.py"
        script_path = self.output_dir / script_filename
        
        # Generate script content
        if test_category == "ui":
            script_content = self._generate_ui_script(test, user_story, application_url, acceptance_criteria)
        else:
            script_content = self._generate_api_script(test, user_story, application_url, acceptance_criteria)
        
        # Write script file
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        return script_path

    def _generate_ui_script(
        self, test: Dict[str, Any], user_story: str, application_url: Optional[str], acceptance_criteria: List[str]
    ) -> str:
        """Generate UI test script"""
        test_name = test.get('name', 'test').lower().replace(' ', '_').replace('-', '_')
        # Remove special characters for function name
        test_name = "".join(c for c in test_name if c.isalnum() or c == '_')
        
        lines = [
            '"""',
            f"Generated Playwright UI Test",
            f"User Story: {user_story}",
            f"Application URL: {application_url or 'N/A'}",
            '"""',
            "",
            "import pytest",
            "from playwright.sync_api import Page, expect",
            "",
            "",
            f"def test_{test_name}(page: Page):",
            f'    """{test.get("description", user_story)}"""',
            "",
        ]
        
        # Add navigation if URL provided
        if application_url:
            lines.append(f"    # Navigate to application")
            lines.append(f'    page.goto("{application_url}")')
            lines.append(f"    page.wait_for_load_state('networkidle')")
            lines.append("")
        
        # Add test steps based on acceptance criteria
        for idx, criteria in enumerate(acceptance_criteria[:5], 1):  # Limit to 5
            lines.append(f"    # Step {idx}: {criteria}")
            # Generate basic Playwright code from criteria
            criteria_lower = criteria.lower()
            if "click" in criteria_lower or "button" in criteria_lower:
                # Try to extract button text
                if "login" in criteria_lower:
                    lines.append('    page.get_by_role("button", name="Login").click()')
                elif "submit" in criteria_lower:
                    lines.append('    page.get_by_role("button", name="Submit").click()')
                else:
                    lines.append(f'    # TODO: Click button for: {criteria}')
            elif "enter" in criteria_lower or "input" in criteria_lower or "type" in criteria_lower:
                if "email" in criteria_lower:
                    lines.append('    page.get_by_label("Email").fill("test@example.com")')
                elif "password" in criteria_lower:
                    lines.append('    page.get_by_label("Password").fill("password123")')
                else:
                    lines.append(f'    # TODO: Fill input for: {criteria}')
            elif "verify" in criteria_lower or "check" in criteria_lower or "assert" in criteria_lower:
                lines.append(f'    # TODO: Add assertion for: {criteria}')
            else:
                lines.append(f'    # TODO: Implement: {criteria}')
            lines.append("")
        
        # Add basic assertions
        lines.append("    # Assertions")
        if application_url:
            lines.append(f'    expect(page).to_have_url(containing="{application_url.split("/")[-1]}"))')
        lines.append("")
        
        return "\n".join(lines)

    def _generate_api_script(
        self, test: Dict[str, Any], user_story: str, application_url: Optional[str], acceptance_criteria: List[str]
    ) -> str:
        """Generate API test script"""
        lines = [
            '"""',
            f"Generated Playwright API Test",
            f"User Story: {user_story}",
            '"""',
            "",
            "from playwright.sync_api import APIRequestContext, expect",
            "",
            "",
            f"def test_{test.get('name', 'test').lower().replace(' ', '_')}(api_request_context: APIRequestContext):",
            f'    """{test.get("description", user_story)}"""',
            "",
        ]
        
        # Add API test steps
        for idx, criteria in enumerate(acceptance_criteria[:5], 1):
            lines.append(f"    # Step {idx}: {criteria}")
            lines.append(f"    # TODO: Implement API call: {criteria}")
            lines.append("")
        
        lines.append("    # Assertions")
        lines.append("    # TODO: Add response assertions")
        lines.append("")
        
        return "\n".join(lines)
