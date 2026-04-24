"""Agent registry — routes requests to the appropriate agent."""

from typing import Any, Dict, List, Optional

from services.agents.base import BaseAgent
from services.agents.failure_analyzer import FailureAnalyzerAgent
from services.agents.locator_expert import LocatorExpertAgent
from services.agents.test_generator import TestGeneratorAgent
from services.cache import Cache
from services.knowledge.base import KnowledgeBase


class AgentRegistry:
    """Manages and dispatches to Phoenix agents."""

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        cache: Cache,
        mcp_client=None,
        llm_client=None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.cache = cache
        self._agents: Dict[str, BaseAgent] = {}
        self._init_agents(mcp_client, llm_client)

    def _init_agents(self, mcp_client=None, llm_client=None) -> None:
        kwargs = dict(mcp_client=mcp_client, llm_client=llm_client)
        self._agents["test_generator"] = TestGeneratorAgent(
            self.knowledge_base, self.cache, **kwargs
        )
        self._agents["locator_expert"] = LocatorExpertAgent(
            self.knowledge_base, self.cache, **kwargs
        )
        self._agents["failure_analyzer"] = FailureAnalyzerAgent(
            self.knowledge_base, self.cache, **kwargs
        )

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        return list(self._agents.keys())

    def invoke_agent(self, agent_name: str, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        agent = self.get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Unknown agent: '{agent_name}'. Available: {self.list_agents()}")
        return agent.process(input_data, **kwargs)

    # ------------------------------------------------------------------
    # Convenience methods used by the API server
    # ------------------------------------------------------------------

    def generate_tests(
        self,
        user_story: str,
        application_url: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        test_type: str = "both",
        risk_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.invoke_agent(
            "test_generator",
            {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria or [],
            },
            test_type=test_type,
            risk_level=risk_level,
        )

    def discover_locators(
        self,
        page_url: str,
        element_name: str,
        dom_snapshot: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.invoke_agent(
            "locator_expert",
            {
                "page_url": page_url,
                "element_name": element_name,
                "dom_snapshot": dom_snapshot,
            },
        )

    def analyze_failure(
        self,
        test_case_id: str,
        error_message: str,
        traceback: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.invoke_agent(
            "failure_analyzer",
            {
                "test_case_id": test_case_id,
                "error_message": error_message,
                "traceback": traceback or "",
            },
        )
