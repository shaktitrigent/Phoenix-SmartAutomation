"""Locator discovery agent — uses LLM + MCP to find stable Playwright locators."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

_prompt_loader = PromptLoader()


class LocatorExpertAgent(BaseAgent):
    """Discovers stable Playwright locators for UI elements.

    Flow:
        1. Inspect the live page via MCP to get an accessibility snapshot.
        2. Build a prompt from the versioned ``locator_expert/1.0.md`` prompt.
        3. Call the LLM → returns JSON with primary + fallback locators.
        4. Falls back to role/test-id heuristic when LLM is unavailable.
    """

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        page_url = input_data.get("page_url", "")
        element_name = input_data.get("element_name", "")
        dom_snapshot = input_data.get("dom_snapshot")

        cache_key = self._cache_key("locator", page_url=page_url, element_name=element_name)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        locators = self._discover_locators(element_name, page_url, dom_snapshot)

        result = {
            "locators": locators,
            "recommended_locator": locators[0] if locators else None,
            "metadata": {
                "page_url": page_url,
                "element_name": element_name,
                "llm_used": bool(self.llm_client),
                "mcp_used": bool(self.mcp_client and page_url),
            },
        }

        self.cache.set(cache_key, result, ttl=7200)
        return result

    # ------------------------------------------------------------------

    def _discover_locators(
        self,
        element_name: str,
        page_url: str,
        dom_snapshot: Optional[str],
    ) -> List[Dict[str, Any]]:
        return self._llm_with_fallback(
            llm_fn=lambda: self._discover_via_llm(element_name, page_url, dom_snapshot),
            fallback_fn=lambda: self._heuristic_locators(element_name),
            operation="LocatorExpertAgent",
        )

    def _discover_via_llm(
        self,
        element_name: str,
        page_url: str,
        dom_snapshot: Optional[str],
    ) -> List[Dict[str, Any]]:
        # Get live page snapshot via MCP if we don't already have one.
        # Phase D: best-effort — a failing MCP call must not abort locator discovery.
        snapshot = dom_snapshot or ""
        if not snapshot and self.mcp_client and page_url:
            logger.info("Fetching page snapshot via MCP: %s", page_url)
            try:
                snapshot = self.mcp_client.inspect_page(page_url) or ""
            except Exception as _mcp_exc:
                logger.warning(
                    "MCP inspect_page failed for %s — continuing without snapshot: %s",
                    page_url, _mcp_exc,
                )
                snapshot = ""

        system_prompt = _prompt_loader.get("locator_expert")

        # Inject locator strategy knowledge
        knowledge_context = self.get_knowledge_context(query="locator strategy")

        user_parts = [
            f"Discover stable Playwright locators for the element: **{element_name}**",
            f"\nPage URL: {page_url or 'not provided'}",
        ]
        if knowledge_context:
            user_parts.append(f"\n## Locator Strategy Knowledge\n{knowledge_context[:1000]}")
        if snapshot:
            user_parts += [
                "\n## Page Accessibility Snapshot",
                "Use the snapshot below to choose accurate locators.",
                "",
                snapshot,
            ]
        else:
            user_parts.append(
                "\nNo page snapshot available. Use your best judgement based on the element name."
            )

        user_parts.append(
            "\nReturn a JSON object with a `locators` array as specified in the system prompt."
        )

        logger.info("Discovering locators for '%s' via LLM", element_name)
        raw = self.llm_client.generate(system_prompt, "\n".join(user_parts))
        return self._parse_locators(raw)

    @staticmethod
    def _parse_locators(raw: str) -> List[Dict[str, Any]]:
        """Extract the locators array from the LLM response."""
        raw = raw.strip()
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw).strip()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("locators", [])
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return []

    @staticmethod
    def _heuristic_locators(element_name: str) -> List[Dict[str, Any]]:
        """Simple role/test-id fallback when the LLM is unavailable."""
        slug = element_name.lower().replace(" ", "-")
        label = element_name.title()
        return [
            {
                "element_name": element_name,
                "strategy": "role",
                "value": f"button[name='{label}']",
                "playwright_code": f"page.get_by_role('button', name='{label}')",
                "confidence": 0.7,
                "fallback": False,
                "description": "Semantic role locator (heuristic)",
            },
            {
                "element_name": element_name,
                "strategy": "test-id",
                "value": f"[data-testid='{slug}']",
                "playwright_code": f"page.get_by_test_id('{slug}')",
                "confidence": 0.6,
                "fallback": True,
                "description": "test-id fallback (heuristic)",
            },
        ]
