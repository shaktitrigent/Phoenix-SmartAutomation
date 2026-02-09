"""Test generation agent"""

from typing import Dict, Any, List, Optional
from phoenix.agents.base import BaseAgent


class TestGeneratorAgent(BaseAgent):
    """Agent specialized in generating test cases from user stories"""

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Generate test cases from user story and acceptance criteria.
        
        Args:
            input_data: Dictionary containing:
                - user_story: User story text
                - application_url: Application URL (optional)
                - acceptance_criteria: List of acceptance criteria
                - project: Project name (optional)
            **kwargs: Additional parameters:
                - test_type: 'manual', 'automation', or 'both' (default: 'both')
                - risk_level: 'smoke', 'regression', 'edge' (optional)
                
        Returns:
            Dictionary containing:
                - manual_tests: List of manual test cases
                - automation_tests: List of automation test cases
                - metadata: Additional metadata
        """
        user_story = input_data.get("user_story", "")
        application_url = input_data.get("application_url")
        acceptance_criteria = input_data.get("acceptance_criteria", [])
        test_type = kwargs.get("test_type", "both")
        risk_level = kwargs.get("risk_level")
        
        # Get knowledge context
        knowledge_context = self.get_knowledge_context(query=user_story)
        
        # Check cache first
        cache_key = self._cache_key("test_generation", 
                                    user_story=user_story,
                                    application_url=application_url or "",
                                    acceptance_criteria=acceptance_criteria)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        result = {
            "manual_tests": [],
            "automation_tests": [],
            "metadata": {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria,
                "knowledge_context_used": bool(knowledge_context),
                "test_type": test_type,
                "risk_level": risk_level,
            }
        }
        
        # Generate manual tests if requested
        if test_type in ["manual", "both"]:
            result["manual_tests"] = self._generate_manual_tests(
                user_story, application_url, acceptance_criteria, knowledge_context, risk_level
            )
        
        # Generate automation tests if requested
        if test_type in ["automation", "both"]:
            result["automation_tests"] = self._generate_automation_tests(
                user_story, application_url, acceptance_criteria, knowledge_context, risk_level
            )
        
        # Cache result
        self.cache.set(cache_key, result, ttl=3600)
        
        return result

    def _generate_manual_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        knowledge_context: str,
        risk_level: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate manual test cases.
        """
        # Generate structured manual test cases from acceptance criteria
        steps = []
        if application_url:
            steps.append(f"Navigate to {application_url}")
        
        for idx, criteria in enumerate(acceptance_criteria, 1):
            steps.append(f"Step {idx}: {criteria}")
        
        return [
            {
                "name": f"Manual Test: {user_story[:50]}...",
                "description": user_story,
                "steps": steps,
                "expected_result": "All acceptance criteria are met and the user story is fulfilled",
                "risk_level": risk_level or "regression",
                "tags": ["manual", "generated"],
            }
        ]

    def _generate_automation_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        knowledge_context: str,
        risk_level: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate automation test cases.
        """
        return [
            {
                "name": f"Automation Test: {user_story[:50]}...",
                "description": user_story,
                "script_template": "playwright",
                "test_steps": acceptance_criteria,
                "application_url": application_url,
                "risk_level": risk_level or "regression",
                "tags": ["automation", "generated"],
            }
        ]
