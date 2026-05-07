"""Test generation agent - uses LLM + Knowledge Base + MCP for real code generation."""

import json
import logging
import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap around Python scripts."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _safe_py_str(value: str) -> str:
    """Escape a value so it is safe to embed inside a Python double-quoted string literal.

    Handles:
    - Unicode smart/curly quotes (“ ” ‘ ’) → replaced with ASCII equivalents
    - Backslashes → escaped
    - ASCII double quotes → escaped
    """
    # Normalise Unicode quotation marks to ASCII before escaping
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("‘", "'").replace("’", "'")
    # Escape backslashes first, then double quotes
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return value


# ---------------------------------------------------------------------------
# Control taxonomy (RC-02)
# ---------------------------------------------------------------------------


class ControlType(Enum):
    TEXT_INPUT = "text_input"
    PASSWORD_INPUT = "password_input"
    EMAIL_INPUT = "email_input"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    SELECT_DROPDOWN = "select_dropdown"
    FILE_INPUT = "file_input"
    NUMBER_INPUT = "number_input"
    BUTTON = "button"
    LINK = "link"
    BROWSER_ALERT = "browser_alert"
    BROWSER_CONFIRM = "browser_confirm"
    BROWSER_PROMPT = "browser_prompt"
    HOVER_TARGET = "hover_target"
    DRAG_DROP = "drag_drop"
    MULTI_TAB = "multi_tab"
    DYNAMIC_CONTENT = "dynamic_content"
    FORM_SUBMIT = "form_submit"
    NAVIGATE = "navigate"
    ASSERTION = "assertion"
    WAIT = "wait"
    UNKNOWN = "unknown"


def _classify_control(criterion: str, application_url: Optional[str] = None) -> ControlType:
    """Determine ControlType from criterion text and optional URL."""
    lower = criterion.lower()
    url_lower = (application_url or "").lower()

    # URL-based hints
    if ("/checkboxes" in url_lower or "checkbox" in url_lower) and any(
        k in lower for k in ["check", "tick", "uncheck", "untick"]
    ):
        return ControlType.CHECKBOX
    if "/dropdown" in url_lower and any(
        k in lower for k in ["select", "choose", "pick", "option"]
    ):
        return ControlType.SELECT_DROPDOWN
    if "/upload" in url_lower and any(k in lower for k in ["upload", "attach", "file"]):
        return ControlType.FILE_INPUT
    if ("/javascript_alerts" in url_lower or "/alerts" in url_lower) and any(
        k in lower for k in ["alert", "dialog", "confirm", "prompt", "dismiss", "accept"]
    ):
        if "confirm" in lower:
            return ControlType.BROWSER_CONFIRM
        if "prompt" in lower:
            return ControlType.BROWSER_PROMPT
        return ControlType.BROWSER_ALERT
    if ("/drag_and_drop" in url_lower or "/drag" in url_lower) and any(
        k in lower for k in ["drag", "drop"]
    ):
        return ControlType.DRAG_DROP
    if ("/hovers" in url_lower or "/hover" in url_lower) and any(
        k in lower for k in ["hover", "mouse over"]
    ):
        return ControlType.HOVER_TARGET

    # Keyword-based classification
    if any(k in lower for k in ["navigate", "go to", "open", "visit"]):
        return ControlType.NAVIGATE
    if any(
        k in lower for k in ["verify", "assert", "check that", "should", "confirm that", "ensure"]
    ):
        return ControlType.ASSERTION
    if any(k in lower for k in ["wait for", "loading", "wait until"]):
        return ControlType.WAIT
    if "drag" in lower:
        return ControlType.DRAG_DROP
    if any(k in lower for k in ["hover", "mouse over"]):
        return ControlType.HOVER_TARGET
    if any(k in lower for k in ["upload", "attach"]) and any(
        k in lower for k in ["file", "document"]
    ):
        return ControlType.FILE_INPUT
    if any(k in lower for k in ["dismiss", "accept", "ok"]) and any(
        k in lower for k in ["alert", "dialog", "popup"]
    ):
        if "confirm" in lower:
            return ControlType.BROWSER_CONFIRM
        return ControlType.BROWSER_ALERT
    if "alert" in lower or "dialog" in lower:
        return ControlType.BROWSER_ALERT
    if any(k in lower for k in ["uncheck", "untick"]):
        return ControlType.CHECKBOX
    if any(k in lower for k in ["check", "tick"]) and any(k in lower for k in ["checkbox", "box"]):
        return ControlType.CHECKBOX
    if any(k in lower for k in ["select", "choose", "pick"]) and any(
        k in lower for k in ["dropdown", "option", "combobox", "list"]
    ):
        return ControlType.SELECT_DROPDOWN
    if any(k in lower for k in ["select", "choose", "pick"]) and "option" in lower:
        return ControlType.SELECT_DROPDOWN
    if "password" in lower and any(k in lower for k in ["enter", "type", "fill", "input"]):
        return ControlType.PASSWORD_INPUT
    if "email" in lower and any(k in lower for k in ["enter", "type", "fill", "input"]):
        return ControlType.EMAIL_INPUT
    if any(k in lower for k in ["enter", "type", "fill", "input"]):
        return ControlType.TEXT_INPUT
    if any(k in lower for k in ["submit", "click submit", "press submit"]):
        return ControlType.FORM_SUBMIT
    if any(k in lower for k in ["click", "press", "tap"]) and "link" in lower:
        return ControlType.LINK
    if any(k in lower for k in ["click", "press", "tap", "button"]):
        return ControlType.BUTTON
    return ControlType.UNKNOWN


def _extract_quoted_value(text: str) -> Optional[str]:
    """Return the first quoted string found in text."""
    m = re.search(r'["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _extract_fill_target_and_value(criterion: str) -> Tuple[str, str]:
    """Extract (field_label, fill_value) from fill-type criteria."""
    # Pattern: action + field + value  e.g. "Enter username tomsmith"
    # Try quoted value first
    quoted = _extract_quoted_value(criterion)

    # Remove action keyword at start
    cleaned = re.sub(
        r"^(?:enter|type|fill|input|provide)\s+",
        "",
        criterion.strip(),
        flags=re.IGNORECASE,
    )

    # "in the X field" or "into the X field" → extract field from that
    field_match = re.search(
        r"(?:in|into|for)\s+(?:the\s+)?['\"]?([a-zA-Z\s]+?)['\"]?\s+(?:field|input|box|area)",
        criterion,
        re.IGNORECASE,
    )
    if field_match:
        field = field_match.group(1).strip()
        value = (
            quoted or re.sub(r"\s+(?:in|into|for)\s+.*$", "", cleaned, flags=re.IGNORECASE).strip()
        )
        return field.title(), value

    # "with value X" / "as X" / "= X"
    with_match = re.search(r"(?:with|as|value|=)\s+['\"]?([^'\"]+)['\"]?", cleaned, re.IGNORECASE)
    if with_match:
        value = with_match.group(1).strip()
        field = re.sub(r"\s+(?:with|as|value|=).*$", "", cleaned, flags=re.IGNORECASE).strip()
        return field.title(), value

    # e.g. "username tomsmith" → first token = field, rest = value
    parts = cleaned.split(None, 1)
    if len(parts) == 2:
        return parts[0].title(), quoted or parts[1]
    if len(parts) == 1:
        return parts[0].title(), quoted or "value"

    return "Field", quoted or "value"


def _extract_click_target(criterion: str) -> Tuple[str, str]:
    """Return (role_hint, label) for click-type criteria.  role_hint ∈ {'button','link','text'}"""
    lower = criterion.lower()
    cleaned = re.sub(
        r"^(?:click|press|tap|submit)\s+(?:the\s+|on\s+(?:the\s+)?)?",
        "",
        criterion.strip(),
        flags=re.IGNORECASE,
    )
    quoted = _extract_quoted_value(criterion) or cleaned

    if "button" in lower:
        label = re.sub(r"\s+button.*$", "", cleaned, flags=re.IGNORECASE).strip()
        return "button", label or quoted
    if "link" in lower:
        label = re.sub(r"\s+link.*$", "", cleaned, flags=re.IGNORECASE).strip()
        return "link", label or quoted
    return "text", quoted


def _extract_select_option(criterion: str) -> Tuple[str, str]:
    """Return (field_label, option_value) for select-type criteria."""
    # "Select Option 1 from dropdown"
    from_match = re.search(r"(.+?)\s+from\s+(?:the\s+)?(.+)", criterion, re.IGNORECASE)
    if from_match:
        option = from_match.group(1)
        option = re.sub(r"^(?:select|choose|pick)\s+", "", option, flags=re.IGNORECASE).strip()
        field = from_match.group(2).strip().title()
        return field, option

    # "Select X" with no context
    cleaned = re.sub(r"^(?:select|choose|pick)\s+", "", criterion.strip(), flags=re.IGNORECASE)
    quoted = _extract_quoted_value(criterion)
    return "Dropdown", quoted or cleaned


def _extract_assertion_subject(criterion: str) -> str:
    """Extract what should be visible/true from assertion criteria."""
    lower = criterion.lower()
    # Remove assertion keyword
    cleaned = re.sub(
        r"^(?:verify|assert|check that|should|confirm that|ensure|validate)\s+(?:that\s+|the\s+)?",
        "",
        criterion.strip(),
        flags=re.IGNORECASE,
    )
    quoted = _extract_quoted_value(criterion)
    if quoted:
        return quoted
    # "the Secure Area page is shown" → "Secure Area"
    title_match = re.search(r"the\s+(.+?)\s+(?:page|section|area|screen)", cleaned, re.IGNORECASE)
    if title_match:
        return title_match.group(1).strip()
    # "URL contains /secure" → /secure
    url_match = re.search(r"url\s+(?:contains|includes|is|=)\s+['\"]?([^\s'\"]+)", lower)
    if url_match:
        return url_match.group(1).strip()
    return cleaned[:60]


def _criterion_to_playwright_lines(
    criterion: str,
    step_num: int,
    application_url: Optional[str] = None,
) -> List[str]:
    """Map a single acceptance criterion → list of indented Playwright code lines."""
    control = _classify_control(criterion, application_url)
    lower = criterion.lower()
    lines: List[str] = [f"    # Step {step_num}: {criterion}"]

    if control == ControlType.NAVIGATE:
        url = _extract_quoted_value(criterion) or application_url or "https://example.com"
        lines += [
            f'    page.goto("{url}")',
            '    page.wait_for_load_state("networkidle")',
        ]

    elif control == ControlType.TEXT_INPUT:
        field, value = _extract_fill_target_and_value(criterion)
        lines.append(f'    page.get_by_label("{_safe_py_str(field)}").fill("{_safe_py_str(value)}")')

    elif control == ControlType.PASSWORD_INPUT:
        _, value = _extract_fill_target_and_value(criterion)
        lines.append(f'    page.get_by_label("Password").fill("{_safe_py_str(value)}")')

    elif control == ControlType.EMAIL_INPUT:
        _, value = _extract_fill_target_and_value(criterion)
        lines.append(f'    page.get_by_label("Email").fill("{_safe_py_str(value)}")')

    elif control == ControlType.CHECKBOX:
        if any(k in lower for k in ["uncheck", "untick"]):
            # "Uncheck checkbox 2" → nth(1)
            num_match = re.search(r"\d+", criterion)
            idx = int(num_match.group()) - 1 if num_match else 0
            lines.append(f"    page.locator(\"input[type='checkbox']\").nth({idx}).uncheck()")
        else:
            # "Check checkbox 1"
            num_match = re.search(r"\d+", criterion)
            idx = int(num_match.group()) - 1 if num_match else 0
            label_match = re.search(r'the\s+["\']?(.+?)["\']?\s+checkbox', criterion, re.IGNORECASE)
            if label_match:
                label = label_match.group(1).strip()
                lines.append(f'    page.get_by_label("{_safe_py_str(label)}").check()')
            else:
                lines.append(f"    page.locator(\"input[type='checkbox']\").nth({idx}).check()")

    elif control == ControlType.RADIO_BUTTON:
        field, _ = _extract_fill_target_and_value(criterion)
        lines.append(f'    page.get_by_label("{_safe_py_str(field)}").check()')

    elif control == ControlType.SELECT_DROPDOWN:
        field, option = _extract_select_option(criterion)
        lines.append(f'    page.get_by_label("{_safe_py_str(field)}").select_option("{_safe_py_str(option)}")')

    elif control == ControlType.FILE_INPUT:
        lines.append("    page.locator('input[type=\"file\"]').set_input_files('test_file.txt')")

    elif control == ControlType.BUTTON:
        role, label = _extract_click_target(criterion)
        if role == "button":
            lines.append(f'    page.get_by_role("button", name="{_safe_py_str(label)}").click()')
        else:
            lines.append(f'    page.get_by_text("{_safe_py_str(label)}").first.click()')

    elif control == ControlType.LINK:
        _, label = _extract_click_target(criterion)
        lines.append(f'    page.get_by_role("link", name="{_safe_py_str(label)}").click()')

    elif control == ControlType.FORM_SUBMIT:
        lines.append('    page.get_by_role("button", name="Submit").click()')

    elif control == ControlType.BROWSER_ALERT:
        if "dismiss" in lower:
            lines += [
                '    page.on("dialog", lambda dialog: dialog.dismiss())',
                "    # Trigger the alert",
                '    page.get_by_role("button").first.click()',
            ]
        else:
            lines += [
                '    page.on("dialog", lambda dialog: dialog.accept())',
                "    # Trigger the alert",
                '    page.get_by_role("button").first.click()',
            ]

    elif control == ControlType.BROWSER_CONFIRM:
        if "dismiss" in lower or "cancel" in lower:
            lines.append('    page.on("dialog", lambda dialog: dialog.dismiss())')
        else:
            lines.append('    page.on("dialog", lambda dialog: dialog.accept())')

    elif control == ControlType.BROWSER_PROMPT:
        prompt_val = _extract_quoted_value(criterion) or "response text"
        lines.append(f'    page.on("dialog", lambda dialog: dialog.accept("{_safe_py_str(prompt_val)}"))')

    elif control == ControlType.HOVER_TARGET:
        cleaned = re.sub(
            r"^(?:hover|mouse over)\s+(?:over\s+)?(?:the\s+)?", "", criterion, flags=re.IGNORECASE
        ).strip()
        target = _extract_quoted_value(criterion) or cleaned or "element"
        lines.append(f'    page.get_by_text("{_safe_py_str(target)}").hover()')

    elif control == ControlType.DRAG_DROP:
        lines += [
            "    source = page.locator('#column-a')",
            "    target = page.locator('#column-b')",
            "    source.drag_to(target)",
        ]

    elif control == ControlType.ASSERTION:
        subject = _extract_assertion_subject(criterion)
        if any(k in lower for k in ["url", "navigate", "redirect", "page contains /", "page is"]):
            url_frag = re.search(r"[/][\w/-]+", subject)
            if url_frag:
                lines.append(
                    f'    expect(page).to_have_url(re.compile(r".*{re.escape(url_frag.group())}.*"))'
                )
            else:
                lines.append(
                    f'    expect(page).to_have_url(re.compile(r".*{re.escape(subject)}.*"))'
                )
        elif "title" in lower:
            lines.append(f'    expect(page).to_have_title(re.compile(r".*{re.escape(subject)}.*"))')
        else:
            lines.append(f'    expect(page.get_by_text("{_safe_py_str(subject)}").first).to_be_visible()')

    elif control == ControlType.WAIT:
        lines.append('    page.wait_for_load_state("networkidle")')

    else:
        # Truly unrecognized — emit comment + warning
        logger.warning(
            "Criterion not recognized for heuristic mapping, using comment: %s", criterion
        )
        lines.append(
            f"    # WARNING: Criterion not mapped — add Playwright action here: {criterion}"
        )

    lines.append("")
    return lines


def _derive_expected_result(criterion: str) -> str:
    """Derive a specific expected result string for a manual test step (RC-03).

    Never returns the generic placeholder 'Step completes as expected'.
    """
    lower = criterion.lower()

    # Assertion / verification criteria — the criterion IS the expected result
    if any(
        k in lower
        for k in ["verify", "assert", "check that", "should", "confirm that", "ensure", "validate"]
    ):
        cleaned = re.sub(
            r"^(?:verify|assert|check that|should|confirm that|ensure|validate)\s+(?:that\s+|the\s+)?",
            "",
            criterion.strip(),
            flags=re.IGNORECASE,
        )
        return cleaned.capitalize() if cleaned else criterion

    # Fill / input actions
    if any(k in lower for k in ["enter", "type", "fill", "input", "provide"]):
        field, value = _extract_fill_target_and_value(criterion)
        return f'"{field}" field contains the value "{value}"'

    # Click / button actions
    if any(k in lower for k in ["click", "press", "tap"]):
        _, label = _extract_click_target(criterion)
        if "button" in lower or "submit" in lower:
            return f'"{label}" button is clicked and the action is triggered'
        if "link" in lower:
            return f'Clicking "{label}" navigates to the linked page'
        return f'"{label}" element responds to the click interaction'

    # Select / dropdown
    if any(k in lower for k in ["select", "choose", "pick"]):
        field, option = _extract_select_option(criterion)
        return f'"{option}" is shown as the selected value in the "{field}" control'

    # Checkbox
    if any(k in lower for k in ["check", "tick"]) and "checkbox" in lower:
        return "Checkbox is checked (contains a tick/checkmark)"
    if any(k in lower for k in ["uncheck", "untick"]):
        return "Checkbox is unchecked (tick/checkmark is removed)"

    # File upload
    if any(k in lower for k in ["upload", "attach"]):
        return "File is attached and its filename appears in the upload control"

    # Alert / dialog
    if any(k in lower for k in ["alert", "dialog", "confirm", "prompt"]):
        if "dismiss" in lower or "cancel" in lower:
            return "Dialog/alert is dismissed and the page returns to its previous state"
        return "Dialog/alert is accepted and the page responds accordingly"

    # Navigation
    if any(k in lower for k in ["navigate", "go to", "open", "visit"]):
        url = _extract_quoted_value(criterion) or "the target URL"
        return f"Page loads at {url} with visible content and no error messages"

    # Hover
    if any(k in lower for k in ["hover", "mouse over"]):
        return "Hover tooltip or visual change is displayed for the target element"

    # Drag & drop
    if "drag" in lower:
        return "Source element is moved to the target drop zone"

    # Wait / loading
    if any(k in lower for k in ["wait", "loading"]):
        return "Page or element finishes loading and becomes interactive"

    # Unknown — flag for manual review
    return f"[NEEDS MANUAL REVIEW] Expected outcome after: {criterion}"


def _derive_overall_expected_result(criteria: List[str], user_story: str) -> str:
    """Synthesise a final overall expected result from all criteria (RC-03)."""
    # Look for explicit assertion criteria to use as the final outcome
    assertion_keywords = ("verify", "assert", "check that", "should", "confirm that", "ensure")
    assertions = [c for c in criteria if any(c.lower().startswith(k) for k in assertion_keywords)]
    if assertions:
        subjects = [
            re.sub(
                r"^(?:verify|assert|check that|should|confirm that|ensure)\s+(?:that\s+)?",
                "",
                a,
                flags=re.IGNORECASE,
            ).strip()
            for a in assertions
        ]
        return "All assertions pass: " + "; ".join(subjects)

    # Derive from story text
    story_clean = re.sub(
        r"^(?:as a [^,]+,?\s*)?(?:i want to|i should be able to)\s+",
        "",
        user_story,
        flags=re.IGNORECASE,
    ).strip()
    return (
        f"User successfully {story_clean}"
        if story_clean
        else "All acceptance criteria are satisfied"
    )


_prompt_loader = PromptLoader()


class TestGeneratorAgent(BaseAgent):
    """Agent specialised in generating test cases from user stories.

    Flow (automation):
        1. Load knowledge context from the Knowledge Base.
        2. Inspect the target page via Playwright MCP (accessibility snapshot).
        3. Build prompt from versioned prompt file (prompts/test_generator/1.0.md).
        4. Call LLM -> returns complete Playwright script code.

    Flow (manual):
        1. Build prompt from versioned prompt file (prompts/manual_test_generator/1.0.md).
        2. Call LLM -> returns JSON array of structured test cases.
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
    # Manual tests - LLM-powered structured output
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

        knowledge_context = self.get_knowledge_context(query=user_story)
        if knowledge_context:
            user_prompt += f"\n\n## Additional Context (Knowledge Base)\n{knowledge_context[:1500]}"

        logger.info("Generating manual tests via LLM for: %s", user_story[:80])
        raw = self.llm_client.generate(system_prompt, user_prompt)
        tests = self._parse_json_array(raw)

        if not tests:
            raise ValueError("LLM returned empty or unparseable manual test JSON")

        normalised = []
        for idx, test in enumerate(tests, 1):
            normalised.append(
                {
                    "name": test.get("name", f"TC-{idx:03d}: {user_story[:50]}"),
                    "description": test.get("description", user_story),
                    "risk_level": test.get("risk_level", risk_level or "regression"),
                    "preconditions": test.get("preconditions", ""),
                    "steps": self._normalise_steps(test.get("steps", [])),
                    "expected_result": test.get("expected_result", ""),
                    "postconditions": test.get("postconditions", ""),
                    "tags": test.get("tags", ["manual", "generated"]),
                }
            )

        logger.info("LLM generated %d manual test(s)", len(normalised))
        return normalised

    def _generate_manual_tests_fallback(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Heuristic fallback when LLM is unavailable.

        Derives specific expected results for each step (RC-03) rather than
        emitting the generic placeholder 'Step completes as expected'.
        """
        steps = []
        if application_url:
            steps.append(
                {
                    "step_number": 1,
                    "action": f"Navigate to {application_url}",
                    "expected_result": (
                        f"Page at {application_url} loads successfully "
                        "with visible content and no error messages"
                    ),
                }
            )
        for criterion in acceptance_criteria:
            steps.append(
                {
                    "step_number": len(steps) + 1,
                    "action": criterion,
                    "expected_result": _derive_expected_result(criterion),
                }
            )

        test_name = self._derive_short_name(user_story)
        overall_result = _derive_overall_expected_result(acceptance_criteria, user_story)
        return [
            {
                "name": f"TC-001: {test_name.replace('_', ' ').title()}",
                "description": user_story,
                "risk_level": risk_level or "regression",
                "preconditions": "User has access to the application",
                "steps": steps,
                "expected_result": overall_result,
                "postconditions": "",
                "tags": ["manual", "generated"],
            }
        ]

    # ------------------------------------------------------------------
    # Automation tests - LLM + MCP powered
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
                "LLM client is not configured. Set PHOENIX_LLM_PROVIDER and the matching API key, then restart the server."
            )

        try:
            page_snapshot = ""
            if self.mcp_client and application_url:
                logger.info("Inspecting page via MCP: %s", application_url)
                page_snapshot = self.mcp_client.inspect_page(application_url)
                if page_snapshot:
                    logger.info("MCP snapshot received (%d chars)", len(page_snapshot))
                else:
                    logger.warning("MCP returned empty snapshot for %s", application_url)

            system_prompt_template = _prompt_loader.get("test_generator")
            system_prompt = system_prompt_template.format(
                knowledge_context=knowledge_context
                if knowledge_context
                else "(no additional context)"
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

            logger.info("Generating automation script via LLM for: %s", user_story[:80])
            raw = self.llm_client.generate(system_prompt, user_prompt)
            script_code = _strip_code_fences(raw)
        except Exception as exc:
            logger.warning(
                "LLM automation generation failed, using fallback script: %s",
                exc,
                exc_info=True,
            )
            script_code = self._build_automation_fallback_script(
                user_story=user_story,
                application_url=application_url,
                acceptance_criteria=acceptance_criteria,
            )

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

    def _build_automation_fallback_script(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
    ) -> str:
        """Build a heuristic Playwright test from acceptance criteria when LLM fails.

        Uses the criteria-to-action mapping layer (RC-01 / RC-02) to emit real
        Playwright interactions rather than comment-only stubs.
        """
        logger.warning(
            "⚠  LLM generation failed — building heuristic script from acceptance criteria. "
            "Set ANTHROPIC_API_KEY (or OPENAI_API_KEY / GOOGLE_API_KEY) for real generation."
        )
        url = application_url or "https://example.com"

        body_lines: List[str] = [
            "    # Navigate to target URL",
            f'    page.goto("{url}")',
            '    page.wait_for_load_state("networkidle")',
            "",
        ]

        for idx, criterion in enumerate(acceptance_criteria, 1):
            body_lines.extend(_criterion_to_playwright_lines(criterion, idx, application_url))

        body = "\n".join(body_lines)

        return (
            "# WARNING: This is heuristic fallback output — LLM generation failed.\n"
            "# Set ANTHROPIC_API_KEY (or OPENAI_API_KEY / GOOGLE_API_KEY) for LLM-powered scripts.\n"
            "import re\n"
            "import pytest\n"
            "from playwright.sync_api import Page, expect\n"
            "\n"
            "\n"
            "def test_generated_automation_flow(page: Page):\n"
            f'    """Heuristic fallback script for: {user_story.replace(chr(34), chr(39))}"""\n'
            f"{body}\n"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _derive_short_name(self, user_story: str) -> str:
        """Derive a short snake_case name - LLM first, heuristic fallback."""
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
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return []

    @staticmethod
    def _normalise_steps(steps: Any) -> List[Dict[str, Any]]:
        """Normalise steps - accept list-of-dicts or list-of-strings."""
        if not steps:
            return []
        normalised = []
        for idx, step in enumerate(steps, 1):
            if isinstance(step, dict):
                normalised.append(
                    {
                        "step_number": step.get("step_number", idx),
                        "action": step.get("action", str(step)),
                        "expected_result": step.get("expected_result", ""),
                        "test_data": step.get("test_data", ""),
                    }
                )
            else:
                normalised.append(
                    {
                        "step_number": idx,
                        "action": str(step),
                        "expected_result": "",
                        "test_data": "",
                    }
                )
        return normalised
