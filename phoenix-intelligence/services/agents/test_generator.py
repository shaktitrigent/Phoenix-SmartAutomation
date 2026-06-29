"""Test generation agent - uses LLM + Knowledge Base + MCP for real code generation."""

import ast
import json
import logging
import re
import textwrap
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from services.agents.base import BaseAgent
from services.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


def _safe_substitute(template: str, **kwargs: str) -> str:
    """Replace only the explicitly named ``{key}`` placeholders in *template*.

    Unlike ``str.format()``, this never raises ``KeyError`` or ``ValueError``
    for unknown placeholders — JSON literals, f-string examples, and other
    ``{...}`` patterns in prompt markdown are left unchanged.
    """
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", value)
    return template


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap around Python scripts.

    Handles the common LLM pattern of appending prose after the closing fence
    (e.g. "```\\nNote: remember to set APP_URL…") by extracting only the content
    between the first opening and first closing fence.
    """
    text = text.strip()
    # Greedy extraction: pull the body from the first ``` block even when there
    # is trailing text after the closing fence.
    fence_match = re.search(r"^```[a-zA-Z]*\r?\n(.*?)```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    # Fallback for bare fences at start/end only
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _parse_structured_v2_output(
    raw: str,
) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Parse the v2.0 structured response into (script, locators, recommendations).

    Expects three sections delimited by '### SCRIPT', '### LOCATORS',
    '### RECOMMENDATIONS' (in that order).  Falls back gracefully when the
    LLM omits a section or returns plain Python (v1.0-style response).
    """
    # Check whether the response uses the new structured format
    if "### SCRIPT" not in raw and "### LOCATORS" not in raw:
        # Plain script returned (v1.0-style fallback from the LLM)
        return _strip_code_fences(raw), [], []

    script = ""
    locators: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    # Split on section headers — result is ['prefix', 'SCRIPT', body, 'LOCATORS', body, ...]
    parts = re.split(r"^###\s+(SCRIPT|LOCATORS|RECOMMENDATIONS)\s*$", raw, flags=re.MULTILINE)
    section_map: Dict[str, str] = {}
    it = iter(parts)
    next(it, None)  # discard preamble before first header
    for header in it:
        body = next(it, "")
        section_map[header.strip().upper()] = body.strip()

    if "SCRIPT" in section_map:
        script = _strip_code_fences(section_map["SCRIPT"])

    if "LOCATORS" in section_map:
        raw_json = _strip_code_fences(section_map["LOCATORS"])
        if raw_json and raw_json != "[]":
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    locators = parsed
            except (json.JSONDecodeError, ValueError):
                logger.debug("Could not parse LOCATORS section as JSON: %s", raw_json[:200])

    if "RECOMMENDATIONS" in section_map:
        rec_text = section_map["RECOMMENDATIONS"].strip()
        if rec_text and rec_text.lower() != "none.":
            recommendations = [
                line.lstrip("-•* ").strip()
                for line in rec_text.splitlines()
                if line.strip() and line.strip().lower() != "none."
            ]

    return script, locators, recommendations


def _safe_py_str(value: str) -> str:
    """Escape a value so it is safe to embed inside a Python double-quoted string literal.

    Handles:
    - Unicode smart/curly quotes (" " ' ') → replaced with ASCII equivalents
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
    LOGIN = "login"                 # navigate + fill credentials + click login button
    LOGIN_CREDENTIALS = "login_credentials"  # "login using valid Admin credentials" (no URL)
    NAVIGATE = "navigate"
    MENU_CLICK = "menu_click"       # click a top-level nav menu item
    DATE_PICKER_FUTURE = "date_picker_future"  # "select a future date" / date picker
    DATE_PICKER_PAST = "date_picker_past"      # "select a past date" / date picker
    ASSERTION = "assertion"
    WAIT = "wait"
    UNKNOWN = "unknown"


_LOGIN_URL_RE = re.compile(r'https?://\S+')
_LOGIN_USER_RE = re.compile(r"[Uu]sername\s*['\"]?([\w@.+-]+)['\"]?")
_LOGIN_PASS_RE = re.compile(r"[Pp]assword\s*['\"]?([\w@.!#$%^&*()-]+)['\"]?")
_MANUAL_REVIEW_WARNING = "Manual locator review required"
_PLACEHOLDER_ASSERTION_RE = re.compile(
    r"\b(loads?\s+successfully|fields?\s+are\s+visible|appears?\b|is\s+visible\b|success\s+message)\b",
    re.IGNORECASE,
)


def _manual_review_warning_line(reason: str, criterion: Optional[str] = None) -> str:
    suffix = f" - {reason}" if reason else ""
    if criterion:
        suffix = f"{suffix} [{criterion}]"
    return f"    # WARNING: {_MANUAL_REVIEW_WARNING}{suffix}".rstrip()


def _looks_like_placeholder_assertion(text: str) -> bool:
    return bool(_PLACEHOLDER_ASSERTION_RE.search(text))


def _classify_control(criterion: str, application_url: Optional[str] = None) -> ControlType:
    """Determine ControlType from criterion text and optional URL."""
    lower = criterion.lower()
    url_lower = (application_url or "").lower()

    # LOGIN: "Navigate to <url> and log in with Username X and Password Y"
    if (
        any(k in lower for k in ["navigate", "go to", "open", "visit"])
        and any(k in lower for k in ["log in", "login", "sign in"])
        and any(k in lower for k in ["username", "password"])
    ):
        return ControlType.LOGIN

    # LOGIN_CREDENTIALS: "Login using valid Admin credentials" — no URL or username/password literal
    if re.search(
        r"(log\s*in|login|sign\s*in)\s+using\s+(valid\s+)?\w+\s+(admin\s+|user\s+)?credentials",
        lower,
    ) or re.search(
        r"(log\s*in|login|sign\s*in)\s+(as|with)\s+(admin|valid|user)",
        lower,
    ):
        return ControlType.LOGIN_CREDENTIALS

    # DATE_PICKER_FUTURE: "select a future From Date" / "choose a future date"
    if re.search(r"(select|choose|pick)\s+(a\s+)?future\s+.*date", lower) or re.search(
        r"(select|choose|pick)\s+.*date.*\s+(in\s+the\s+)?future", lower
    ):
        return ControlType.DATE_PICKER_FUTURE

    # DATE_PICKER_PAST: "select past leave date" / "select a past date"
    if re.search(r"(select|choose|pick)\s+(a\s+)?past\s+.*date", lower) or re.search(
        r"(select|choose|pick)\s+.*past.*date", lower
    ):
        return ControlType.DATE_PICKER_PAST

    # Generic date picker: "select from date" / "select to date" / "select leave date"
    if re.search(r"(select|choose|pick)\s+(from|to|leave|start|end)\s+date", lower):
        return ControlType.DATE_PICKER_FUTURE

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

    # MENU_CLICK: "Click X in the navigation menu" / "Click X menu"
    if any(k in lower for k in ["click", "press", "tap"]) and any(
        k in lower for k in ["menu", "navigation", "nav", "sidebar", "submenu"]
    ):
        return ControlType.MENU_CLICK

    # Keyword-based classification
    if any(k in lower for k in ["navigate", "go to", "open", "visit"]):
        return ControlType.NAVIGATE
    if any(
        k in lower
        for k in ["verify", "assert", "check that", "should", "confirm that", "ensure"]
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

    if control == ControlType.LOGIN:
        # Extract URL, username, password from step text
        url_match = _LOGIN_URL_RE.search(criterion)
        url = url_match.group(0).rstrip(".,)") if url_match else (application_url or "https://example.com")
        user_match = _LOGIN_USER_RE.search(criterion)
        username_val = user_match.group(1).strip().strip("'\"") if user_match else None
        pass_match = _LOGIN_PASS_RE.search(criterion)
        password_val = pass_match.group(1).strip().strip("'\"") if pass_match else None
        username_expr = f'"{_safe_py_str(username_val)}"' if username_val else 'os.environ["TEST_USERNAME"]'
        password_expr = f'"{_safe_py_str(password_val)}"' if password_val else 'os.environ["TEST_PASSWORD"]'
        lines += [
            f'    page.goto("{_safe_py_str(url)}", timeout=NAVIGATION_TIMEOUT_MS)',
            f'    fill_ready(page, page.locator("input[name=\'username\']"), {username_expr}, "Username input")',
            f'    fill_ready(page, page.locator("input[name=\'password\']"), {password_expr}, "Password input")',
            '    click_ready(page, page.get_by_role("button", name="Login", exact=True), "Login button")',
            '    expect(page).to_have_url(re.compile(r".*/dashboard.*"), timeout=NAVIGATION_TIMEOUT_MS)',
        ]

    elif control == ControlType.MENU_CLICK:
        # Extract the menu item label — strip "Click [the] X in/from the [navigation] menu/nav/sidebar/submenu"
        cleaned = re.sub(
            r"^(?:click|press|tap)\s+(?:the\s+|on\s+(?:the\s+)?)?",
            "",
            criterion.strip(),
            flags=re.IGNORECASE,
        )
        # Remove trailing "in the X menu" / "in the X submenu" / "menu item" etc.
        label = re.sub(
            r"\s+(?:in|from|on)\s+(?:the\s+)?(?:\w+\s+)?(?:navigation\s+|nav\s+)?(?:menu|nav|sidebar|submenu)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip().strip("'\"")
        # Prefer quoted value if present
        label = _extract_quoted_value(criterion) or label
        lines += [
            f'    click_ready(page, page.get_by_role("link", name="{_safe_py_str(label)}", exact=True), "{_safe_py_str(label)} navigation link")',
            f'    expect(page.get_by_role("link", name="{_safe_py_str(label)}", exact=True)).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)',
        ]

    elif control == ControlType.NAVIGATE:
        url = _extract_quoted_value(criterion) or application_url or "https://example.com"
        lines += [
            f'    page.goto("{_safe_py_str(url)}", timeout=NAVIGATION_TIMEOUT_MS)',
            '    expect(page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)',
        ]

    elif control == ControlType.TEXT_INPUT:
        field, value = _extract_fill_target_and_value(criterion)
        lines.append(
            f'    fill_ready(page, page.get_by_label("{_safe_py_str(field)}", exact=True), "{_safe_py_str(value)}", "{_safe_py_str(field)} field")'
        )

    elif control == ControlType.PASSWORD_INPUT:
        _, value = _extract_fill_target_and_value(criterion)
        lines.append(
            f'    fill_ready(page, page.get_by_label("Password", exact=True), "{_safe_py_str(value)}", "Password field")'
        )

    elif control == ControlType.EMAIL_INPUT:
        _, value = _extract_fill_target_and_value(criterion)
        lines.append(
            f'    fill_ready(page, page.get_by_label("Email", exact=True), "{_safe_py_str(value)}", "Email field")'
        )

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
        lines += [
            f'    unique_visible(page.get_by_label("{_safe_py_str(field)}", exact=True), "{_safe_py_str(field)} dropdown").select_option("{_safe_py_str(option)}")',
        ]

    elif control == ControlType.FILE_INPUT:
        lines.append("    page.locator('input[type=\"file\"]').set_input_files('test_file.txt')")

    elif control == ControlType.BUTTON:
        role, label = _extract_click_target(criterion)
        if role == "button":
            lines.append(
                f'    click_ready(page, page.get_by_role("button", name="{_safe_py_str(label)}", exact=True), "{_safe_py_str(label)} button")'
            )
        else:
            lines.append(_manual_review_warning_line("No stable button locator could be derived", criterion))

    elif control == ControlType.LINK:
        _, label = _extract_click_target(criterion)
        lines.append(
            f'    click_ready(page, page.get_by_role("link", name="{_safe_py_str(label)}", exact=True), "{_safe_py_str(label)} link")'
        )

    elif control == ControlType.FORM_SUBMIT:
        lines.append('    click_ready(page, page.get_by_role("button", name="Submit", exact=True), "Submit button")')

    elif control == ControlType.BROWSER_ALERT:
        if "dismiss" in lower:
            lines += [
                '    page.once("dialog", lambda dialog: dialog.dismiss())',
                "    # Trigger the alert",
                '    click_ready(page, page.get_by_role("button").first, "Alert trigger button")',
            ]
        else:
            lines += [
                '    page.once("dialog", lambda dialog: dialog.accept())',
                "    # Trigger the alert",
                '    click_ready(page, page.get_by_role("button").first, "Alert trigger button")',
            ]

    elif control == ControlType.BROWSER_CONFIRM:
        if "dismiss" in lower or "cancel" in lower:
            lines.append('    page.once("dialog", lambda dialog: dialog.dismiss())')
        else:
            lines.append('    page.once("dialog", lambda dialog: dialog.accept())')

    elif control == ControlType.BROWSER_PROMPT:
        prompt_val = _extract_quoted_value(criterion) or "response text"
        lines.append(f'    page.once("dialog", lambda dialog: dialog.accept("{_safe_py_str(prompt_val)}"))')

    elif control == ControlType.HOVER_TARGET:
        cleaned = re.sub(
            r"^(?:hover|mouse over)\s+(?:over\s+)?(?:the\s+)?", "", criterion, flags=re.IGNORECASE
        ).strip()
        target = _extract_quoted_value(criterion) or cleaned or "element"
        lines.append(
            f'    unique_visible(page.get_by_text("{_safe_py_str(target)}", exact=True), "{_safe_py_str(target)} hover target").hover()'
        )

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
            if _looks_like_placeholder_assertion(subject):
                lines.append(_manual_review_warning_line("Assertion text is not DOM-backed", criterion))
            else:
                lines.append(
                    f'    expect(unique_visible(page.get_by_text("{_safe_py_str(subject)}", exact=True), "{_safe_py_str(subject)} assertion target")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)'
                )

    elif control == ControlType.LOGIN_CREDENTIALS:
        # "Login using valid Admin credentials" — use env vars; no URL extraction needed
        lines += [
            '    fill_ready(page, page.locator("input[name=\'username\']"), os.environ.get("TEST_USERNAME", "Admin"), "Username input")',
            '    fill_ready(page, page.locator("input[name=\'password\']"), os.environ.get("TEST_PASSWORD", "admin123"), "Password input")',
            '    click_ready(page, page.get_by_role("button", name="Login", exact=True), "Login button")',
            '    expect(page).to_have_url(re.compile(r".*/dashboard.*"), timeout=NAVIGATION_TIMEOUT_MS)',
        ]

    elif control == ControlType.DATE_PICKER_FUTURE:
        # "Select a future From Date" / "Select From Date"
        field_match = re.search(
            r"(from|to|start|end|leave)\s+date",
            lower,
        )
        field_label = field_match.group(0).title() if field_match else "Date"
        lines += [
            f'    # Date picker — select a future date for "{field_label}"',
            f'    page.locator("input.oxd-date-input-field, input[placeholder*=\'Date\'], [class*=\'date\'] input").first.click()',
            '    dismiss_known_overlays(page)',
            '    # Click the next-month arrow until a future date is reachable, then click a date cell',
            '    future_date_cell = page.locator("[class*=\'calender-cell\'], [class*=\'day\']:not([class*=\'disabled\']):not([class*=\'prev\']):not([class*=\'next\'])").nth(14)',
            '    future_date_cell.click(timeout=ACTION_TIMEOUT_MS)',
        ]

    elif control == ControlType.DATE_PICKER_PAST:
        # "Select past leave date" / "Select a past date"
        field_match = re.search(
            r"(from|to|start|end|leave|past)\s+.*date|date.*past",
            lower,
        )
        field_label = field_match.group(0).title() if field_match else "Date"
        lines += [
            f'    # Date picker — select a past date for "{field_label}"',
            f'    page.locator("input.oxd-date-input-field, input[placeholder*=\'Date\'], [class*=\'date\'] input").first.click()',
            '    dismiss_known_overlays(page)',
            '    # Click a past date cell (use a date 7 days ago)',
            '    past_date_cell = page.locator("[class*=\'calender-cell\'], [class*=\'day\']:not([class*=\'disabled\']):not([class*=\'prev\']):not([class*=\'next\'])").nth(1)',
            '    past_date_cell.click(timeout=ACTION_TIMEOUT_MS)',
        ]

    elif control == ControlType.WAIT:
        lines += [
            '    dismiss_known_overlays(page)',
            '    expect(page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)',
        ]

    else:
        logger.warning("Criterion not recognized for heuristic mapping: %s", criterion)
        lines.append(_manual_review_warning_line("Criterion not mapped to a stable automation step", criterion))

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


def _load_quality_standards() -> str:
    """Return the quality standards body, or empty string if the file is missing."""
    try:
        return _prompt_loader.get("test_quality_standards")
    except (FileNotFoundError, KeyError):
        logger.debug("test_quality_standards prompt not found — skipping injection")
        return ""


def _format_supporting_documents(docs: List[Dict[str, Any]]) -> str:
    """Format a list of supporting document dicts into a prompt section string.

    Each document is labelled with its filename so the LLM knows which artefact
    it is reading (wireframe vs schema vs requirements doc, etc.).
    """
    if not docs:
        return ""
    lines = ["## Supporting Documents (use these to inform test cases and locators)"]
    for doc in docs:
        filename = doc.get("filename", "document")
        content = doc.get("content", "").strip()
        if content:
            lines += ["", f"### {filename}", content]
    return "\n".join(lines)


# Maximum manual tests generated per user story (enforced in code, not just in the prompt)
_MAX_MANUAL_TESTS = 5

# Placeholder / comment patterns that indicate unimplemented automation code
_PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*#\s*(WARNING|TODO|FIXME|NOTE|Criterion not mapped|add Playwright action here"
    r"|placeholder|replace this|implement|step completes|needs manual review"
    r"|Manual locator review required|No stable|Assertion text is not DOM)",
    re.IGNORECASE,
)

_GLOB_URL_WAIT_RE = re.compile(
    r'(?P<indent>\s*)page\.wait_for_url\("(?P<glob>\*\*[^"]+)",\s*timeout=(?P<timeout>\d+)\)'
)

# Known placeholder domains that indicate the LLM hallucinated a URL instead of
# using os.environ["APP_URL"].  Matches patterns like:
#   https://your-app.com/...   https://./your-app.com/...   http://example.com/...
_PLACEHOLDER_URL_RE = re.compile(
    r'(?:https?://)?(?:\./)?(?:your[-_]app\.com|example\.com|your[-_]domain\.com)[^\s"\']*',
    re.IGNORECASE,
)


def _scrub_placeholder_urls(script: str) -> str:
    """Replace known placeholder URLs with os.environ['APP_URL'].

    The LLM sometimes emits template URLs (e.g. ``https://your-app.com/login``)
    when the real application URL is not provided.  This turns them into the
    canonical env-var reference so tests fail with a clear NameError rather than
    a mysterious net::ERR_NAME_NOT_RESOLVED.
    """
    return _PLACEHOLDER_URL_RE.sub('os.environ["APP_URL"]', script)

_FALLBACK_RUNTIME_HELPERS = textwrap.dedent(
    """
    ACTION_TIMEOUT_MS = 30_000
    NAVIGATION_TIMEOUT_MS = 60_000
    ASSERTION_TIMEOUT_MS = 15_000
    OVERLAY_SELECTORS = [
        "[role='dialog']",
        "[aria-modal='true']",
        "[data-testid*='modal']",
        "[data-testid*='overlay']",
        "[class*='modal']",
        "[class*='overlay']",
        "[class*='backdrop']",
    ]


    def configure_page(page: Page) -> None:
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)


    def dismiss_known_overlays(page: Page) -> None:
        for selector in OVERLAY_SELECTORS:
            overlay = page.locator(selector)
            try:
                if overlay.count() == 0:
                    continue
                close_button = overlay.get_by_role(
                    "button",
                    name=re.compile(r"close|dismiss|cancel|not now|skip|got it", re.IGNORECASE),
                ).first
                if close_button.is_visible(timeout=1_000):
                    close_button.click(timeout=2_000)
            except Exception:
                continue
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass


    def unique_visible(locator: Locator, description: str) -> Locator:
        expect(locator).to_have_count(1, timeout=ASSERTION_TIMEOUT_MS)
        expect(locator).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)
        return locator


    def click_ready(page: Page, locator: Locator, description: str) -> None:
        dismiss_known_overlays(page)
        target = unique_visible(locator, description)
        expect(target).to_be_enabled(timeout=ASSERTION_TIMEOUT_MS)
        target.scroll_into_view_if_needed()
        target.click(timeout=ACTION_TIMEOUT_MS)


    def fill_ready(page: Page, locator: Locator, value: str, description: str) -> None:
        dismiss_known_overlays(page)
        target = unique_visible(locator, description)
        target.scroll_into_view_if_needed()
        target.fill(value, timeout=ACTION_TIMEOUT_MS)


    def expect_url_path(page: Page, path_fragment: str) -> None:
        expect(
            page,
        ).to_have_url(
            re.compile(rf".*{re.escape(path_fragment.strip('/'))}.*"),
            timeout=NAVIGATION_TIMEOUT_MS,
        )
    """
).strip()


def _glob_to_url_regex(glob_pattern: str) -> str:
    """Convert a simple Playwright glob URL pattern into a regex fragment."""
    pattern = glob_pattern
    if pattern.startswith("**/"):
        pattern = pattern[3:]
    pattern = pattern.strip("*")
    pattern = pattern.strip("/")
    escaped_pattern = re.escape(pattern).replace("\\/", "/")
    return rf".*{escaped_pattern}.*"


def _inject_runtime_helpers(script: str) -> str:
    """Add shared Playwright helper functions and stronger imports to generated scripts."""
    if "def configure_page(page: Page)" in script:
        return script

    if "import os" not in script:
        script = "import os\n" + script

    if "import re" not in script:
        script = "import re\n" + script

    script = re.sub(
        r"from playwright\.sync_api import Page, expect",
        "from playwright.sync_api import Locator, Page, expect",
        script,
    )

    if "from playwright.sync_api import Locator, Page, expect" not in script:
        script = script.replace(
            "from playwright.sync_api import Page, expect",
            "from playwright.sync_api import Locator, Page, expect",
        )

    helper_block = f"\n\n{_FALLBACK_RUNTIME_HELPERS}\n\n"

    import_anchor = "from playwright.sync_api import Locator, Page, expect\n"
    if import_anchor in script:
        script = script.replace(import_anchor, import_anchor + helper_block, 1)
    else:
        script = helper_block + script

    return script


def _normalise_generated_script(script: str) -> str:
    """Tighten generated Playwright code for dynamic UIs and strict-mode safety."""
    script = _strip_automation_placeholders(script)
    script = _scrub_placeholder_urls(script)
    script = _inject_runtime_helpers(script)

    script = _GLOB_URL_WAIT_RE.sub(
        lambda m: (
            f'{m.group("indent")}expect(page).to_have_url('
            f're.compile(r"{_glob_to_url_regex(m.group("glob"))}"), '
            f'timeout={m.group("timeout")})'
        ),
        script,
    )

    script = re.sub(
        r'(?m)^(\s*)page\.wait_for_load_state\("networkidle"(?:,\s*timeout=\d+)?\)\s*$',
        r'\1expect(page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)',
        script,
    )

    if "configure_page(page)" not in script:
        script = re.sub(
            r'(^def test_[^(]+\([^)]*\)\s*->\s*None:\n(?:\s+""".*?"""\n)?)',
            r"\1    configure_page(page)\n    dismiss_known_overlays(page)\n",
            script,
            count=1,
            flags=re.DOTALL | re.MULTILINE,
        )

    return script


def _cap_and_consolidate(tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enforce maximum _MAX_MANUAL_TESTS tests, prioritising coverage diversity.

    Selection order: 1 smoke → up to 2 regression → up to 2 edge.
    If any bucket is empty the remaining slots are filled from whatever is left.
    """
    if len(tests) <= _MAX_MANUAL_TESTS:
        return tests

    by_risk: Dict[str, List] = {"smoke": [], "regression": [], "edge": []}
    for t in tests:
        rl = str(t.get("risk_level", "regression")).lower()
        by_risk.setdefault(rl, []).append(t)

    selected: List[Dict] = []
    for risk, quota in [("smoke", 1), ("regression", 2), ("edge", 2)]:
        selected.extend(by_risk.get(risk, [])[:quota])

    # Fill remaining slots with any test not yet selected
    if len(selected) < _MAX_MANUAL_TESTS:
        chosen_names = {t["name"] for t in selected}
        for t in tests:
            if t["name"] not in chosen_names and len(selected) < _MAX_MANUAL_TESTS:
                selected.append(t)

    logger.info(
        "Capped manual tests from %d → %d (limit=%d)",
        len(tests), len(selected), _MAX_MANUAL_TESTS,
    )
    return selected[:_MAX_MANUAL_TESTS]


def _strip_automation_placeholders(code: str) -> str:
    """Remove placeholder / unimplemented comment lines from a Playwright script.

    Removes:
      - # WARNING: ...  (generator warnings must never appear in committed code)
      - # TODO: ...
      - # FIXME: ...
      - # Criterion not mapped ...
      - # add Playwright action here ...
      - Any indented comment-only line inside a test function body that is
        purely advisory and doesn't correspond to a real step header.

    Preserves:
      - Module-level docstrings
      - Import statements
      - Step header comments that follow the pattern "# --- Step N: ..."
      - Inline expected-result notes that follow "# Expected: ..."
      - # UNGROUNDABLE: markers (surfaced to RECOMMENDATIONS, not silently dropped)
    """
    lines = code.splitlines(keepends=True)
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            result.append(line)
            continue
        # Keep step-header and expected-result comments — they are structural
        if re.match(r"#\s*---\s*Step\s+\d+", stripped) or re.match(r"#\s*Expected:", stripped):
            result.append(line)
            continue
        # Keep UNGROUNDABLE markers — they propagate to RECOMMENDATIONS for human review
        if re.match(r"#\s*UNGROUNDABLE\b", stripped, re.IGNORECASE):
            result.append(line)
            continue
        # Drop all WARNING, TODO, FIXME, and other placeholder comments
        if _PLACEHOLDER_LINE_RE.match(line):
            continue
        # Keep everything else (imports, module-level comments, etc.)
        result.append(line)
    return "".join(result)


# ---------------------------------------------------------------------------
# Phase C helpers — BDD bundle parsing + POM synthesis
# ---------------------------------------------------------------------------

def _parse_attr(attrs_str: str, attr_name: str, default: str = "") -> str:
    """Extract a single XML attribute value from an attribute string."""
    m = re.search(rf'{re.escape(attr_name)}=["\']([^"\']*)["\']', attrs_str)
    return m.group(1) if m else default


def _parse_bdd_bundle_output(raw: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Parse an ``<automation_bundle>`` XML response (from ``3.0_bdd.md`` prompt).

    Returns ``(bdd_bundle, locators_raw, recommendations)``.

    The ``bdd_bundle`` shape matches what ``commands.py`` consumes at the BDD
    apply path (``commands.py:962-1035``):

    .. code-block:: python

        {
            "features":     [{"action": ..., "file": ..., "content": ...}],
            "steps":        [{"action": ..., "file": ..., "code": ...}],
            "page_objects": [{"action": ..., "file": ..., "code": ..., "class_name": ...}],
            "locators":     [{"action": ..., "file": ..., "entries": [...]}],
            "keywords":     [{...}],
            "test_data":    [],
        }
    """
    bundle: Dict[str, Any] = {
        "features": [],
        "steps": [],
        "page_objects": [],
        "locators": [],
        "keywords": [],
        "test_data": [],
    }
    locators_raw: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    # Extract the content of <automation_bundle>…</automation_bundle>
    m = re.search(r"<automation_bundle>(.*?)</automation_bundle>", raw, re.DOTALL)
    if not m:
        # LLM sometimes truncates the closing tag
        m = re.search(r"<automation_bundle>(.*)", raw, re.DOTALL)
    if not m:
        logger.warning("No <automation_bundle> block found in BDD LLM response")
        return bundle, locators_raw, recommendations

    content = m.group(1)

    def _cdata(tag_body: str) -> str:
        """Return CDATA content or stripped raw text."""
        c = re.search(r"<!\[CDATA\[(.*?)\]\]>", tag_body, re.DOTALL)
        return c.group(1).strip() if c else tag_body.strip()

    # <feature action=... file=...>CDATA</feature>
    for fm in re.finditer(r"<feature\s+([^>]*)>(.*?)</feature>", content, re.DOTALL):
        attrs, body = fm.group(1), fm.group(2)
        file_ = _parse_attr(attrs, "file")
        if file_:
            bundle["features"].append({
                "action": _parse_attr(attrs, "action", "create"),
                "file": file_,
                "content": _cdata(body),
            })

    # <steps action=... file=...>CDATA</steps>
    for sm in re.finditer(r"<steps\s+([^>]*)>(.*?)</steps>", content, re.DOTALL):
        attrs, body = sm.group(1), sm.group(2)
        file_ = _parse_attr(attrs, "file")
        if file_:
            bundle["steps"].append({
                "action": _parse_attr(attrs, "action", "create"),
                "file": file_,
                "code": _cdata(body),
            })

    # <page_object action=... file=... class=...>CDATA</page_object>
    for pm in re.finditer(r"<page_object\s+([^>]*)>(.*?)</page_object>", content, re.DOTALL):
        attrs, body = pm.group(1), pm.group(2)
        file_ = _parse_attr(attrs, "file")
        if file_:
            bundle["page_objects"].append({
                "action": _parse_attr(attrs, "action", "create"),
                "file": file_,
                "code": _cdata(body),
                "class_name": _parse_attr(attrs, "class"),
            })

    # <locators action=... file=...>CDATA-JSON</locators>
    for lm in re.finditer(r"<locators\s+([^>]*)>(.*?)</locators>", content, re.DOTALL):
        attrs, body = lm.group(1), lm.group(2)
        file_ = _parse_attr(attrs, "file")
        entries: List[Dict] = []
        raw_json = _cdata(body)
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    entries = parsed
                    locators_raw.extend(parsed)
            except json.JSONDecodeError:
                logger.debug("Could not parse <locators> JSON in BDD bundle")
        if file_:
            bundle["locators"].append({
                "action": _parse_attr(attrs, "action", "create"),
                "file": file_,
                "entries": entries,
            })

    # <keywords action="register">CDATA-JSON</keywords>
    for km in re.finditer(r"<keywords\s+[^>]*>(.*?)</keywords>", content, re.DOTALL):
        raw_json = _cdata(km.group(1))
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    bundle["keywords"].extend(parsed)
            except json.JSONDecodeError:
                logger.debug("Could not parse <keywords> JSON in BDD bundle")

    return bundle, locators_raw, recommendations


_AUTH_PRECONDITION_PHRASES = (
    "logged in",
    "authenticated",
    "on the dashboard",
    "already logged in",
    "signed in",
    "valid session",
    "active session",
    "user is logged",
    "user has logged",
)


def _needs_authenticated_page(preconditions: str) -> bool:
    """Return True when the preconditions indicate the user must already be logged in."""
    low = preconditions.lower()
    return any(phrase in low for phrase in _AUTH_PRECONDITION_PHRASES)


def _extract_test_body_lines(script_code: str) -> List[str]:
    """Extract the body lines of the first ``test_*`` function in *script_code*.

    Returns lines indented at 8 spaces (suitable for a class method body).
    Skips the leading docstring of the function.
    """
    try:
        tree = ast.parse(script_code)
    except SyntaxError:
        return []

    source_lines = script_code.splitlines(keepends=True)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        body_nodes = node.body
        # Skip leading docstring
        if (
            body_nodes
            and isinstance(body_nodes[0], ast.Expr)
            and isinstance(body_nodes[0].value, ast.Constant)
            and isinstance(body_nodes[0].value.value, str)
        ):
            body_nodes = body_nodes[1:]
        if not body_nodes:
            return []

        start = body_nodes[0].lineno - 1
        end = node.end_lineno  # type: ignore[attr-defined]
        raw_lines = source_lines[start:end]

        # Re-indent from 4-space (test fn body) to 8-space (class method body)
        result = []
        for ln in raw_lines:
            stripped_ln = ln.rstrip("\n").rstrip("\r")
            if stripped_ln.startswith("    "):
                result.append("        " + stripped_ln[4:])
            else:
                result.append(stripped_ln)
        return result

    return []


def _synthesize_pom_bundle(
    script_code: str,
    module_name: str,
    test_name: str,
    preconditions: str = "",
    human_name: str = "",
) -> Dict[str, Any]:
    """Build a minimal ``pom_bundle`` from a flat Playwright script.

    The entire flat-script body is wrapped in a single page-object method; a
    thin test file navigates and calls that method.  This avoids any LLM call
    and is robust even when the flat script is imperfect — the
    validate→repair loop in ``AutomationTestGenerator`` still runs on the
    synthesized test file.
    """
    # Derive class name from the human-readable test name when available so that
    # the class captures the full intent (e.g. "SuccessfulLoginWithValidCredentialsPage")
    # rather than the truncated module slug.
    if human_name:
        _clean = re.sub(r"^[A-Z]+-\d+[:\s\-]+", "", human_name).strip()
        _clean = re.sub(r"[^a-zA-Z0-9 ]", " ", _clean)
        page_class = "".join(w.capitalize() for w in _clean.split() if w) + "Page"
    else:
        page_class = "".join(w.capitalize() for w in re.split(r"[_\-]+", module_name)) + "Page"
    page_file = f"pages/{module_name}_page.py"
    test_file = f"tests/{module_name}/test_{test_name}.py"

    # Extract and adapt the test body
    body_lines = _extract_test_body_lines(script_code)
    # Remove page.goto(...) lines — BasePage.navigate() handles navigation
    body_lines = [ln for ln in body_lines if not re.match(r"\s*(?:self\._)?page\.goto\(", ln)]
    # Replace `page.` → `self._page.` and standalone `page` args; skip comment lines
    # so prose like "the login page. The user remains" is not mangled.
    body_lines = [
        ln if ln.lstrip().startswith("#") else re.sub(r"\bpage\b", "self._page",
            re.sub(r"(?<!\.)page\.", "self._page.", ln))
        for ln in body_lines
    ]

    if not body_lines:
        body_lines = [
            "        # [NEEDS MANUAL REVIEW] No automation steps were extracted.",
            "        # This usually means the MCP browser connection was unavailable during",
            "        # `phoenix automate`. Re-run after resolving the MCP connection, or",
            "        # fill in the Playwright steps manually.",
            "        pass",
        ]

    method_body = "\n".join(body_lines)

    # ── Page object ────────────────────────────────────────────────────────
    page_code = (
        f'"""{"".join(w.capitalize() for w in re.split(r"[_-]+", module_name))}Page'
        f" — synthesized by phoenix automate (pom mode).\"\"\"\n"
        f"from __future__ import annotations\n\n"
        f"import os\n"
        f"import re\n"
        f"from playwright.sync_api import Locator, Page, expect\n"
        f"from pages.base_page import BasePage\n\n\n"
        f"{_FALLBACK_RUNTIME_HELPERS}\n\n\n"
        f"class {page_class}(BasePage):\n"
        f'    """Page object for {module_name} tests."""\n\n'
        f'    URL_PATH = ""\n\n'
        f"    def {test_name}(self) -> None:\n"
        f'        """{test_name.replace("_", " ")}."""\n'
        f"{method_body}\n"
    )

    # Choose the correct pytest fixture based on preconditions: tests that start
    # from an already-authenticated state should use authenticated_page so the
    # session-scoped storage state is reused instead of logging in again.
    _fixture = "authenticated_page" if _needs_authenticated_page(preconditions) else "page"

    # ── Test file ──────────────────────────────────────────────────────────
    test_code = (
        f'"""Test: {test_name.replace("_", " ")}'
        f" — generated by phoenix automate (pom mode).\"\"\"\n"
        f"from __future__ import annotations\n\n"
        f"import pytest\n"
        f"from playwright.sync_api import Page\n"
        f"from pages.{module_name}_page import {page_class}\n\n\n"
        f"def test_{test_name}({_fixture}: Page) -> None:\n"
        f'    """{test_name.replace("_", " ")}."""\n'
        f"    _po = {page_class}({_fixture})\n"
        f"    _po.navigate()\n"
        f"    _po.{test_name}()\n"
    )

    return {
        "page_objects": [
            {"action": "extend", "file": page_file, "code": page_code, "class_name": page_class}
        ],
        "locators": [],  # handled by persist_locators shared helper
        "tests": [
            {"action": "extend", "file": test_file, "code": test_code}
        ],
        "test_data": [],
    }


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
        domain_knowledge = input_data.get("domain_knowledge", "")
        supporting_documents = input_data.get("supporting_documents", [])
        test_type = kwargs.get("test_type", "both")
        risk_level = kwargs.get("risk_level")

        knowledge_context = self.get_knowledge_context(query=user_story)
        prompt_state = {
            "manual_test_generator": _prompt_loader.prompt_state("manual_test_generator"),
            "automation_from_manual": _prompt_loader.prompt_state("automation_from_manual"),
            "test_name": _prompt_loader.prompt_state("test_name"),
        }

        cache_key = self._cache_key(
            "test_generation",
            user_story=user_story,
            application_url=application_url or "",
            acceptance_criteria=acceptance_criteria,
            test_type=test_type,
            prompt_signatures={name: state["signature"] for name, state in prompt_state.items()},
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
                "prompt_state": prompt_state,
                "llm_configured": bool(self.llm_client),
            },
        }

        # ---------------------------------------------------------------
        # Manual-First: always generate manual tests before automation.
        # When test_type is "automation" only, we still build a minimal
        # manual spec internally so the automation has proper steps to
        # translate — it is just not written to disk by the caller.
        # ---------------------------------------------------------------
        if test_type in ("manual", "both"):
            result["manual_tests"] = self._generate_manual_tests(
                user_story, application_url, acceptance_criteria, risk_level,
                supporting_documents=supporting_documents,
            )
            manual_tests_for_automation = result["manual_tests"]
        elif test_type == "automation":
            # Generate manual internally as input to automation
            manual_tests_for_automation = self._generate_manual_tests(
                user_story, application_url, acceptance_criteria, risk_level,
                supporting_documents=supporting_documents,
            )
        else:
            manual_tests_for_automation = []

        if test_type in ("automation", "both"):
            result["automation_tests"] = self._generate_automation_tests(
                user_story=user_story,
                application_url=application_url,
                acceptance_criteria=acceptance_criteria,
                knowledge_context=knowledge_context,
                domain_knowledge=domain_knowledge,
                supporting_documents=supporting_documents,
                risk_level=risk_level,
                manual_tests=manual_tests_for_automation,
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
        supporting_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if self.llm_client:
            try:
                return self._generate_manual_tests_via_llm(
                    user_story, application_url, acceptance_criteria, risk_level,
                    supporting_documents=supporting_documents,
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
        supporting_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Call the LLM using the versioned manual_test_generator prompt."""
        system_prompt = _prompt_loader.get("manual_test_generator")

        # Group criteria thematically so the LLM can see what a consolidated test covers
        criteria_text = "\n".join(f"  {i}. {c}" for i, c in enumerate(acceptance_criteria, 1))
        n_criteria = len(acceptance_criteria)
        risk_instruction = (
            f"\nGenerate at least one '{risk_level}' level test." if risk_level else ""
        )

        user_prompt = (
            f"Generate consolidated manual test cases for the following user story.\n\n"
            f"## User Story\n{user_story}\n\n"
            f"## Application URL\n{application_url or 'Not specified'}\n\n"
            f"## Acceptance Criteria ({n_criteria} total — group related ones into the same test)\n"
            f"{criteria_text or '  (none provided)'}"
            f"{risk_instruction}\n\n"
            f"## HARD LIMIT\n"
            f"Return AT MOST {_MAX_MANUAL_TESTS} test cases in the JSON array.\n"
            f"Do NOT create one test per criterion. Group related criteria into one test.\n"
            f"Each test must cover a complete end-to-end workflow including login.\n\n"
            f"Return a JSON array of test case objects as specified in the system prompt."
        )

        knowledge_context = self.get_knowledge_context(query=user_story)
        if knowledge_context:
            user_prompt += f"\n\n## Context\n{knowledge_context[:1000]}"

        if supporting_documents:
            user_prompt += _format_supporting_documents(supporting_documents)

        quality_standards = _load_quality_standards()
        if quality_standards:
            user_prompt += f"\n\n## Quality Standards (apply to all generated tests)\n{quality_standards}"

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

        # Hard-enforce the cap regardless of what the LLM returned
        normalised = _cap_and_consolidate(normalised)
        logger.info("Final manual test count: %d", len(normalised))
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
        # Only add a bare navigate step if the first criterion isn't already a login/navigate step
        first_criterion = acceptance_criteria[0] if acceptance_criteria else ""
        first_is_login = _classify_control(first_criterion, application_url) in (
            ControlType.LOGIN, ControlType.NAVIGATE
        )
        if application_url and not first_is_login:
            steps.append(
                {
                    "step_number": 1,
                    "action": f"Navigate to {application_url} and log in",
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
    # Automation tests — derived from manual tests (1 script per manual test)
    # ------------------------------------------------------------------

    def _generate_automation_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        knowledge_context: str,
        domain_knowledge: str = "",
        supporting_documents: Optional[List[Dict[str, Any]]] = None,
        risk_level: Optional[str] = None,
        manual_tests: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate one automation script for each manual test."""
        if not manual_tests:
            if not self.llm_client:
                raise RuntimeError(
                    "LLM client is not configured. Set ANTHROPIC_API_KEY (or equivalent) "
                    "and restart the intelligence server. "
                    "Alternatively run 'phoenix generate' first to create manual tests, "
                    "then 'phoenix automate' to derive scripts from them without LLM."
                )
            logger.warning("No manual tests provided — generating single fallback script")
            return self._generate_single_automation_fallback(
                user_story, application_url, acceptance_criteria, risk_level
            )

        # Fetch the page snapshot once for all tests.
        # Phase D: best-effort grounding — never block generation on MCP failure.
        page_snapshot = ""
        if self.mcp_client and application_url:
            logger.info("Inspecting page via MCP: %s", application_url)
            try:
                import concurrent.futures as _cf
                _mcp_pool = _cf.ThreadPoolExecutor(max_workers=1)
                _mcp_fut = _mcp_pool.submit(self.mcp_client.inspect_page, application_url)
                try:
                    page_snapshot = _mcp_fut.result(timeout=60) or ""
                    logger.info("MCP snapshot received (%d chars)", len(page_snapshot))
                except _cf.TimeoutError:
                    logger.warning(
                        "MCP inspect_page timed out after 60s for %s — proceeding without snapshot",
                        application_url,
                    )
                    page_snapshot = ""
                finally:
                    _mcp_pool.shutdown(wait=False)  # don't block; hung thread runs in background
            except Exception as _mcp_exc:
                logger.error(
                    "MCP inspect_page failed for %s — generation will proceed without a DOM "
                    "snapshot. Page object methods will contain [NEEDS MANUAL REVIEW] markers "
                    "and must be completed before tests can run. Error: %s",
                    application_url, _mcp_exc,
                )
                page_snapshot = ""

        results = []
        for manual_test in manual_tests:
            gen = self._generate_script_for_manual_test(
                manual_test=manual_test,
                application_url=application_url,
                knowledge_context=knowledge_context,
                domain_knowledge=domain_knowledge,
                supporting_documents=supporting_documents,
                page_snapshot=page_snapshot,
            )
            script_code = gen["script_code"]
            test_name = self._derive_short_name(manual_test.get("name", user_story))
            results.append(
                {
                    "name": test_name,
                    "description": manual_test.get("description", user_story),
                    "manual_test_name": manual_test.get("name", ""),
                    "script_template": "playwright",
                    "script_code": script_code,
                    "test_steps": [
                        s.get("action", "") for s in manual_test.get("steps", [])
                    ],
                    "locators": gen["locators"],
                    "recommendations": gen["recommendations"],
                    "application_url": application_url,
                    "risk_level": manual_test.get("risk_level", risk_level or "regression"),
                    "generation_mode": "fallback" if not self.llm_client else "llm",
                    "warnings": self._collect_script_warnings(script_code),
                    "tags": ["automation", "generated", "manual-derived"],
                }
            )
            logger.info(
                "Generated automation script for manual test: %s", manual_test.get("name", "")
            )

        return results

    def _generate_script_for_manual_test(
        self,
        manual_test: Dict[str, Any],
        application_url: Optional[str],
        knowledge_context: str,
        domain_knowledge: str = "",
        supporting_documents: Optional[List[Dict[str, Any]]] = None,
        page_snapshot: str = "",
        manifest: str = "",
    ) -> Dict[str, Any]:
        """Translate a single manual test into a Playwright script via LLM or fallback."""
        if not self.llm_client:
            script = self._build_fallback_script_from_manual_test(
                manual_test=manual_test,
                application_url=application_url,
            )
            return {
                "script_code": _normalise_generated_script(script),
                "locators": [],
                "recommendations": [],
            }

        try:
            system_prompt_template = _prompt_loader.get("automation_from_manual")
            system_prompt = _safe_substitute(
                system_prompt_template,
                knowledge_context=knowledge_context or "(no additional context)",
                manifest=manifest or "(no manifest available)",
                dom_snapshot=page_snapshot or "(no snapshot available)",
            )

            steps_text = self._format_manual_steps_for_prompt(manual_test)

            user_parts = [
                "Translate the following manual test case into a complete pytest + Playwright script.",
                "Follow EVERY step in order. Do not skip steps. Do not add steps not in the spec.",
                "",
                f"## Manual Test: {manual_test.get('name', 'Test Case')}",
                "",
                f"**Description:** {manual_test.get('description', '')}",
                f"**Risk Level:** {manual_test.get('risk_level', 'regression')}",
                f"**Preconditions:** {manual_test.get('preconditions', '')}",
                "",
                "## Steps (translate each one into Playwright code)",
                "",
                steps_text,
                "",
                f"**Overall Expected Result:** {manual_test.get('expected_result', '')}",
                "",
                f"## Application URL\n{application_url or 'N/A'}",
            ]

            if page_snapshot:
                user_parts += [
                    "",
                    "## Live DOM Snapshot (ground every locator in this snapshot)",
                    page_snapshot[:3000],
                ]
            else:
                user_parts += [
                    "",
                    "## DOM Snapshot",
                    "No live snapshot available. Use [name], [data-testid], or placeholder"
                    " attributes where visible in the manual test context. Mark any element"
                    " you cannot ground as UNGROUNDABLE in the RECOMMENDATIONS section.",
                ]

            if domain_knowledge and domain_knowledge.strip():
                user_parts += [
                    "",
                    "## Domain Knowledge (project-specific — use this to improve locator selection)",
                    domain_knowledge[:2000],
                ]

            if supporting_documents:
                user_parts += ["", _format_supporting_documents(supporting_documents)]

            user_parts += [
                "",
                "## Output format",
                "Return exactly three sections: ### SCRIPT, ### LOCATORS, ### RECOMMENDATIONS",
                "See the system prompt for the required structure of each section.",
            ]

            quality_standards = _load_quality_standards()
            if quality_standards:
                user_parts += [
                    "",
                    "## Quality Standards (apply to the generated script)",
                    quality_standards,
                ]

            user_prompt = "\n".join(user_parts)
            logger.info(
                "Generating automation via LLM for manual test: %s", manual_test.get("name", "")
            )
            raw = self.llm_client.generate(system_prompt, user_prompt)
            script, locators, recommendations = _parse_structured_v2_output(raw)
            normalised = _normalise_generated_script(script)
            # Validate the normalised script is syntactically correct before
            # sending it to the client.  If not, fall back to the heuristic stub
            # so the client never receives a file that will fail pytest collection.
            try:
                compile(normalised, "<generated>", "exec")
            except SyntaxError as _syn:
                logger.error(
                    "LLM returned syntactically invalid Python for '%s' "
                    "(line %d: %s) — falling back to heuristic stub.",
                    manual_test.get("name", ""),
                    _syn.lineno or 0,
                    _syn.msg,
                )
                normalised = _normalise_generated_script(
                    self._build_fallback_script_from_manual_test(
                        manual_test=manual_test,
                        application_url=application_url,
                    )
                )
                locators = []
                recommendations = [
                    f"LLM generated invalid Python (SyntaxError: {_syn.msg} at line "
                    f"{_syn.lineno}) — review this stub and fill in the Playwright steps "
                    "manually, or re-run `phoenix automate` once the prompt is improved."
                ]
            return {
                "script_code": normalised,
                "locators": locators,
                "recommendations": recommendations,
            }

        except Exception as exc:
            logger.warning(
                "LLM script generation failed for '%s', using fallback: %s",
                manual_test.get("name", ""),
                exc,
                exc_info=True,
            )
            script = self._build_fallback_script_from_manual_test(
                manual_test=manual_test,
                application_url=application_url,
            )
            return {
                "script_code": _normalise_generated_script(script),
                "locators": [],
                "recommendations": [],
            }

    def _build_fallback_script_from_manual_test(
        self,
        manual_test: Dict[str, Any],
        application_url: Optional[str],
    ) -> str:
        """Build a Playwright script by translating manual steps heuristically."""
        logger.warning(
            "Using heuristic fallback for manual test '%s'. "
            "Set ANTHROPIC_API_KEY for LLM-powered generation.",
            manual_test.get("name", ""),
        )
        steps: List[Dict[str, Any]] = manual_test.get("steps", [])
        url = application_url or "https://example.com"

        body_lines: List[str] = []

        if steps:
            for step in steps:
                action = step.get("action", "")
                step_num = step.get("step_number", 1)
                expected = step.get("expected_result", "")
                body_lines.append(f"    # --- Step {step_num}: {action} ---")
                playwright_lines = _criterion_to_playwright_lines(action, step_num, url)
                playwright_lines = [ln for ln in playwright_lines if not ln.startswith(f"    # Step {step_num}:")]
                body_lines.extend(playwright_lines)
                if expected:
                    body_lines.append(f"    # Expected: {expected}")
        else:
            body_lines += [
                "    # No manual steps provided — navigate to URL only",
                f'    page.goto("{url}", timeout=60_000)',
                '    page.wait_for_load_state("domcontentloaded")',
            ]

        body = "\n".join(body_lines)
        test_func_name = self._derive_short_name(manual_test.get("name", "test"))
        description = manual_test.get("description", manual_test.get("name", ""))

        return (
            f'"""{description.replace(chr(34), chr(39))} — automated by Phoenix."""\n'
            "import re\n"
            "import pytest\n"
            "from playwright.sync_api import Page, expect\n"
            "\n"
            "\n"
            f"def test_{test_func_name}(page: Page) -> None:\n"
            f'    """{description.replace(chr(34), chr(39))}"""\n'
            f"{body}\n"
        )

    def _generate_single_automation_fallback(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        risk_level: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Legacy single-script fallback used only when no manual tests exist."""
        url = application_url or "https://example.com"
        body_lines: List[str] = [
            "    # Navigate to target URL",
            f'    page.goto("{url}", timeout=60_000)',
            '    page.wait_for_load_state("domcontentloaded")',
            "",
        ]
        for idx, criterion in enumerate(acceptance_criteria, 1):
            body_lines.extend(_criterion_to_playwright_lines(criterion, idx, application_url))

        body = "\n".join(body_lines)
        test_name = self._derive_short_name(user_story)

        script_code = (
            "# WARNING: No manual tests — heuristic fallback from acceptance criteria.\n"
            "import re\n"
            "import pytest\n"
            "from playwright.sync_api import Page, expect\n"
            "\n\n"
            f"def test_{test_name}(page: Page) -> None:\n"
            f'    """{user_story.replace(chr(34), chr(39))}"""\n'
            f"{body}\n"
        )

        return [
            {
                "name": test_name,
                "description": user_story,
                "script_template": "playwright",
                "script_code": _normalise_generated_script(script_code),
                "test_steps": acceptance_criteria,
                "locators": [],
                "application_url": application_url,
                "risk_level": risk_level or "regression",
                "generation_mode": "fallback",
                "warnings": self._collect_script_warnings(script_code),
                "tags": ["automation", "generated", "fallback"],
            }
        ]

    def _build_automation_fallback_script(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
    ) -> str:
        """Return a heuristic fallback script string (used by tests and legacy callers)."""
        results = self._generate_single_automation_fallback(
            user_story, application_url, acceptance_criteria, risk_level=None
        )
        return results[0]["script_code"] if results else ""

    @staticmethod
    def _format_manual_steps_for_prompt(manual_test: Dict[str, Any]) -> str:
        """Format manual test steps as numbered list for the LLM prompt."""
        steps: List[Dict[str, Any]] = manual_test.get("steps", [])
        if not steps:
            return "(no steps provided)"
        lines = []
        for step in steps:
            num = step.get("step_number", "?")
            action = step.get("action", "")
            expected = step.get("expected_result", "")
            test_data = step.get("test_data", "")
            lines.append(f"**Step {num}:** {action}")
            if test_data:
                lines.append(f"  - Test data: {test_data}")
            lines.append(f"  - Expected: {expected}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public entry point: automate from pre-written manual tests
    # ------------------------------------------------------------------

    def automate_from_manual_tests(
        self,
        manual_tests: List[Dict[str, Any]],
        application_url: Optional[str] = None,
        domain_knowledge: str = "",
        manifest: str = "",
        use_pom: bool = False,
        use_bdd: bool = False,
        keywords: str = "",
    ) -> Dict[str, Any]:
        """Generate one automation script for each supplied manual test.

        This is the entry point for ``phoenix automate`` — the user has already
        reviewed / edited the manual tests on disk and now wants scripts derived
        directly from those tests, with no LLM re-generation of the spec.

        Branching (Phase C):
        - ``use_bdd=True``: uses the ``3.0_bdd.md`` prompt and returns a
          ``bdd_bundle`` that the CLI applies via ``OutputManager``.
        - ``use_pom=True``: generates a flat script then synthesises a
          ``pom_bundle`` (page object + thin test file) deterministically.
        - Neither: flat script as before.

        MCP grounding is best-effort (Phase D): a failing MCP call logs a
        warning and continues with an empty snapshot rather than aborting.
        """
        if not manual_tests:
            return {"automation_tests": []}

        knowledge_context = self.get_knowledge_context(query="playwright automation")

        # Phase D — best-effort grounding: never block on MCP failure
        page_snapshot = ""
        if self.mcp_client and application_url:
            try:
                import concurrent.futures as _cf
                _mcp_pool = _cf.ThreadPoolExecutor(max_workers=1)
                _mcp_fut = _mcp_pool.submit(self.mcp_client.inspect_page, application_url)
                try:
                    page_snapshot = _mcp_fut.result(timeout=60) or ""
                except _cf.TimeoutError:
                    logger.warning(
                        "MCP inspect_page timed out after 60s for %s — proceeding without snapshot",
                        application_url,
                    )
                    page_snapshot = ""
                finally:
                    _mcp_pool.shutdown(wait=False)  # don't block; hung thread runs in background
            except Exception as _mcp_exc:
                logger.error(
                    "MCP inspect_page failed for %s — generation will proceed without a DOM "
                    "snapshot. Page object methods will contain [NEEDS MANUAL REVIEW] markers "
                    "and must be completed before tests can run. Error: %s",
                    application_url, _mcp_exc,
                )
                page_snapshot = ""

        results = []
        for manual_test in manual_tests:
            test_name = self._derive_short_name(manual_test.get("name", "test"))
            source_file = manual_test.get("source_file", "")
            # Derive a clean module name from source file:
            # 1. Take the file stem and slugify it
            # 2. Strip leading "manual_test_NNN_", "tc_NNN_" prefixes (file-naming artefacts)
            # 3. Truncate to 30 chars on a word boundary so class/file names stay readable
            if source_file:
                _stem = re.sub(r"[^\w]", "_", Path(source_file).stem).strip("_").lower()
                _stem = re.sub(r"^(?:manual_test_\d+_|tc_\d+_|test_\d+_)+", "", _stem).strip("_")
                if len(_stem) > 50:
                    _trunc = _stem[:50]
                    _last_us = _trunc.rfind("_")
                    _stem = (_trunc[:_last_us].strip("_") if _last_us > 5 else _trunc).strip("_")
                module_name = _stem or test_name
            else:
                module_name = test_name

            if use_bdd:
                # ── Phase C: BDD bundle via 3.0_bdd.md prompt ────────────
                gen = self._generate_bdd_bundle_for_manual_test(
                    manual_test=manual_test,
                    application_url=application_url,
                    knowledge_context=knowledge_context,
                    domain_knowledge=domain_knowledge,
                    page_snapshot=page_snapshot,
                    manifest=manifest,
                    keywords=keywords,
                )
                results.append(
                    {
                        "name": test_name,
                        "description": manual_test.get("description", ""),
                        "manual_test_name": manual_test.get("name", ""),
                        "source_file": source_file,
                        "script_template": "bdd",
                        "script_code": "",  # BDD produces a bundle, not a flat file
                        "test_steps": [s.get("action", "") for s in manual_test.get("steps", [])],
                        "locators": gen.get("locators_raw", []),
                        "recommendations": gen.get("recommendations", []),
                        "application_url": application_url,
                        "risk_level": manual_test.get("risk_level", "regression"),
                        "generation_mode": "fallback" if not self.llm_client else "llm",
                        "warnings": [],
                        "tags": ["automation", "generated", "manual-derived", "bdd"],
                        "bdd_bundle": gen.get("bdd_bundle", {}),
                    }
                )
                logger.info("Generated BDD bundle for manual test: %s", manual_test.get("name", ""))

            elif use_pom:
                # ── Phase C: POM bundle (flat script + synthesized page object) ──
                gen = self._generate_script_for_manual_test(
                    manual_test=manual_test,
                    application_url=application_url,
                    knowledge_context=knowledge_context,
                    domain_knowledge=domain_knowledge,
                    page_snapshot=page_snapshot,
                    manifest=manifest,
                )
                script_code = gen["script_code"]
                pom_bundle = _synthesize_pom_bundle(
                    script_code,
                    module_name,
                    test_name,
                    preconditions=manual_test.get("preconditions", ""),
                    human_name=manual_test.get("name", ""),
                )
                results.append(
                    {
                        "name": test_name,
                        "description": manual_test.get("description", ""),
                        "manual_test_name": manual_test.get("name", ""),
                        "source_file": source_file,
                        "script_template": "pom",
                        "script_code": script_code,
                        "test_steps": [s.get("action", "") for s in manual_test.get("steps", [])],
                        "locators": gen["locators"],
                        "recommendations": gen["recommendations"],
                        "application_url": application_url,
                        "risk_level": manual_test.get("risk_level", "regression"),
                        "generation_mode": "fallback" if not self.llm_client else "llm",
                        "warnings": self._collect_script_warnings(script_code),
                        "tags": ["automation", "generated", "manual-derived", "pom"],
                        "pom_bundle": pom_bundle,
                    }
                )
                logger.info("Generated POM bundle for manual test: %s", manual_test.get("name", ""))

            else:
                # ── Flat mode ────────────────────────────────────────────
                gen = self._generate_script_for_manual_test(
                    manual_test=manual_test,
                    application_url=application_url,
                    knowledge_context=knowledge_context,
                    domain_knowledge=domain_knowledge,
                    page_snapshot=page_snapshot,
                    manifest=manifest,
                )
                script_code = gen["script_code"]
                results.append(
                    {
                        "name": test_name,
                        "description": manual_test.get("description", ""),
                        "manual_test_name": manual_test.get("name", ""),
                        "source_file": source_file,
                        "script_template": "playwright",
                        "script_code": script_code,
                        "preconditions": manual_test.get("preconditions", ""),
                        "test_steps": [s.get("action", "") for s in manual_test.get("steps", [])],
                        "locators": gen["locators"],
                        "recommendations": gen["recommendations"],
                        "application_url": application_url,
                        "risk_level": manual_test.get("risk_level", "regression"),
                        "generation_mode": "fallback" if not self.llm_client else "llm",
                        "warnings": self._collect_script_warnings(script_code),
                        "tags": ["automation", "generated", "manual-derived"],
                    }
                )
                logger.info("Automated manual test: %s", manual_test.get("name", ""))

        return {"automation_tests": results}

    # ------------------------------------------------------------------
    # Phase C — BDD generation
    # ------------------------------------------------------------------

    def _generate_bdd_bundle_for_manual_test(
        self,
        manual_test: Dict[str, Any],
        application_url: Optional[str],
        knowledge_context: str,
        domain_knowledge: str = "",
        page_snapshot: str = "",
        manifest: str = "",
        keywords: str = "",
    ) -> Dict[str, Any]:
        """Generate a BDD bundle for a single manual test using the ``3.0_bdd.md`` prompt.

        Returns ``{"bdd_bundle": {...}, "locators_raw": [...], "recommendations": [...]}``.
        On LLM failure returns an empty bundle so the CLI falls through to flat mode.
        """
        if not self.llm_client:
            logger.warning(
                "BDD generation skipped for '%s': no LLM client configured",
                manual_test.get("name", ""),
            )
            return {"bdd_bundle": {}, "locators_raw": [], "recommendations": []}

        try:
            system_prompt_template = _prompt_loader.get("automation_from_manual", "3.0_bdd")
            system_prompt = _safe_substitute(
                system_prompt_template,
                knowledge_context=knowledge_context or "(no additional context)",
                manifest=manifest or "(no manifest available)",
                keywords=keywords or "(no existing keywords)",
                dom_snapshot=page_snapshot or "(no live snapshot available)",
            )

            steps_text = self._format_manual_steps_for_prompt(manual_test)

            user_parts = [
                "Translate the following manual test case into a BDD automation bundle.",
                "Follow EVERY step in order. Emit <automation_bundle>…</automation_bundle>.",
                "",
                f"## Manual Test: {manual_test.get('name', 'Test Case')}",
                "",
                f"**Description:** {manual_test.get('description', '')}",
                f"**Risk Level:** {manual_test.get('risk_level', 'regression')}",
                f"**Preconditions:** {manual_test.get('preconditions', '')}",
                "",
                "## Steps (translate each one into Gherkin + page methods)",
                "",
                steps_text,
                "",
                f"**Overall Expected Result:** {manual_test.get('expected_result', '')}",
                "",
                f"## Application URL\n{application_url or 'N/A'}",
            ]

            if page_snapshot:
                user_parts += [
                    "",
                    "## Live DOM Snapshot (ground every locator in this snapshot)",
                    page_snapshot[:3000],
                ]
            else:
                user_parts += [
                    "",
                    "## DOM Snapshot",
                    "No live snapshot available. Use [name], [data-testid], or placeholder"
                    " attributes. Set verified_in_snapshot=false for all locators.",
                ]

            if domain_knowledge and domain_knowledge.strip():
                user_parts += [
                    "",
                    "## Domain Knowledge",
                    domain_knowledge[:2000],
                ]

            user_prompt = "\n".join(user_parts)
            logger.info("Generating BDD bundle via LLM for: %s", manual_test.get("name", ""))
            raw = self.llm_client.generate(system_prompt, user_prompt)
            bdd_bundle, locators_raw, recommendations = _parse_bdd_bundle_output(raw)
            return {
                "bdd_bundle": bdd_bundle,
                "locators_raw": locators_raw,
                "recommendations": recommendations,
            }

        except Exception as exc:
            logger.warning(
                "BDD bundle generation failed for '%s': %s — returning empty bundle",
                manual_test.get("name", ""),
                exc,
                exc_info=True,
            )
            return {"bdd_bundle": {}, "locators_raw": [], "recommendations": []}

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
    def _collect_script_warnings(script_code: str) -> List[str]:
        warnings: List[str] = []
        for line in script_code.splitlines():
            stripped = line.strip()
            if stripped.startswith("# WARNING:"):
                warnings.append(stripped[2:].strip())
        return warnings

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
