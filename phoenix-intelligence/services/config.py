"""Configuration for phoenix-intelligence services."""

import os
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_PROVIDER = os.environ.get("PHOENIX_LLM_PROVIDER", "gemini").lower()
_PROVIDER_API_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": "",
}
_PROVIDER_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3",
}


def _provider_api_key_env_var(provider: str) -> str:
    return _PROVIDER_API_KEYS.get(provider.lower(), "GOOGLE_API_KEY")


def _provider_default_model(provider: str) -> str:
    return _PROVIDER_DEFAULT_MODELS.get(provider.lower(), "gemini-2.5-flash")


@dataclass
class LLMSettings:
    """LLM provider settings - supports anthropic, openai, gemini, ollama."""

    provider: str = _DEFAULT_PROVIDER
    api_key_env_var: str = _provider_api_key_env_var(provider)
    api_key: str = os.environ.get(api_key_env_var, "")
    model: str = os.environ.get("PHOENIX_LLM_MODEL", _provider_default_model(provider))
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