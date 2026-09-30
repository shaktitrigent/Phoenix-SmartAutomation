"""Agent registry — routes requests to the appropriate agent."""

from typing import Any, Dict, List, Optional

from services.agents.base import BaseAgent
from services.agents.failure_analyzer import FailureAnalyzerAgent
from services.agents.locator_expert import LocatorExpertAgent
from services.agents.script_fixer import ScriptFixerAgent
from services.agents.test_generator import TestGeneratorAgent
from services.cache import Cache
from services.knowledge.base import KnowledgeBase
from services.request_config import RequestConfig
from services.request_llm import build_request_llm
import logging

logger = logging.getLogger(__name__)


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
        self._mcp_client = mcp_client
        self._llm_client = llm_client
        self._init_agents(mcp_client, llm_client)

    @property
    def mcp_client(self):
        return self._mcp_client

    @mcp_client.setter
    def mcp_client(self, client):
        self._mcp_client = client
        if "test_generator" in self._agents:
            self._agents["test_generator"].mcp_client = client
        if "locator_expert" in self._agents:
            self._agents["locator_expert"].mcp_client = client

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
        self._agents["script_fixer"] = ScriptFixerAgent(
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
        result = agent.process(input_data, **kwargs)
        return self._with_runtime_metadata(result, agent_name)

    def _with_runtime_metadata(self, result: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        result.setdefault("metadata", {})
        result["metadata"].setdefault("agent", agent_name)
        result["metadata"].setdefault("llm_configured", self._llm_client is not None)
        result["metadata"].setdefault("mcp_configured", self._mcp_client is not None)
        return result

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
        domain_knowledge: str = "",
        supporting_documents: Optional[List[Dict[str, Any]]] = None,
        use_pom: bool = True,
    ) -> Dict[str, Any]:
        return self.invoke_agent(
            "test_generator",
            {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria or [],
                "domain_knowledge": domain_knowledge,
                "supporting_documents": supporting_documents or [],
            },
            test_type=test_type,
            risk_level=risk_level,
            use_pom=use_pom,
        )

    def discover_locators(
        self,
        page_url: str,
        element_name: str,
        dom_snapshot: Optional[str] = None,
        element_context: Optional[Dict[str, Any]] = None,
        require_llm: bool = False,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        if request_config is not None:
            request_llm = build_request_llm(request_config.values)
            agent = LocatorExpertAgent(
                self.knowledge_base,
                Cache(),
                mcp_client=self._mcp_client,
                llm_client=request_llm.client,
            )
            return agent.process({
                "page_url": page_url,
                "element_name": element_name,
                "dom_snapshot": dom_snapshot,
                "element_context": element_context or {},
                "require_llm": require_llm,
            })
        return self.invoke_agent(
            "locator_expert",
            {
                "page_url": page_url,
                "element_name": element_name,
                "dom_snapshot": dom_snapshot,
                "element_context": element_context or {},
                "require_llm": require_llm,
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

    def automate_from_manual(
        self,
        manual_tests: List[Dict[str, Any]],
        application_url: Optional[str] = None,
        domain_knowledge: str = "",
        manifest: str = "",
        use_pom: bool = True,  # Changed default to True for production-ready POM generation
        use_bdd: bool = False,
        keywords: str = "",
        project_context: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        locator_bundles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        llm_client = self._llm_client
        llm_reason = None
        if request_config is not None:
            request_llm = build_request_llm(request_config.values)
            llm_client = request_llm.client
            llm_reason = request_llm.reason
        existing_agent = self._agents.get("test_generator")
        fully_initialized = hasattr(self, "knowledge_base") and hasattr(self, "cache")
        if fully_initialized:
            # Agents are request-local: a client created for one project is
            # never stored on the registry or reused by another request.
            agent = TestGeneratorAgent(
                self.knowledge_base, self.cache,
                mcp_client=self._mcp_client, llm_client=llm_client,
            )
            LocatorExpertAgent(
                self.knowledge_base, self.cache,
                mcp_client=self._mcp_client, llm_client=llm_client,
            )
        else:
            # Preserve compatibility with lightweight/embedded registries and
            # older integrations that provide a generator without initializing
            # the registry service container. Production registries always use
            # the request-local branch above.
            if existing_agent is None:
                raise RuntimeError("test_generator_agent_unavailable")
            agent = existing_agent
        bundles = locator_bundles or []
        logger.info(
            "Automation request: project_context=%s config_source=%s bundles=%d llm_available=%s",
            project_context is not None,
            ",".join(request_config.diagnostics.sources) if request_config else "legacy",
            len(bundles), bool(llm_client),
        )
        result = agent.automate_from_manual_tests(
            manual_tests=manual_tests,
            application_url=application_url,
            domain_knowledge=domain_knowledge,
            manifest=manifest,
            use_pom=use_pom,
            use_bdd=use_bdd,
            keywords=keywords,
            locator_bundles=bundles,
        )
        result.setdefault("metadata", {})
        result["metadata"].update({
            "agent": "test_generator",
            "llm_configured": bool(llm_client),
            "locator_bundles_loaded": len(bundles),
            "locator_sources": sorted({
                (b.get("metadata") or {}).get("locator_source", "unresolved")
                for b in bundles
            }),
            "locator_expert_scope": "unresolved_elements_only",
        })
        if llm_reason:
            result["metadata"]["llm_unavailable_reason"] = llm_reason
        return result

    def fix_script(
        self,
        script_code: str,
        error_message: str,
        error_type: str = "unknown",
        test_name: str = "unknown_test",
        application_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.invoke_agent(
            "script_fixer",
            {
                "script_code": script_code,
                "error_message": error_message,
                "error_type": error_type,
                "test_name": test_name,
                "application_url": application_url,
            },
        )
