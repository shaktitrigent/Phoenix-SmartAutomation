"""Test generation agent — uses LLM + Knowledge Base + MCP for real code generation."""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

_prompt_loader = PromptLoader()


class TestGeneratorAgent(BaseAgent):
    """Agent specialised in generating test cases from user stories.

    Flow (automation):
        1. Load knowledge context from the Knowledge Base.
        2. Inspect the target page via Playwright MCP (accessibility snapshot).
        3. Build prompt from versioned prompt file (prompts/test_generator/1.0.md).
        4. Call LLM → returns complete Playwright script code.

    Flow (manual):
        1. Build prompt from versioned prompt file (prompts/manual_test_generator/1.0.md).
        2. Call LLM → returns JSON array of structured test cases.
        3. Falls back to heuristic if LLM unavailable.
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
            test_type=test_type,
        )
        cached = self.cache.get(cache_key)
        if cached:
            logger.info("Returning cached result for %s", cache_key)
            return cached

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
    # Manual tests — LLM-powered structured output
    # ------------------------------------------------------------------

    def _generate_manual_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        if self.llm_client:
            try:
                return self._generate_manual_tests_via_llm(
                    user_story, application_url, acceptance_criteria, risk_level
                )
            except Exception as exc:
                logger.warning("LLM manual test generation failed, using fallback: %s", exc)

        return self._generate_manual_tests_fallback(
            user_story, application_url, acceptance_criteria, risk_level
        )

    def _generate_manual_tests_via_llm(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Call the LLM using the versioned manual_test_generator prompt."""
        system_prompt = _prompt_loader.get("manual_test_generator")

        criteria_text = "\n".join(f"  {i}. {c}" for i, c in enumerate(acceptance_criteria, 1))
        risk_instruction = (
            f"\nFocus on generating '{risk_level}' level tests." if risk_level else ""
        )

        user_prompt = (
            f"Generate structured manual test cases for the following user story.\n\n"
            f"## User Story\n{user_story}\n\n"
            f"## Application URL\n{application_url or 'Not specified'}\n\n"
            f"## Acceptance Criteria\n{criteria_text or '  (none provided)'}"
            f"{risk_instruction}\n\n"
            f"Return a JSON array of test case objects as specified in the system prompt."
        )

        # Inject knowledge context (test patterns, best practices) into user prompt
        knowledge_context = self.get_knowledge_context(query=user_story)
        if knowledge_context:
            user_prompt += f"\n\n## Additional Context (Knowledge Base)\n{knowledge_context[:1500]}"

        logger.info("Generating manual tests via LLM for: %s", user_story[:80])
        raw = self.llm_client.generate(system_prompt, user_prompt)
        tests = self._parse_json_array(raw)

        if not tests:
            raise ValueError("LLM returned empty or unparseable manual test JSON")

        # Normalise each test case from the LLM
        normalised = []
        for idx, test in enumerate(tests, 1):
            normalised.append({
                "name": test.get("name", f"TC-{idx:03d}: {user_story[:50]}"),
                "description": test.get("description", user_story),
                "risk_level": test.get("risk_level", risk_level or "regression"),
                "preconditions": test.get("preconditions", ""),
                "steps": self._normalise_steps(test.get("steps", [])),
                "expected_result": test.get("expected_result", ""),
                "postconditions": test.get("postconditions", ""),
                "tags": test.get("tags", ["manual", "generated"]),
            })

        logger.info("LLM generated %d manual test(s)", len(normalised))
        return normalised

    def _generate_manual_tests_fallback(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Heuristic fallback when LLM is unavailable."""
        steps = []
        if application_url:
            steps.append({
                "step_number": 1,
                "action": f"Navigate to {application_url}",
                "expected_result": "Page loads successfully",
            })
        for idx, criteria in enumerate(acceptance_criteria, 1):
            steps.append({
                "step_number": len(steps) + 1,
                "action": criteria,
                "expected_result": "Step completes as expected",
            })

        test_name = self._derive_short_name(user_story)
        return [
            {
                "name": f"TC-001: {test_name.replace('_', ' ').title()}",
                "description": user_story,
                "risk_level": risk_level or "regression",
                "preconditions": "User has access to the application",
                "steps": steps,
                "expected_result": "All acceptance criteria are met",
                "postconditions": "",
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
                "LLM client is not configured. "
                "Set a supported provider key and restart the server."
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

        # Step 2 — Load versioned system prompt
        system_prompt_template = _prompt_loader.get("test_generator")
        system_prompt = system_prompt_template.format(
            knowledge_context=knowledge_context if knowledge_context else "(no additional context)"
        )

        # Step 3 — Build user prompt
        criteria_text = "\n".join(f"  {i}. {c}" for i, c in enumerate(acceptance_criteria, 1))
        user_parts = [
            "Generate a complete pytest + Playwright test script for the following user story.",
            "",
            f"## User Story\n{user_story}",
            "",
            f"## Application URL\n{application_url or 'N/A'}",
            "",
            f"## Acceptance Criteria\n{criteria_text}",
        ]

        if page_snapshot:
            user_parts += [
                "",
                "## Page Accessibility Snapshot (live inspection of the target page)",
                "Use the element roles, names, and values below to choose accurate locators.",
                "",
                page_snapshot,
            ]
        else:
            user_parts += [
                "",
                "## Page Snapshot",
                "No live page snapshot available. Use your best judgement for locators "
                "based on common web patterns and the acceptance criteria.",
            ]

        user_parts += [
            "",
            "## Instructions",
            "- Write ONE test function that covers all acceptance criteria.",
            "- Use the locator priority order defined in the system prompt.",
            "- If the page snapshot contains exact element names/roles, use them directly.",
            "- Include meaningful assertions for each acceptance criterion.",
            "- Return ONLY the Python source code, nothing else.",
        ]

        user_prompt = "\n".join(user_parts)

        # Step 4 — Call LLM
        logger.info("Generating automation script via LLM for: %s", user_story[:80])
        script_code = self.llm_client.generate(system_prompt, user_prompt)

        # Step 5 — Derive a clean name
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
        """Derive a short snake_case name — LLM first, heuristic fallback."""
        if self.llm_client:
            try:
                system_prompt = _prompt_loader.get("test_name")
                raw = self.llm_client.generate(system_prompt, user_story).strip()
                name = re.sub(r"[^a-z0-9_]", "", raw.lower().replace(" ", "_"))
                if name:
                    return name[:40]
            except Exception:
                logger.debug("LLM naming failed, using heuristic", exc_info=True)

        story = user_story.lower()
        for prefix in ("as a user, i want to ", "as a tester, i want to ", "i want to "):
            if prefix in story:
                story = story.split(prefix, 1)[1]
                break
        story = story.split(" so that")[0].split(" in order to")[0]
        name = re.sub(r"[^a-z0-9]+", "_", story).strip("_")[:40]
        return name or "automation_test"

    @staticmethod
    def _parse_json_array(raw: str) -> List[Dict[str, Any]]:
        """Extract a JSON array from the LLM response."""
        raw = raw.strip()
        # Strip any accidental code fences
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tests" in data:
                return data["tests"]
        except json.JSONDecodeError:
            # Try to find a JSON array anywhere in the response
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return []

    @staticmethod
    def _normalise_steps(steps: Any) -> List[Dict[str, Any]]:
        """Normalise steps — accept list-of-dicts or list-of-strings."""
        if not steps:
            return []
        normalised = []
        for idx, step in enumerate(steps, 1):
            if isinstance(step, dict):
                normalised.append({
                    "step_number": step.get("step_number", idx),
                    "action": step.get("action", str(step)),
                    "expected_result": step.get("expected_result", ""),
                    "test_data": step.get("test_data", ""),
                })
            else:
                normalised.append({
                    "step_number": idx,
                    "action": str(step),
                    "expected_result": "",
                    "test_data": "",
                })
        return normalised
