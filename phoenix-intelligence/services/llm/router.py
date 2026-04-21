"""LLM router with provider auto-selection and fallback support."""

from __future__ import annotations

import logging
import os
import re
from typing import Protocol, runtime_checkable

from services.config import LLMSettings

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface every provider must implement."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...


class AnthropicProvider:
    """Wrap the Anthropic Python SDK."""

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


class OpenAIProvider:
    """Wrap the OpenAI Python SDK."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
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


class GeminiProvider:
    """Wrap the Google Generative AI SDK."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._model = None

    def _get_model(self):
        if self._model is None:
            api_key = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                raise RuntimeError(
                    "GOOGLE_API_KEY or GEMINI_API_KEY is not set. "
                    "Set one of them before starting the intelligence server."
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


class OllamaProvider:
    """Call a local Ollama instance via its REST API."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
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


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

_MODEL_PROVIDER_HINTS = (
    ("claude", "anthropic"),
    ("anthropic", "anthropic"),
    ("gemini", "gemini"),
    ("gpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("llama", "ollama"),
    ("mistral", "ollama"),
)


class LLMRouter:
    """Select the active provider from explicit config, auto-detection, or fallbacks."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings()
        self.provider_candidates = _resolve_provider_candidates(self.settings)
        if not self.provider_candidates:
            raise RuntimeError(
                "No usable LLM provider could be resolved. "
                "Set PHOENIX_LLM_PROVIDER or configure one of: "
                "ANTHROPIC_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY."
            )
        self.active_provider_name = self.provider_candidates[0]
        self._providers: dict[str, LLMProvider] = {}
        logger.info(
            "LLM Router initialised: providers=%s model=%s",
            " -> ".join(self.provider_candidates),
            self.settings.model,
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        errors: list[str] = []
        for provider_name in self.provider_candidates:
            provider = self._get_provider(provider_name)
            self.active_provider_name = provider_name
            try:
                return provider.generate(system_prompt, user_prompt)
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                if provider_name == self.provider_candidates[-1]:
                    break
                logger.warning(
                    "LLM provider '%s' failed, trying next fallback provider: %s",
                    provider_name,
                    exc,
                )

        raise RuntimeError(
            "All configured LLM providers failed. " + " | ".join(errors)
        )

    def _get_provider(self, provider_name: str) -> LLMProvider:
        if provider_name not in self._providers:
            self._providers[provider_name] = _PROVIDERS[provider_name](self.settings)
        return self._providers[provider_name]


def _resolve_provider_candidates(settings: LLMSettings) -> list[str]:
    raw_tokens = [
        token.strip().lower()
        for token in settings.provider.replace(";", ",").split(",")
        if token.strip()
    ]
    tokens = raw_tokens or ["auto"]
    candidates: list[str] = []

    for token in tokens:
        if token == "auto":
            candidates.extend(_auto_provider_candidates(settings))
            continue
        if token not in _PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider '{token}'. Supported: {list(_PROVIDERS.keys())} or 'auto'."
            )
        candidates.append(token)

    return _dedupe(candidates)


def _auto_provider_candidates(settings: LLMSettings) -> list[str]:
    candidates: list[str] = []
    model_name = os.environ.get("PHOENIX_LLM_MODEL", "").strip().lower()

    if model_name:
        for prefix, provider_name in _MODEL_PROVIDER_HINTS:
            if model_name.startswith(prefix):
                candidates.append(provider_name)
                break

    if settings.api_key:
        candidates.append("anthropic")
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        candidates.append("gemini")
    if os.environ.get("OPENAI_API_KEY"):
        candidates.append("openai")
    if os.environ.get("OLLAMA_BASE_URL"):
        candidates.append("ollama")

    if not candidates:
        candidates.extend(["anthropic", "gemini", "openai", "ollama"])

    return _dedupe(candidates)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()
