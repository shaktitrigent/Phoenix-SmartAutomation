"""Test generation agent — uses LLM + Knowledge Base + MCP for real code generation."""

import logging
import re
from typing import Dict, Any, List, Optional

from services.agents.base import BaseAgent
from services.llm.prompts import build_test_generation_prompt, build_test_name_prompt

logger = logging.getLogger(__name__)


class TestGeneratorAgent(BaseAgent):
    """Agent specialised in generating test cases from user stories.

    Flow:
        1. Load knowledge context from the Knowledge Base.
        2. Inspect the target page via Playwright MCP (accessibility snapshot).
        3. Send everything to Anthropic Claude to produce complete Playwright code.
        4. Return the generated ``script_code`` alongside manual test steps.
    """

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        user_story = input_data.get("user_story", "")
        application_url = input_data.get("application_url")
        acceptance_criteria = input_data.get("acceptance_criteria", [])
        test_type = kwargs.get("test_type", "both")
        risk_level = kwargs.get("risk_level")

        knowledge_context = self.get_knowledge_context(query=user_story)

        cache_key = self._cache_key(
            "test_generation",
            user_story=user_story,
            application_url=application_url or "",
            acceptance_criteria=acceptance_criteria,
        )
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info("Returning cached result for %s", cache_key)
            return cached_result

        result: Dict[str, Any] = {
            "manual_tests": [],
            "automation_tests": [],
            "metadata": {
                "user_story": user_story,
                "application_url": application_url,
                "acceptance_criteria": acceptance_criteria,
                "knowledge_context_used": bool(knowledge_context),
                "test_type": test_type,
                "risk_level": risk_level,
            },
        }

        if test_type in ("manual", "both"):
            result["manual_tests"] = self._generate_manual_tests(
                user_story, application_url, acceptance_criteria, risk_level
            )

        if test_type in ("automation", "both"):
            result["automation_tests"] = self._generate_automation_tests(
                user_story, application_url, acceptance_criteria, knowledge_context, risk_level
            )

        self.cache.set(cache_key, result, ttl=3600)
        return result

    # ------------------------------------------------------------------
    # Manual tests — simple structured output (no LLM needed)
    # ------------------------------------------------------------------

    def _generate_manual_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        steps = []
        if application_url:
            steps.append(f"Navigate to {application_url}")
        for idx, criteria in enumerate(acceptance_criteria, 1):
            steps.append(f"Step {idx}: {criteria}")

        test_name = self._derive_short_name(user_story)

        return [
            {
                "name": f"Manual Test: {test_name}",
                "description": user_story,
                "steps": steps,
                "expected_result": "All acceptance criteria are met and the user story is fulfilled",
                "risk_level": risk_level or "regression",
                "tags": ["manual", "generated"],
            }
        ]

    # ------------------------------------------------------------------
    # Automation tests — LLM + MCP powered
    # ------------------------------------------------------------------

    def _generate_automation_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        knowledge_context: str,
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not self.llm_client:
            raise RuntimeError(
                "LLM client is not configured. Set ANTHROPIC_API_KEY and restart the intelligence server."
            )

        # Step 1 — Inspect the live page via MCP
        page_snapshot = ""
        if self.mcp_client and application_url:
            logger.info("Inspecting page via MCP: %s", application_url)
            page_snapshot = self.mcp_client.inspect_page(application_url)
            if page_snapshot:
                logger.info("MCP snapshot received (%d chars)", len(page_snapshot))
            else:
                logger.warning("MCP returned empty snapshot for %s", application_url)

        # Step 2 — Build the prompt
        system_prompt, user_prompt = build_test_generation_prompt(
            user_story=user_story,
            acceptance_criteria=acceptance_criteria,
            knowledge_context=knowledge_context,
            page_snapshot=page_snapshot,
            application_url=application_url,
        )

        # Step 3 — Call Claude
        logger.info("Generating automation script via LLM for: %s", user_story[:80])
        script_code = self.llm_client.generate(system_prompt, user_prompt)

        # Step 4 — Derive a clean short name
        test_name = self._derive_short_name(user_story)

        return [
            {
                "name": test_name,
                "description": user_story,
                "script_template": "playwright",
                "script_code": script_code,
                "test_steps": acceptance_criteria,
                "locators": [],
                "application_url": application_url,
                "risk_level": risk_level or "regression",
                "tags": ["automation", "generated", "llm"],
            }
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _derive_short_name(self, user_story: str) -> str:
        """Derive a short, clean snake_case name from the user story.

        Uses the LLM if available, otherwise falls back to a simple heuristic.
        """
        if self.llm_client:
            try:
                system, user = build_test_name_prompt(user_story)
                raw = self.llm_client.generate(system, user).strip()
                name = re.sub(r"[^a-z0-9_]", "", raw.lower().replace(" ", "_"))
                if name:
                    return name[:40]
            except Exception:
                logger.debug("LLM naming failed, using heuristic", exc_info=True)

        # Heuristic fallback
        story = user_story.lower()
        for prefix in ("as a user, i want to ", "as a tester, i want to ", "i want to "):
            if prefix in story:
                story = story.split(prefix, 1)[1]
                break
        story = story.split(" so that")[0].split(" in order to")[0]
        name = re.sub(r"[^a-z0-9]+", "_", story).strip("_")[:40]
        return name or "automation_test"
