"""Build request-scoped Intelligence clients without changing process state."""

from dataclasses import dataclass
from typing import Mapping, Optional

from services.config import LLMSettings
from services.llm.client import LLMClient


@dataclass(frozen=True)
class RequestLLMResult:
    client: Optional[LLMClient]
    available: bool
    reason: Optional[str] = None


def build_request_llm(values: Mapping[str, str]) -> RequestLLMResult:
    key = values.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return RequestLLMResult(None, False, "anthropic_key_missing")
    if len(key) < 20 or not key.startswith("sk-ant-"):
        return RequestLLMResult(None, False, "anthropic_key_invalid")
    try:
        max_tokens = int(values.get("PHOENIX_LLM_MAX_TOKENS", "4096"))
        temperature = float(values.get("PHOENIX_LLM_TEMPERATURE", "0.2"))
    except ValueError:
        return RequestLLMResult(None, False, "llm_configuration_invalid")
    settings = LLMSettings(
        provider="anthropic",
        api_key=key,
        model=values.get("PHOENIX_LLM_MODEL", "claude-sonnet-4-6"),
        max_tokens=max_tokens,
        temperature=temperature,
        prompts_dir=values.get("PHOENIX_PROMPTS_DIR", ""),
    )
    # LLMSettings has legacy process-backed initialization. Re-apply the
    # immutable request snapshot so no shared/server value can win.
    settings.provider = "anthropic"
    settings.api_key = key
    settings.model = values.get("PHOENIX_LLM_MODEL", "claude-sonnet-4-6")
    settings.max_tokens = max_tokens
    settings.temperature = temperature
    return RequestLLMResult(LLMClient(settings), True)
