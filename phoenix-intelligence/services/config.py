"""Configuration for phoenix-intelligence services."""

import os
from dataclasses import dataclass
from pathlib import Path


def _provider_key_name(provider: str) -> str:
    provider = provider.lower()
    if provider == "openai":
        return "OPENAI_API_KEY"
    if provider == "gemini":
        return "GOOGLE_API_KEY"
    if provider == "ollama":
        return ""
    return "ANTHROPIC_API_KEY"


def _default_model(provider: str) -> str:
    provider = provider.lower()
    if provider == "openai":
        return "gpt-4o"
    if provider == "gemini":
        return "gemini-1.5-pro"
    if provider == "ollama":
        return "llama3"
    return "claude-sonnet-4-20250514"


@dataclass
class LLMSettings:
    """LLM provider settings - supports anthropic, openai, gemini, ollama."""

    provider: str = os.environ.get("PHOENIX_LLM_PROVIDER", "anthropic")
    api_key: str = os.environ.get(
        _provider_key_name(os.environ.get("PHOENIX_LLM_PROVIDER", "anthropic")),
        "",
    )
    model: str = os.environ.get(
        "PHOENIX_LLM_MODEL",
        _default_model(os.environ.get("PHOENIX_LLM_PROVIDER", "anthropic")),
    )
    max_tokens: int = int(os.environ.get("PHOENIX_LLM_MAX_TOKENS", "4096"))
    temperature: float = float(os.environ.get("PHOENIX_LLM_TEMPERATURE", "0.2"))
    # Prompt versioning
    prompts_dir: str = os.environ.get(
        "PHOENIX_PROMPTS_DIR",
        str(Path(__file__).resolve().parents[1] / "prompts"),
    )


@dataclass
class MCPSettings:
    """Playwright MCP settings for page inspection via stdio."""

    enabled: bool = os.environ.get("PHOENIX_MCP_ENABLED", "true").lower() == "true"
    command: str = os.environ.get("PHOENIX_MCP_COMMAND", "npx")
    args: str = os.environ.get("PHOENIX_MCP_ARGS", "@playwright/mcp@latest --headless")
    timeout: int = int(os.environ.get("PHOENIX_MCP_TIMEOUT", "30"))


@dataclass
class IntelligenceSettings:
    """Intelligence API settings."""

    host: str = os.environ.get("PHOENIX_INTELLIGENCE_HOST", "0.0.0.0")
    port: int = int(os.environ.get("PHOENIX_INTELLIGENCE_PORT", "8001"))
    log_level: str = os.environ.get("PHOENIX_INTELLIGENCE_LOG_LEVEL", "info")
    log_json: bool = os.environ.get("PHOENIX_LOG_JSON", "false").lower() == "true"
