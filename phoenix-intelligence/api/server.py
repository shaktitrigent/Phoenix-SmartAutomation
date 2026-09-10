"""Phoenix intelligence API server."""

import logging
from datetime import datetime, timezone
from pathlib import Path
import os
import sys

# Ensure phoenix-intelligence root is on sys.path for local execution
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Configure logger with enhanced error handling
logger = logging.getLogger(__name__)

# CRITICAL FIX: Add detailed error logging for startup issues
def _enhance_error_logging():
    """Enhance error logging with detailed context."""
    if not logger.handlers:
        # Add console handler if none exists
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

_enhance_error_logging()

# Load environment variables from project directory if available
def _load_project_env():
    """Load .env files from project directory for API keys."""
    try:
        import dotenv
        
        # Try to find the project directory (look for .phoenixrc)
        project_dir = None
        current = Path.cwd()
        
        # Check current directory first
        if (current / ".phoenixrc").exists():
            project_dir = current
        else:
            # Check parent directories
            for parent in current.parents:
                if (parent / ".phoenixrc").exists():
                    project_dir = parent
                    break
        
        if project_dir:
            env_files = [
                project_dir / ".env.local",
                project_dir / ".env",
            ]
            for env_file in env_files:
                if env_file.exists():
                    logger.info(f"Loading environment variables from {env_file}")
                    dotenv.load_dotenv(env_file, override=True)
                    
                    # Log if ANTHROPIC_API_KEY was loaded
                    if "ANTHROPIC_API_KEY" in os.environ:
                        logger.info("✓ ANTHROPIC_API_KEY loaded from .env file")
                    else:
                        logger.warning("⚠ ANTHROPIC_API_KEY not found in .env file")
        else:
            logger.warning("No .phoenixrc found in current or parent directories")
            logger.warning("Environment variables will be loaded from system environment only")
    except ImportError:
        logger.warning("python-dotenv not installed, .env files will not be loaded")
    except Exception as e:
        logger.warning(f"Failed to load .env files: {e}")

_load_project_env()

from fastapi import FastAPI
from services.cache import Cache
from services.config import IntelligenceSettings, LLMSettings, MCPSettings
from services.knowledge.base import KnowledgeBase
from services.llm.client import LLMClient
from services.mcp.client import MCPClient
from services.agents.registry import AgentRegistry
from api.models import (
    AutomateRequest,
    AutomateResponse,
    TestGenerationRequest,
    TestGenerationResponse,
    LocatorDiscoveryRequest,
    LocatorDiscoveryResponse,
    FailureAnalysisRequest,
    FailureAnalysisResponse,
    ScriptFixRequest,
    ScriptFixResponse,
)

app = FastAPI(title="Phoenix Intelligence API", version="2.0.0")

# ---------------------------------------------------------------------------
# Shared services
# ---------------------------------------------------------------------------
_cache = Cache()
_knowledge_base = KnowledgeBase()


def _provider_key_name(provider: str) -> str:
    """Only Anthropic is supported."""
    return "ANTHROPIC_API_KEY"


_llm_settings = LLMSettings()
_llm_client = None

# Enhanced API key validation for Anthropic only
def _check_llm_availability() -> tuple[bool, str, list[str]]:
    """Check Anthropic API key availability."""
    warnings = []

    # Reinitialize settings to pick up any environment changes
    _llm_settings.__post_init__()

    # Check if Anthropic API key is configured
    if _llm_settings.is_configured():
        logger.info("Anthropic API key is configured and valid")
        return True, "anthropic", []
    else:
        warnings.append("ANTHROPIC_API_KEY is not configured or invalid")
        logger.warning("ANTHROPIC_API_KEY is not configured or invalid")
        return False, "None", warnings

_llm_available, _available_providers_list, _llm_warnings = _check_llm_availability()

if _llm_available:
    try:
        _llm_client = LLMClient(_llm_settings)
        logger.info(
            "LLM client initialised (provider=%s model=%s available=%s)",
            _llm_settings.provider,
            _llm_settings.model,
            _available_providers_list,
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        _llm_client = None
        _llm_available = False
        _llm_warnings.append(f"LLM client initialization failed: {str(e)}")

if not _llm_available:
    _banner = (
        "\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        "║  ⚠  ANTHROPIC API KEY NOT CONFIGURED                    ║\n"
        "╠══════════════════════════════════════════════════════════╣\n"
        "║  Provider : Anthropic (Claude)                          ║\n"
        "║  Required : ANTHROPIC_API_KEY                           ║\n"
        "╠══════════════════════════════════════════════════════════╣\n"
        "║  Without an API key:                                     ║\n"
        "║  • Automation scripts will be heuristic stubs only       ║\n"
        "║  • All generated output is fallback / placeholder        ║\n"
        "║  • DOM-based healing will be limited                    ║\n"
        "╠══════════════════════════════════════════════════════════╣\n"
        "║  Fix:  export ANTHROPIC_API_KEY=sk-ant-...               ║\n"
        "║  Then restart the phoenix-intelligence server.           ║\n"
        "╚══════════════════════════════════════════════════════════╝\n"
    )
    logger.warning(_banner)

    # Log individual warnings
    for warning in _llm_warnings:
        logger.warning(f"LLM Configuration Warning: {warning}")

_mcp_settings = MCPSettings()
_mcp_client = None

# Initialize intelligent runtime components for DOM reuse
_artifacts_manager = None
_dom_snapshot_manager = None

try:
    from phoenix.execution.artifacts import get_artifacts_manager
    from phoenix.execution.dom_snapshot_manager import DOMSnapshotManager
    
    # Initialize artifacts manager
    _artifacts_manager = get_artifacts_manager(base_dir="PhoenixRuntime/artifacts")
    
    # Initialize DOM snapshot manager
    _dom_snapshot_manager = DOMSnapshotManager(base_dir="PhoenixRuntime")
    
    logger.info("Intelligent runtime components initialized for DOM reuse")
except ImportError as e:
    logger.warning(f"Could not initialize intelligent runtime components: {e}")

if _mcp_settings.enabled:
    _mcp_client = MCPClient(
        _mcp_settings, 
        artifacts_manager=_artifacts_manager,
        dom_snapshot_manager=_dom_snapshot_manager
    )
    logger.info("MCP client initialised (command=%s %s)", _mcp_settings.command, _mcp_settings.args)
else:
    logger.info("MCP is disabled via PHOENIX_MCP_ENABLED=false")

_agent_registry = AgentRegistry(
    _knowledge_base, _cache, mcp_client=_mcp_client, llm_client=_llm_client
)


def _decorate_metadata(result: dict) -> dict:
    result.setdefault("metadata", {})
    result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["metadata"]["version"] = "2.0.0"
    result["metadata"]["llm_configured"] = _llm_settings.is_configured()
    result["metadata"]["prompt_hot_reload"] = True

    warnings = list(result["metadata"].get("warnings", []))
    for test in result.get("automation_tests", []):
        warnings.extend(test.get("warnings", []))
    if warnings:
        deduped = []
        for warning in warnings:
            if warning not in deduped:
                deduped.append(warning)
        result["metadata"]["warnings"] = deduped
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health_check():
    """Health check endpoint — reports LLM and MCP availability."""
    llm_ok = _llm_settings.is_configured()
    _provider_key = _provider_key_name(_llm_settings.provider)
    return {
        "status": "ok" if llm_ok else "degraded",
        "llm": {
            "configured": llm_ok,
            "provider": _llm_settings.provider,
            "model": _llm_settings.model if llm_ok else None,
            "warning": None
            if llm_ok
            else (
                f"No API key for provider '{_llm_settings.provider}'. "
                f"Set {_provider_key or 'the provider-specific env var'} and restart."
            ),
        },
        "mcp": {
            "enabled": _mcp_settings.enabled,
            "configured": _mcp_client is not None,
        },
    }


@app.post("/api/v1/tests/generate", response_model=TestGenerationResponse)
def generate_tests(payload: TestGenerationRequest):
    """Generate manual and automation tests from a user story."""
    options = payload.options
    test_type = options.test_type if options else "both"
    risk_level = options.risk_level if options else None

    # Extract MCP configuration from payload if provided
    mcp_config = getattr(payload, "mcp_config", None)
    if mcp_config and mcp_config.get("enabled"):
        # Temporarily update MCP settings for this request
        from services.config import MCPSettings
        original_enabled = _mcp_settings.enabled
        original_command = _mcp_settings.command
        original_args = _mcp_settings.args
        original_timeout = _mcp_settings.timeout

        _mcp_settings.enabled = mcp_config.get("enabled", True)
        _mcp_settings.command = mcp_config.get("command", "npx")
        _mcp_settings.args = mcp_config.get("args", "@playwright/mcp@latest")
        _mcp_settings.timeout = mcp_config.get("timeout", 60)

        # Reinitialize MCP client with new settings
        if _mcp_settings.enabled:
            from services.mcp.client import MCPClient
            _mcp_client = MCPClient(settings=_mcp_settings)

    supporting_documents = [
        doc.model_dump() for doc in (payload.supporting_documents or [])
    ]
    result = _agent_registry.generate_tests(
        user_story=payload.user_story,
        application_url=payload.application_url,
        acceptance_criteria=payload.acceptance_criteria,
        test_type=test_type,
        risk_level=risk_level,
        domain_knowledge=payload.domain_knowledge or "",
        supporting_documents=supporting_documents,
    )

    # Restore original MCP settings
    if mcp_config:
        _mcp_settings.enabled = original_enabled
        _mcp_settings.command = original_command
        _mcp_settings.args = original_args
        _mcp_settings.timeout = original_timeout

        # Reinitialize MCP client with original settings
        if _mcp_settings.enabled:
            from services.mcp.client import MCPClient
            _mcp_client = MCPClient(settings=_mcp_settings)

    return _decorate_metadata(result)


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
    return _decorate_metadata(result)


@app.post("/api/v1/tests/automate", response_model=AutomateResponse)
def automate_from_manual(payload: AutomateRequest):
    """Generate automation scripts from pre-written manual tests (1 script per test)."""
    
    # Extract MCP configuration from payload if provided
    mcp_config = getattr(payload, "mcp_config", None)
    if mcp_config and mcp_config.get("enabled"):
        # Temporarily update MCP settings for this request
        from services.config import MCPSettings
        original_enabled = _mcp_settings.enabled
        original_command = _mcp_settings.command
        original_args = _mcp_settings.args
        original_timeout = _mcp_settings.timeout
        
        _mcp_settings.enabled = mcp_config.get("enabled", True)
        _mcp_settings.command = mcp_config.get("command", "npx")
        _mcp_settings.args = mcp_config.get("args", "@playwright/mcp@latest")
        _mcp_settings.timeout = mcp_config.get("timeout", 60)
        
        # Reinitialize MCP client with new settings
        if _mcp_settings.enabled:
            from services.mcp.client import MCPClient
            _mcp_client = MCPClient(
                settings=_mcp_settings,
                artifacts_manager=_artifacts_manager,
                dom_snapshot_manager=_dom_snapshot_manager
            )
            logger.info(f"MCP client reconfigured from request: command={_mcp_settings.command} args={_mcp_settings.args}")
        
        # Update agent registry with new MCP client
        _agent_registry._mcp_client = _mcp_client
    
    result = _agent_registry.automate_from_manual(
        manual_tests=payload.manual_tests,
        application_url=payload.application_url,
        domain_knowledge=payload.domain_knowledge or "",
        manifest=payload.manifest or "",
        use_pom=payload.use_pom,
        use_bdd=payload.use_bdd,
        keywords=payload.keywords or "",
    )
    
    # Restore original MCP settings
    if mcp_config:
        _mcp_settings.enabled = original_enabled
        _mcp_settings.command = original_command
        _mcp_settings.args = original_args
        _mcp_settings.timeout = original_timeout
    
    return _decorate_metadata(result)


@app.post("/api/v1/tests/fix", response_model=ScriptFixResponse)
def fix_script(payload: ScriptFixRequest):
    """Fix a failing automation script given its error output."""
    result = _agent_registry.fix_script(
        script_code=payload.script_code,
        error_message=payload.error_message,
        error_type=payload.error_type,
        test_name=payload.test_name,
        application_url=payload.application_url,
    )
    return _decorate_metadata(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from services.logger import configure_logging

    settings = IntelligenceSettings()
    json_logs = os.environ.get("PHOENIX_LOG_JSON", "false").lower() == "true"
    configure_logging(level=settings.log_level.upper(), json_output=json_logs)

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
