"""Phoenix intelligence API server."""

import logging
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure phoenix-intelligence root is on sys.path for local execution
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from services.cache import Cache
from services.config import LLMSettings, MCPSettings
from services.knowledge.base import KnowledgeBase
from services.llm.client import LLMClient
from services.mcp.client import MCPClient
from services.agents.registry import AgentRegistry
from api.models import (
    TestGenerationRequest,
    TestGenerationResponse,
    LocatorDiscoveryRequest,
    LocatorDiscoveryResponse,
    FailureAnalysisRequest,
    FailureAnalysisResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Phoenix Intelligence API", version="2.0.0")

# ---------------------------------------------------------------------------
# Shared services
# ---------------------------------------------------------------------------
_cache = Cache()
_knowledge_base = KnowledgeBase()

_llm_settings = LLMSettings()
_llm_client = None
if _llm_settings.api_key:
    _llm_client = LLMClient(_llm_settings)
    logger.info("LLM client initialised (model=%s)", _llm_settings.model)
else:
    logger.warning(
        "ANTHROPIC_API_KEY is not set — automation test generation will fail. "
        "Set the environment variable and restart the server."
    )

_mcp_settings = MCPSettings()
_mcp_client = None
if _mcp_settings.enabled:
    _mcp_client = MCPClient(_mcp_settings)
    logger.info("MCP client initialised (command=%s %s)", _mcp_settings.command, _mcp_settings.args)
else:
    logger.info("MCP is disabled via PHOENIX_MCP_ENABLED=false")

_agent_registry = AgentRegistry(
    _knowledge_base, _cache, mcp_client=_mcp_client, llm_client=_llm_client
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/tests/generate", response_model=TestGenerationResponse)
def generate_tests(payload: TestGenerationRequest):
    """Generate manual and automation tests from a user story."""
    options = payload.options
    test_type = options.test_type if options else "both"
    risk_level = options.risk_level if options else None

    result = _agent_registry.generate_tests(
        user_story=payload.user_story,
        application_url=payload.application_url,
        acceptance_criteria=payload.acceptance_criteria,
        test_type=test_type,
        risk_level=risk_level,
    )

    result.setdefault("metadata", {})
    result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["metadata"]["version"] = "2.0.0"
    return result


@app.post("/api/v1/locators/discover", response_model=LocatorDiscoveryResponse)
def discover_locators(payload: LocatorDiscoveryRequest):
    """Discover locators for the requested elements on a page."""
    results = []
    for element in payload.elements:
        locators = _agent_registry.discover_locators(
            page_url=payload.page_url,
            element_name=element,
            dom_snapshot=payload.dom_snapshot,
        )
        results.extend(locators.get("locators", []))

    return {
        "locators": results,
        "recommended_locator": results[0] if results else None,
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "version": "2.0.0"},
    }


@app.post("/api/v1/failures/analyze", response_model=FailureAnalysisResponse)
def analyze_failure(payload: FailureAnalysisRequest):
    """Analyze a failure and suggest fixes."""
    result = _agent_registry.analyze_failure(
        test_case_id=getattr(payload, "test_case_id", "unknown") or "unknown",
        error_message=payload.error_message,
        traceback=payload.traceback,
    )
    result.setdefault("metadata", {})
    result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["metadata"]["version"] = "2.0.0"
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import uvicorn
    from services.config import IntelligenceSettings
    from services.logger import configure_logging

    settings = IntelligenceSettings()
    json_logs = os.environ.get("PHOENIX_LOG_JSON", "false").lower() == "true"
    configure_logging(level=settings.log_level.upper(), json_output=json_logs)

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
