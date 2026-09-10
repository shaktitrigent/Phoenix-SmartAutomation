"""Configuration for phoenix-intelligence services."""

import os
from dataclasses import dataclass
from pathlib import Path


def _provider_key_name(provider: str) -> str:
    """Only Anthropic is supported."""
    return "ANTHROPIC_API_KEY"


def _default_model(provider: str) -> str:
    """Only Anthropic models are supported."""
    return "claude-sonnet-4-6"


@dataclass
class LLMSettings:
    """LLM provider settings - supports anthropic, openai, gemini, ollama."""

    provider: str = "anthropic"
    api_key: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.2
    # Prompt versioning
    prompts_dir: str = ""

    def __post_init__(self):
        """Initialize settings from environment variables after instance creation."""
        # Read provider from environment
        self.provider = os.environ.get("PHOENIX_LLM_PROVIDER", self.provider or "anthropic")

        # Read API key based on provider
        if not self.api_key:
            self.api_key = os.environ.get(
                _provider_key_name(self.provider),
                "",
            )

        # Read model from environment or use default
        if not self.model:
            self.model = os.environ.get(
                "PHOENIX_LLM_MODEL",
                _default_model(self.provider),
            )

        # Read other settings from environment
        self.max_tokens = int(os.environ.get("PHOENIX_LLM_MAX_TOKENS", str(self.max_tokens)))
        self.temperature = float(os.environ.get("PHOENIX_LLM_TEMPERATURE", str(self.temperature)))

        # Set prompts directory
        if not self.prompts_dir:
            self.prompts_dir = os.environ.get(
                "PHOENIX_PROMPTS_DIR",
                str(Path(__file__).resolve().parents[1] / "prompts"),
            )
    
    def is_configured(self) -> bool:
        """Check if Anthropic API key is properly configured."""
        # Refresh API key from environment to catch runtime changes
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", self.api_key)

        # Check if API key exists
        api_key = self.api_key
        if not api_key:
            return False

        # Check for minimum length (real Anthropic API keys are much longer than 20 chars)
        if len(api_key) < 20:
            return False

        # Anthropic-specific format validation
        if not api_key.startswith("sk-ant-"):
            return False

        return True


@dataclass
class MCPSettings:
    """Playwright MCP settings for page inspection via stdio."""

    enabled: bool = os.environ.get("PHOENIX_MCP_ENABLED", "true").lower() == "true"
    command: str = os.environ.get("PHOENIX_MCP_COMMAND", "npx")
    args: str = os.environ.get("PHOENIX_MCP_ARGS", "@playwright/mcp@latest")
    timeout: int = int(os.environ.get("PHOENIX_MCP_TIMEOUT", "30"))


@dataclass
class IntelligenceSettings:
    """Intelligence API settings."""

    host: str = os.environ.get("PHOENIX_INTELLIGENCE_HOST", "0.0.0.0")
    port: int = int(os.environ.get("PHOENIX_INTELLIGENCE_PORT", "8001"))
    log_level: str = os.environ.get("PHOENIX_INTELLIGENCE_LOG_LEVEL", "info")
    log_json: bool = os.environ.get("PHOENIX_LOG_JSON", "false").lower() == "true"
