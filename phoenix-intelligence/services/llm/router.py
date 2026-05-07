"""LLM Router — selects and wraps the active LLM provider.

Supported providers
-------------------
anthropic   → Anthropic Claude  (ANTHROPIC_API_KEY)
openai      → OpenAI            (OPENAI_API_KEY)
gemini      → Google Gemini     (GOOGLE_API_KEY)
ollama      → Local Ollama      (no key required)

Fallback behaviour
------------------
If the primary provider fails (rate limit, timeout, missing package, wrong key),
the router automatically tries the next provider in the configured fallback chain.
Only if ALL providers fail does it raise an exception — never returns empty output.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol, runtime_checkable

from services.config import LLMSettings

logger = logging.getLogger(__name__)

_RATE_LIMIT_WAIT = 60  # seconds to wait on 429 before trying next provider


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface every provider must implement."""

    def generate(self, system_prompt: str, user_prompt: str) -> str: ...


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """Wraps the Anthropic Python SDK."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._settings.api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Set the environment variable before starting the intelligence server."
                )
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._settings.api_key)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        logger.info(
            "Calling Anthropic %s (max_tokens=%d, temperature=%.1f)",
            self._settings.model,
            self._settings.max_tokens,
            self._settings.temperature,
        )
        message = client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            temperature=self._settings.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text
        logger.info(
            "Anthropic response: %d chars, input=%d tokens, output=%d tokens",
            len(text),
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        return _strip_code_fences(text)

    @staticmethod
    def check_available() -> tuple[bool, str]:
        """Pre-flight: verify the package and API key are present."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "pip install anthropic"
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY not set"
        return True, "OK"


class OpenAIProvider:
    """Wraps the OpenAI Python SDK."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            import os

            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. "
                    "Set the environment variable before starting the intelligence server."
                )
            import openai

            self._client = openai.OpenAI(api_key=api_key)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        model = self._settings.model or "gpt-4o"
        logger.info("Calling OpenAI %s", model)
        response = client.chat.completions.create(
            model=model,
            max_tokens=self._settings.max_tokens,
            temperature=self._settings.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        logger.info("OpenAI response: %d chars", len(text))
        return _strip_code_fences(text)

    @staticmethod
    def check_available() -> tuple[bool, str]:
        try:
            import openai  # noqa: F401
        except ImportError:
            return False, "pip install openai"
        if not os.environ.get("OPENAI_API_KEY"):
            return False, "OPENAI_API_KEY not set"
        return True, "OK"


class GeminiProvider:
    """Wraps Google GenerativeAI SDK (google-generativeai)."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._model = None

    def _get_model(self):
        if self._model is None:
            import os

            api_key = os.environ.get("GOOGLE_API_KEY", "")
            if not api_key:
                raise RuntimeError(
                    "GOOGLE_API_KEY is not set. "
                    "Set the environment variable before starting the intelligence server."
                )
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model_name = self._settings.model or "gemini-1.5-pro"
            self._model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=None,
            )
        return self._model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._get_model()
        combined = f"{system_prompt}\n\n{user_prompt}"
        logger.info("Calling Gemini %s", self._settings.model)
        response = model.generate_content(combined)
        text = response.text or ""
        logger.info("Gemini response: %d chars", len(text))
        return _strip_code_fences(text)

    @staticmethod
    def check_available() -> tuple[bool, str]:
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return False, "pip install google-generativeai"
        if not os.environ.get("GOOGLE_API_KEY"):
            return False, "GOOGLE_API_KEY not set"
        return True, "OK"


class OllamaProvider:
    """Calls a local Ollama instance via its REST API."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        import os

        self._base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import json
        import urllib.request

        model = self._settings.model or "llama3"
        logger.info("Calling Ollama %s at %s", model, self._base_url)
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": self._settings.temperature},
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        text = data.get("message", {}).get("content", "")
        logger.info("Ollama response: %d chars", len(text))
        return _strip_code_fences(text)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

_DEFAULT_FALLBACK_CHAIN = ["anthropic", "gemini", "openai", "ollama"]


class LLMRouter:
    """Instantiates the correct provider based on LLMSettings.provider.

    If the primary provider fails (rate limit, missing key, import error,
    timeout), the router automatically tries the next provider in the
    fallback chain.  Only raises if *all* providers fail.
    """

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings()
        primary = self.settings.provider.lower()
        if primary not in _PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider '{primary}'. Supported: {list(_PROVIDERS.keys())}"
            )

        # Build fallback chain: primary first, then remaining providers
        others = [p for p in _DEFAULT_FALLBACK_CHAIN if p != primary]
        self._chain: list[str] = [primary] + others

        logger.info(
            "LLM Router initialised: primary=%s model=%s fallback_chain=%s",
            primary,
            self.settings.model,
            self._chain[1:],
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Try each provider in chain; return first successful response."""
        last_error: Exception | None = None

        for provider_name in self._chain:
            provider_cls = _PROVIDERS[provider_name]
            provider: LLMProvider = provider_cls(self.settings)

            # Pre-flight check — skip unavailable providers immediately
            if hasattr(provider_cls, "check_available"):
                ok, reason = provider_cls.check_available()
                if not ok:
                    logger.warning(
                        "Skipping provider '%s': %s", provider_name, reason
                    )
                    last_error = RuntimeError(f"{provider_name} unavailable: {reason}")
                    continue

            try:
                result = provider.generate(system_prompt, user_prompt)
                if provider_name != self._chain[0]:
                    logger.info("Fallback provider '%s' succeeded.", provider_name)
                return result

            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate limit" in err_str or "quota" in err_str:
                    logger.warning(
                        "Provider '%s' rate-limited — waiting %ds before next provider",
                        provider_name,
                        _RATE_LIMIT_WAIT,
                    )
                    time.sleep(_RATE_LIMIT_WAIT)
                else:
                    logger.warning(
                        "Provider '%s' failed: %s — trying next provider",
                        provider_name,
                        exc,
                    )
                last_error = exc

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}\n"
            "Check API keys and provider availability."
        ) from last_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()
