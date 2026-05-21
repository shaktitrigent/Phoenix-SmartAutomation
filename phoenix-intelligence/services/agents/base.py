"""Base agent class for skill-based agents"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, NotRequired, Optional, TypedDict, TypeVar

from services.knowledge.base import KnowledgeBase
from services.cache import Cache

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Shared response envelope used by every agent
# ---------------------------------------------------------------------------

class AgentMetadata(TypedDict, total=False):
    agent: str
    llm_configured: bool
    mcp_configured: bool
    llm_used: bool
    test_case_id: str
    warnings: List[str]


class AgentResponse(TypedDict):
    """Minimal response shape every agent must conform to."""
    metadata: AgentMetadata


# ---------------------------------------------------------------------------
# Per-agent input TypedDicts (kwargs replace Dict[str, Any])
# ---------------------------------------------------------------------------

class FailureAnalysisInput(TypedDict):
    test_case_id: NotRequired[str]
    error_message: str
    traceback: NotRequired[str]


class LocatorDiscoveryInput(TypedDict):
    page_url: str
    element_name: str
    dom_snapshot: NotRequired[str]


class TestGenerationInput(TypedDict):
    user_story: str
    application_url: NotRequired[str]
    acceptance_criteria: NotRequired[List[str]]


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

    def _llm_with_fallback(
        self,
        llm_fn: Callable[[], T],
        fallback_fn: Callable[[], T],
        operation: str,
    ) -> T:
        """Call llm_fn if LLM is configured; fall back to fallback_fn on failure or absence.

        Logs a warning on LLM failure so the reason is always traceable.
        """
        if self.llm_client:
            try:
                return llm_fn()
            except Exception as exc:
                logger.warning(
                    "%s: LLM call failed (%s), using heuristic fallback",
                    operation,
                    exc,
                    exc_info=True,
                )
        else:
            logger.debug("%s: no LLM configured, using heuristic fallback", operation)
        return fallback_fn()
