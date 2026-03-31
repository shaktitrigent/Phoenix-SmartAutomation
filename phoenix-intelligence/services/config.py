"""Configuration for phoenix-intelligence services."""

import os
from dataclasses import dataclass, field


@dataclass
class LLMSettings:
    """Anthropic Claude LLM settings."""

    provider: str = os.environ.get("PHOENIX_LLM_PROVIDER", "anthropic")
    api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    model: str = os.environ.get("PHOENIX_LLM_MODEL", "claude-sonnet-4-20250514")
    max_tokens: int = int(os.environ.get("PHOENIX_LLM_MAX_TOKENS", "4096"))
    temperature: float = float(os.environ.get("PHOENIX_LLM_TEMPERATURE", "0.2"))


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
