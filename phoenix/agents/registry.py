"""Agent registry for routing requests to appropriate agents"""

from typing import Dict, Any, Optional
from phoenix.agents.base import BaseAgent
from phoenix.agents.test_generator import TestGeneratorAgent
from phoenix.agents.locator_expert import LocatorExpertAgent
from phoenix.agents.failure_analyzer import FailureAnalyzerAgent
from phoenix.knowledge.base import KnowledgeBase
from phoenix.storage.cache import Cache


class AgentRegistry:
    """Registry for managing and routing to agents"""

    def __init__(self, knowledge_base: KnowledgeBase, cache: Cache):
        """
        Initialize agent registry.
        
        Args:
            knowledge_base: Knowledge base instance
            cache: Cache instance
        """
        self.knowledge_base = knowledge_base
        self.cache = cache
        self._agents: Dict[str, BaseAgent] = {}
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize all available agents"""
        self._agents["test_generator"] = TestGeneratorAgent(self.knowledge_base, self.cache)
        self._agents["locator_expert"] = LocatorExpertAgent(self.knowledge_base, self.cache)
        self._agents["failure_analyzer"] = FailureAnalyzerAgent(self.knowledge_base, self.cache)

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get an agent by name.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(agent_name)

    def list_agents(self) -> list:
        """List all available agent names"""
        return list(self._agents.keys())

    def invoke_agent(
        self, agent_name: str, input_data: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke an agent with input data.
        
        Args:
            agent_name: Name of the agent
            input_data: Input data dictionary
            **kwargs: Additional parameters
            
        Returns:
            Agent result dictionary
        """
        agent = self.get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        return agent.process(input_data, **kwargs)

    def generate_tests(
        self, user_story: str, application_url: Optional[str] = None, acceptance_criteria: list = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Generate tests using test generator agent.
        
        Args:
            user_story: User story text
            application_url: Application URL to test
            acceptance_criteria: List of acceptance criteria
            **kwargs: Additional parameters
            
        Returns:
            Test generation result
        """
        return self.invoke_agent(
            "test_generator",
            {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria or [],
            },
            **kwargs
        )

    def discover_locators(
        self, page_url: str, element_name: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Discover locators using locator expert agent.
        
        Args:
            page_url: URL of the page
            element_name: Name/description of element
            **kwargs: Additional parameters
            
        Returns:
            Locator discovery result
        """
        return self.invoke_agent(
            "locator_expert",
            {
                "page_url": page_url,
                "element_name": element_name,
            },
            **kwargs
        )

    def analyze_failure(
        self, test_case_id: str, error_message: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Analyze test failure using failure analyzer agent.
        
        Args:
            test_case_id: Test case ID
            error_message: Error message
            **kwargs: Additional parameters
            
        Returns:
            Failure analysis result
        """
        return self.invoke_agent(
            "failure_analyzer",
            {
                "test_case_id": test_case_id,
                "error_message": error_message,
            },
            **kwargs
        )
