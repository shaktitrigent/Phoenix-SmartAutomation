"""Base agent class for skill-based agents"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from services.knowledge.base import KnowledgeBase
from services.cache import Cache


class BaseAgent(ABC):
    """Base class for all Phoenix agents"""

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        cache: Cache,
        mcp_client=None,
        llm_client=None,
    ):
        """
        Initialize base agent.

        Args:
            knowledge_base: Knowledge base instance
            cache: Cache instance
            mcp_client: Optional MCP client for page inspection
            llm_client: Optional LLM client for AI-powered generation
        """
        self.knowledge_base = knowledge_base
        self.cache = cache
        self.agent_type = self.__class__.__name__.lower().replace("agent", "")
        self.mcp_client = mcp_client
        self.llm_client = llm_client

    @abstractmethod
    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process input and return result.

        Args:
            input_data: Input data dictionary
            **kwargs: Additional parameters

        Returns:
            Result dictionary
        """
        pass

    def get_knowledge_context(self, query: Optional[str] = None) -> str:
        """
        Get relevant knowledge context for this agent.

        Args:
            query: Optional query to filter knowledge

        Returns:
            Formatted knowledge context string
        """
        return self.knowledge_base.get_context_for_agent(self.agent_type, query)

    def _cache_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key"""
        import hashlib
        import json

        key_data = {k: v for k, v in kwargs.items()}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"
