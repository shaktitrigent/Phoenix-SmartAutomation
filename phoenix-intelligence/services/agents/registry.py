"""Agent registry for routing requests to appropriate agents"""

from typing import Dict, Any, Optional
from services.agents.base import BaseAgent
from services.agents.test_generator import TestGeneratorAgent
from services.agents.locator_expert import LocatorExpertAgent
from services.agents.failure_analyzer import FailureAnalyzerAgent
from services.knowledge.base import KnowledgeBase
from services.cache import Cache


class AgentRegistry:
    """Registry for managing and routing to agents"""

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        cache: Cache,
        mcp_client=None,
        llm_client=None,
    ):
        """
        Initialize agent registry.

        Args:
            knowledge_base: Knowledge base instance
            cache: Cache instance
            mcp_client: Optional MCP client for page inspection
            llm_client: Optional LLM client for AI-powered generation
        """
        self.knowledge_base = knowledge_base
        self.cache = cache
        self._agents: Dict[str, BaseAgent] = {}
        self._initialize_agents(mcp_client, llm_client)

    def _initialize_agents(self, mcp_client=None, llm_client=None):
        """Initialize all available agents"""
        self._agents["test_generator"] = TestGeneratorAgent(
            self.knowledge_base, self.cache, mcp_client=mcp_client, llm_client=llm_client
        )
        self._agents["locator_expert"] = LocatorExpertAgent(
            self.knowledge_base, self.cache, mcp_client=mcp_client, llm_client=llm_client
        )
        self._agents["failure_analyzer"] = FailureAnalyzerAgent(
            self.knowledge_base, self.cache, mcp_client=mcp_client, llm_client=llm_client
        )

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(agent_name)

    def list_agents(self) -> list:
        """List all available agent names"""
        return list(self._agents.keys())

    def invoke_agent(
        self, agent_name: str, input_data: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Invoke an agent with input data."""
        agent = self.get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Unknown agent: {agent_name}")

        return agent.process(input_data, **kwargs)

    def generate_tests(
        self, user_story: str, application_url: Optional[str] = None, acceptance_criteria: list = None, **kwargs
    ) -> Dict[str, Any]:
        """Generate tests using test generator agent."""
        return self.invoke_agent(
            "test_generator",
            {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria or [],
            },
            **kwargs,
        )

    def discover_locators(
        self, page_url: str, element_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Discover locators using locator expert agent."""
        return self.invoke_agent(
            "locator_expert",
            {
                "page_url": page_url,
                "element_name": element_name,
            },
            **kwargs,
        )

    def analyze_failure(
        self, test_case_id: str, error_message: str, **kwargs
    ) -> Dict[str, Any]:
        """Analyze test failure using failure analyzer agent."""
        return self.invoke_agent(
            "failure_analyzer",
            {
                "test_case_id": test_case_id,
                "error_message": error_message,
            },
            **kwargs,
        )
