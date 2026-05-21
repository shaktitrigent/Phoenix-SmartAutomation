"""Failure analysis agent — uses LLM to diagnose Playwright test failures."""

import json
import logging
import re
from typing import Any, Dict

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

_prompt_loader = PromptLoader()


def _load_quality_standards() -> str:
    try:
        return _prompt_loader.get("test_quality_standards")
    except (FileNotFoundError, KeyError):
        return ""


class FailureAnalyzerAgent(BaseAgent):
    """Analyzes test failures and suggests targeted fixes.

    Flow:
        1. Build a prompt from the versioned ``failure_analyzer/1.0.md`` prompt.
        2. Call the LLM with the error message + traceback.
        3. Parse the structured JSON response (root_cause, suggested_fix, etc.).
        4. Falls back to pattern-matching heuristic when LLM is unavailable.
    """

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        test_case_id = input_data.get("test_case_id", "unknown")
        error_message = input_data.get("error_message", "")
        traceback = input_data.get("traceback", "")

        result = self._llm_with_fallback(
            llm_fn=lambda: self._analyze_via_llm(error_message, traceback),
            fallback_fn=lambda: self._analyze_heuristic(test_case_id, error_message, traceback),
            operation="FailureAnalyzerAgent",
        )
        result.setdefault("metadata", {})["test_case_id"] = test_case_id
        return result

    # ------------------------------------------------------------------

    def _analyze_via_llm(self, error_message: str, traceback: str) -> Dict[str, Any]:
        system_prompt = _prompt_loader.get("failure_analyzer")

        knowledge_context = self.get_knowledge_context(query=error_message)
        user_prompt = (
            "Analyze the following Playwright test failure and return a JSON object "
            "as specified in the system prompt.\n\n"
            f"## Error Message\n{error_message}\n"
        )
        if traceback:
            user_prompt += f"\n## Traceback\n{traceback}\n"
        if knowledge_context:
            user_prompt += f"\n## Relevant Knowledge\n{knowledge_context[:800]}"

        quality_standards = _load_quality_standards()
        if quality_standards:
            user_prompt += f"\n\n## Quality Standards (the suggested fix must comply with these)\n{quality_standards}"

        logger.info("Analyzing failure via LLM: %s", error_message[:120])
        raw = self.llm_client.generate(system_prompt, user_prompt)
        return self._parse_llm_response(raw)

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw).strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {
                    "root_cause": data.get("root_cause", ""),
                    "category": data.get("category", "unknown"),
                    "confidence": float(data.get("confidence", 0.5)),
                    "suggested_fix": data.get("suggested_fix", ""),
                    "code_snippet": data.get("code_snippet", ""),
                    "related_locators": data.get("related_locators", []),
                    "prevention": data.get("prevention", ""),
                    "metadata": {},
                }
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse structured LLM response; falling back to raw text")
        # If parsing fails, return the raw text as the suggested fix
        return {
            "root_cause": "Could not parse structured response from LLM",
            "category": "unknown",
            "confidence": 0.3,
            "suggested_fix": raw,
            "code_snippet": "",
            "related_locators": [],
            "prevention": "",
            "metadata": {},
        }

    @staticmethod
    def _analyze_heuristic(test_case_id: str, error_message: str, traceback: str) -> Dict[str, Any]:
        """Pattern-matching fallback when LLM is unavailable."""
        error_lower = error_message.lower()

        if "timeout" in error_lower or "waiting" in error_lower:
            category = "timing"
            root_cause = "Element not found within the timeout period"
            fix = (
                "Replace time-based waits with Playwright's built-in auto-waiting. "
                "Use expect(locator).to_be_visible() instead of page.wait_for_timeout(), "
                "and verify overlays or modals are not intercepting the action."
            )
        elif any(token in error_lower for token in ["overlay", "intercepts pointer events", "another element"]):
            category = "overlay"
            root_cause = "An overlay, modal, or blocking element prevented interaction"
            fix = (
                "Dismiss or scope to the active dialog before acting. "
                "Validate the target is unique and visible, then retry the action."
            )
        elif "strict mode" in error_lower or "resolved to" in error_lower:
            category = "locator"
            root_cause = "Locator matched multiple elements (strict mode violation)"
            fix = (
                "Scope the locator to a stable parent container, add exact=True where appropriate, "
                "and validate uniqueness with expect(locator).to_have_count(1) before acting."
            )
        elif "not found" in error_lower or "locator" in error_lower:
            category = "locator"
            root_cause = "Element could not be found on the page"
            fix = (
                "Use semantic locators in priority order: "
                "get_by_role > get_by_label > get_by_placeholder > get_by_text > get_by_test_id."
            )
        elif "assertionerror" in error_lower or "expect(" in error_lower:
            category = "assertion"
            root_cause = "Assertion failed — actual value does not match expected"
            fix = "Review the expected value in the assertion. Add logging before the assertion to see the actual value."
        elif "network" in error_lower or "connection" in error_lower:
            category = "network"
            root_cause = "Network error or API connection failure"
            fix = "Verify the application is running and accessible at the configured URL."
        else:
            category = "unknown"
            root_cause = "Could not identify a specific failure pattern"
            fix = "Review the full traceback for details. Enable Playwright tracing for step-by-step diagnostics."

        return {
            "root_cause": root_cause,
            "category": category,
            "confidence": 0.6,
            "suggested_fix": fix,
            "code_snippet": "",
            "related_locators": [],
            "prevention": "Enable Playwright tracing (--tracing=on) for better diagnostics.",
            "metadata": {"test_case_id": test_case_id, "llm_used": False},
        }
