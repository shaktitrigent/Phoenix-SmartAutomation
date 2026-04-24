"""Prompt templates for LLM-based test generation."""

from typing import List, Optional, Tuple


SYSTEM_PROMPT = """\
You are a senior QA automation engineer who generates **complete, executable** \
pytest + Playwright Python test scripts.

## Output Rules
- Return ONLY valid Python source code. No markdown fences, no explanations, no TODOs.
- The script must be immediately runnable with `pytest <file> --headed`.
- Every generated file must start with a module docstring, then imports, then test function(s).

## Imports
Always include these imports at the top:
```
import re
import pytest
from playwright.sync_api import Page, expect
```
Add `import tempfile, os` only when file-upload steps are needed.

## Playwright Conventions
{knowledge_context}

## Locator Priority (follow strictly)
1. `get_by_role` — default for all interactive elements. Always provide `name=`.
2. `get_by_label` — form fields with visible labels.
3. `get_by_placeholder` — inputs without visible labels.
4. `get_by_text` — static text content, use `exact=True` when needed.
5. `get_by_test_id` — when a `data-testid` attribute exists.
6. CSS selector — only when semantic locators are not possible.
7. XPath — absolute last resort.

**Strict-mode collision rule:** if one option is a substring of another (e.g. `Male` vs `Female`),
you MUST use `exact=True` to avoid strict-mode violations.

**Multiple-match rule:** if a locator resolves to multiple elements (common for `Submit`, `Save`, etc.),
you MUST scope to a parent container, use `.filter(...)`, or choose a more specific selector (id/class)
so the locator resolves to exactly one element in strict mode.

## Waiting Rules
- NEVER use `time.sleep()` or `page.wait_for_timeout()` to fix flaky tests.
- Rely on Playwright auto-waiting for actions (.click, .fill, etc.).
- Use `page.wait_for_load_state('networkidle')` only after navigation.
- Use `expect()` assertions for waiting on state changes.

## Dialog Handling
- Never use `page.on("dialog", ...)` (it stacks handlers across multiple dialogs).
- Always use `page.once("dialog", ...)` immediately before the action that triggers the dialog.

## Assertions
- Use `expect(locator)` assertions from `playwright.sync_api`.
- For URL matching use `expect(page).to_have_url(re.compile(r"..."))`.
- Never use bare `assert` with `.text_content()` — use `expect().to_have_text()`.

**No guessing:** Do NOT assert on imagined success messages like \"uploaded successfully\" unless the page snapshot or steps explicitly show that exact text.
Prefer asserting on observable state changes: selected filename appears, dialog handled, new tab opened, etc.

**New tab/window:** If you cannot determine the exact destination URL, assert only that a new page opened and its URL matches `r\"https?://\"`.

## Naming
- Function name: `test_<short_descriptive_name>` using snake_case (max 50 chars).
- Keep function names concise: `test_form_submission`, `test_alert_handling`, etc.

## Test Structure
- Arrange: navigate and set up state.
- Act: perform the user actions described in the acceptance criteria.
- Assert: verify expected outcomes with `expect()`.
"""


def build_test_generation_prompt(
    user_story: str,
    acceptance_criteria: List[str],
    knowledge_context: str,
    page_snapshot: str,
    application_url: Optional[str],
) -> Tuple[str, str]:
    """Build the system and user prompts for test generation.

    Args:
        user_story: The user story text.
        acceptance_criteria: List of acceptance criteria strings.
        knowledge_context: Formatted knowledge base context.
        page_snapshot: Accessibility snapshot of the target page (may be empty).
        application_url: The application URL to test.

    Returns:
        A (system_prompt, user_prompt) tuple.
    """
    system = SYSTEM_PROMPT.format(
        knowledge_context=knowledge_context if knowledge_context else "(no additional context)",
    )

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
        user_parts.extend(
            [
                "",
                "## Page Accessibility Snapshot (live inspection of the target page)",
                "Use the element roles, names, and values below to choose accurate locators.",
                "",
                page_snapshot,
            ]
        )
    else:
        user_parts.extend(
            [
                "",
                "## Page Snapshot",
                "No live page snapshot available. Use your best judgement for locators "
                "based on common web patterns and the acceptance criteria.",
            ]
        )

    user_parts.extend(
        [
            "",
            "## Instructions",
            "- Write ONE test function that covers all acceptance criteria.",
            "- Use the locator priority order defined in the system prompt.",
            "- If the page snapshot contains exact element names/roles, use them directly.",
            "- Include meaningful assertions for each acceptance criterion.",
            "- Return ONLY the Python source code, nothing else.",
        ]
    )

    return system, "\n".join(user_parts)


def build_test_name_prompt(user_story: str) -> Tuple[str, str]:
    """Build a prompt to generate a short, clean test name from a user story.

    Returns:
        A (system_prompt, user_prompt) tuple.
    """
    system = (
        "You are a naming assistant. Given a user story, return ONLY a short snake_case "
        "test name (without the 'test_' prefix). Examples:\n"
        '- "As a user, I want to fill in the form" -> form_submission\n'
        '- "As a user, I want to interact with alerts" -> alert_handling\n'
        '- "As a user, I want to verify the table" -> table_validation\n'
        '- "As a user, I want to upload a file" -> file_upload\n'
        '- "As a user, I want to select a date" -> date_selection\n'
        "Return ONLY the snake_case name, nothing else. Max 40 characters."
    )
    user = user_story
    return system, user
