"""Anthropic Claude LLM client for phoenix-intelligence."""

import logging
import re
from typing import Optional

from services.config import LLMSettings

logger = logging.getLogger(__name__)


class LLMClient:
    """Wraps the Anthropic Python SDK to generate text via Claude."""

    def __init__(self, settings: Optional[LLMSettings] = None):
        self.settings = settings or LLMSettings()
        self._client = None

    def _get_client(self):
        """Lazily initialise the Anthropic client so the import is deferred."""
        if self._client is None:
            if not self.settings.api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Set the environment variable before starting the intelligence server."
                )
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.settings.api_key)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to Claude and return the assistant text.

        Args:
            system_prompt: Instructions that define Claude's role and output format.
            user_prompt: The concrete task (user story, page snapshot, etc.).

        Returns:
            The raw text content returned by Claude.
        """
        client = self._get_client()

        logger.info(
            "Calling Anthropic %s (max_tokens=%d, temperature=%.1f)",
            self.settings.model,
            self.settings.max_tokens,
            self.settings.temperature,
        )

        message = client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = message.content[0].text

        logger.info(
            "Claude response: %d chars, input_tokens=%d, output_tokens=%d",
            len(text),
            message.usage.input_tokens,
            message.usage.output_tokens,
        )

        return self._strip_code_fences(text)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences if Claude wraps the output in them."""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
            stripped = re.sub(r"\n?```\s*$", "", stripped)
        return stripped.strip()
