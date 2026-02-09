"""Manual test case generator"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from phoenix.storage.models import TestType
from phoenix.agents.registry import AgentRegistry


class ManualTestGenerator:
    """Generator for manual test cases"""

    def __init__(self, agent_registry: AgentRegistry, output_dir: str = "./manual_tests"):
        """
        Initialize manual test generator.
        
        Args:
            agent_registry: Agent registry instance
            output_dir: Directory to save manual test files
        """
        self.agent_registry = agent_registry
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        user_story: str,
        application_url: Optional[str] = None,
        acceptance_criteria: List[str] = None,
        risk_level: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate manual test cases.
        
        Args:
            user_story: User story text
            acceptance_criteria: List of acceptance criteria
            risk_level: Risk level (smoke, regression, edge)
            **kwargs: Additional parameters
            
        Returns:
            List of manual test case dictionaries
        """
        # Use test generator agent
        # Remove test_type from kwargs to avoid conflict
        agent_kwargs = {k: v for k, v in kwargs.items() if k != "test_type"}
        result = self.agent_registry.generate_tests(
            user_story=user_story,
            application_url=application_url,
            acceptance_criteria=acceptance_criteria or [],
            test_type="manual",
            risk_level=risk_level,
            **agent_kwargs
        )
        
        manual_tests = result.get("manual_tests", [])
        
        # Format as test case dictionaries and save as markdown files
        formatted_tests = []
        for idx, test in enumerate(manual_tests, 1):
            formatted_test = {
                "name": test.get("name", f"Manual Test {idx}"),
                "description": test.get("description", user_story),
                "steps": test.get("steps", []),
                "expected_result": test.get("expected_result", ""),
                "risk_level": test.get("risk_level", risk_level or "regression"),
                "tags": test.get("tags", ["manual", "generated"]),
                "test_type": TestType.MANUAL.value,
            }
            formatted_tests.append(formatted_test)
            
            # Save as markdown file
            self._save_manual_test(formatted_test, idx, application_url)
        
        return formatted_tests
    
    def _save_manual_test(self, test_case: Dict[str, Any], index: int, application_url: Optional[str] = None):
        """Save manual test case as markdown file"""
        safe_name = "".join(c for c in test_case["name"] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_').lower()
        filename = f"manual_test_{index:03d}_{safe_name}.md"
        file_path = self.output_dir / filename
        
        content = self.format_as_plain_english(test_case)
        if application_url:
            content = f"Application URL: {application_url}\n\n{content}"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        test_case["file_path"] = str(file_path)

    def format_as_gherkin(self, test_case: Dict[str, Any]) -> str:
        """
        Format test case as Gherkin.
        
        Args:
            test_case: Test case dictionary
            
        Returns:
            Gherkin formatted string
        """
        lines = [f"Feature: {test_case['name']}"]
        lines.append(f"  {test_case['description']}")
        lines.append("")
        lines.append(f"  Scenario: {test_case['name']}")
        
        for step in test_case.get("steps", []):
            # Try to identify step type
            step_lower = step.lower()
            if "given" in step_lower or "navigate" in step_lower:
                lines.append(f"    Given {step}")
            elif "when" in step_lower or "click" in step_lower or "enter" in step_lower:
                lines.append(f"    When {step}")
            elif "then" in step_lower or "verify" in step_lower or "assert" in step_lower:
                lines.append(f"    Then {step}")
            else:
                lines.append(f"    Given {step}")
        
        if test_case.get("expected_result"):
            lines.append(f"    Then {test_case['expected_result']}")
        
        return "\n".join(lines)

    def format_as_plain_english(self, test_case: Dict[str, Any]) -> str:
        """
        Format test case as plain English.
        
        Args:
            test_case: Test case dictionary
            
        Returns:
            Plain English formatted string
        """
        lines = [f"Test Case: {test_case['name']}"]
        lines.append("")
        lines.append(f"Description: {test_case['description']}")
        lines.append("")
        lines.append("Steps:")
        
        for idx, step in enumerate(test_case.get("steps", []), 1):
            lines.append(f"  {idx}. {step}")
        
        if test_case.get("expected_result"):
            lines.append("")
            lines.append(f"Expected Result: {test_case['expected_result']}")
        
        if test_case.get("risk_level"):
            lines.append("")
            lines.append(f"Risk Level: {test_case['risk_level'].upper()}")
        
        return "\n".join(lines)
