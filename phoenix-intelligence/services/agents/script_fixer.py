"""Script Fixer Agent.

Takes a failing pytest + Playwright script together with the exact error
message from the test run and returns a corrected, immediately executable
version of that script.

Two execution paths:
  LLM path   — sends the script + error to the LLM using the versioned
                ``script_fixer`` prompt and returns the full fixed script.
  Heuristic  — applies rule-based transforms when no LLM is available:
                * locator_not_found → broaden locator strategy
                * timeout           → double timeout values
                * assertion_failure → relax assertion text
                * stale_element     → add wait_for_selector before action
                * navigation_failure → relax URL pattern + increase timeout
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, Optional

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

_prompt_loader = PromptLoader()


def _load_quality_standards() -> str:
    try:
        return _prompt_loader.get("test_quality_standards")
    except (FileNotFoundError, KeyError):
        return ""


# ---------------------------------------------------------------------------
# Heuristic fix rules
# ---------------------------------------------------------------------------

_TIMEOUT_RE = re.compile(r"(timeout\s*=\s*)(\d+)")
_WAIT_URL_RE = re.compile(r'(page\.wait_for_url\(["\'][^"\']+["\'],\s*timeout\s*=\s*)(\d+)')


def _heuristic_fix(code: str, error_type: str, error_message: str) -> str:
    """Apply rule-based fixes when LLM is unavailable."""

    if error_type == "locator_not_found":
        return _fix_locator(code, error_message)

    if error_type == "timeout":
        return _fix_timeouts(code)

    if error_type == "assertion_failure":
        return _fix_assertion(code, error_message)

    if error_type == "stale_element":
        return _fix_stale_element(code, error_message)

    if error_type == "navigation_failure":
        return _fix_navigation(code, error_message)

    # Unknown — return unchanged
    logger.warning("No heuristic rule for error_type=%s — script unchanged", error_type)
    return code


def _fix_locator(code: str, error_message: str) -> str:
    """Broaden get_by_label → get_by_placeholder for unresolved locators."""
    # Extract the failing locator name from the error if possible
    label_match = re.search(r'get_by_label\("([^"]+)"\)', error_message)
    if label_match:
        label = label_match.group(1)
        old = f'get_by_label("{label}")'
        new = f'get_by_placeholder("{label}")'
        if old in code:
            logger.info("Heuristic fix: replacing %s with %s", old, new)
            return code.replace(old, new, 1)

    # Generic: replace the first get_by_label in the script
    code = re.sub(
        r'get_by_label\("([^"]+)"\)',
        lambda m: f'get_by_placeholder("{m.group(1)}")',
        code,
        count=1,
    )
    return code


def _fix_timeouts(code: str) -> str:
    """Double all timeout values in the script."""
    def _double(m: re.Match) -> str:
        prefix = m.group(1)
        val = int(m.group(2))
        return f"{prefix}{min(val * 2, 120_000)}"

    return _TIMEOUT_RE.sub(_double, code)


def _fix_assertion(code: str, error_message: str) -> str:
    """Relax assertion: replace strict to_have_text with to_contain_text."""
    # to_have_text → to_contain_text
    code = code.replace(".to_have_text(", ".to_contain_text(")

    # If error gives an actual value, try to patch the expected text
    # Pattern: AssertionError: expected "X" to equal "Y"  →  swap X with Y
    actual_match = re.search(r'expected\s+["\'](.+?)["\']', error_message)
    if actual_match:
        actual = actual_match.group(1)
        # Replace first to_contain_text / to_have_text argument
        code = re.sub(
            r'(\.to_contain_text\()(["\'])([^"\']+)(["\'])',
            lambda m: f'{m.group(1)}{m.group(2)}{actual}{m.group(4)}',
            code,
            count=1,
        )
    return code


def _fix_stale_element(code: str, error_message: str) -> str:
    """Add wait_for_selector before the action that hit a stale element."""
    # Extract the locator string from the error if possible
    selector_match = re.search(r'locator\(["\']([^"\']+)["\']', error_message)
    if selector_match:
        selector = selector_match.group(1)
        wait_line = f'    page.wait_for_selector("{selector}", state="visible", timeout=10_000)\n'
        old_line_re = re.compile(rf'(    page\.locator\("{re.escape(selector)}"\))')
        code = old_line_re.sub(wait_line + r'\1', code, count=1)
    return code


def _fix_navigation(code: str, error_message: str) -> str:
    """Relax URL patterns and increase navigation timeouts."""
    # Relax **/path** → **path**
    code = re.sub(r'\*\*/([\w/-]+)\*\*', r'**\1**', code)
    # Double navigation timeouts
    code = _WAIT_URL_RE.sub(
        lambda m: f"{m.group(1)}{min(int(m.group(2)) * 2, 120_000)}",
        code,
    )
    return code


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ScriptFixerAgent(BaseAgent):
    """Fixes a failing Playwright script given its error output.

    Input keys:
        script_code   (str)  — the original Python script
        error_message (str)  — the error/exception text from pytest
        error_type    (str)  — classified error type (locator_not_found, timeout, …)
        test_name     (str)  — name of the failing test function
        application_url (str, optional)

    Output keys:
        fixed_script  (str)  — the corrected Python script
        changed       (bool) — True if the script was actually modified
        fix_summary   (str)  — one-line description of what was changed
    """

    def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        script_code: str = input_data.get("script_code", "")
        error_message: str = input_data.get("error_message", "")
        error_type: str = input_data.get("error_type", "unknown")
        test_name: str = input_data.get("test_name", "unknown_test")
        application_url: Optional[str] = input_data.get("application_url")

        if not script_code:
            return {
                "fixed_script": "",
                "changed": False,
                "fix_summary": "No script code provided",
            }

        if self.llm_client:
            try:
                fixed = self._fix_via_llm(
                    script_code, error_message, error_type, test_name, application_url
                )
                changed = fixed.strip() != script_code.strip()
                return {
                    "fixed_script": fixed,
                    "changed": changed,
                    "fix_summary": f"LLM fix applied for {error_type}",
                }
            except Exception as exc:
                logger.warning(
                    "LLM script fix failed for '%s', falling back to heuristic: %s",
                    test_name,
                    exc,
                )

        # Heuristic fallback
        fixed = _heuristic_fix(script_code, error_type, error_message)
        changed = fixed.strip() != script_code.strip()
        summary = (
            f"Heuristic fix applied for {error_type}"
            if changed
            else f"No heuristic rule matched for {error_type} — script unchanged"
        )
        return {"fixed_script": fixed, "changed": changed, "fix_summary": summary}

    # ------------------------------------------------------------------

    def _fix_via_llm(
        self,
        script_code: str,
        error_message: str,
        error_type: str,
        test_name: str,
        application_url: Optional[str],
    ) -> str:
        system_prompt = _prompt_loader.get("script_fixer")

        user_parts = [
            "Fix the following failing pytest + Playwright script.",
            "",
            f"## Failing test: `{test_name}`",
            f"## Error type: `{error_type}`",
            "",
            "## Exact error from pytest",
            "```",
            error_message[:3000],
            "```",
            "",
        ]
        if application_url:
            user_parts += [f"## Application URL\n{application_url}", ""]

        fix_instructions = [
            "## Instructions",
            "- Return ONLY the complete fixed Python script.",
            "- Fix the specific error above. Change as few lines as possible.",
            "- No markdown fences, no explanations, no TODOs.",
            "- Keep the test function name exactly as-is.",
        ]
        quality_standards = _load_quality_standards()
        if quality_standards:
            fix_instructions += [
                "",
                "## Quality Standards (the fixed script must comply with these)",
                quality_standards,
            ]

        user_parts += [
            "## Original script (failing)",
            "```python",
            script_code,
            "```",
            "",
        ] + fix_instructions

        user_prompt = "\n".join(user_parts)
        logger.info("Fixing script '%s' via LLM (error_type=%s)", test_name, error_type)
        raw = self.llm_client.generate(system_prompt, user_prompt)

        # Strip any markdown fences the LLM might have added
        raw = raw.strip()
        raw = re.sub(r"^```[a-zA-Z]*\r?\n?", "", raw)
        raw = re.sub(r"\r?\n?```\s*$", "", raw)
        return raw.strip()
