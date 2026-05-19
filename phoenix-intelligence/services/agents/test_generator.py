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
    LOGIN = "login"        # navigate + fill credentials + click login button
    NAVIGATE = "navigate"
    MENU_CLICK = "menu_click"  # click a top-level nav menu item
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


def _is_orangehrm_context(criterion: str, application_url: Optional[str] = None) -> bool:
    lower = criterion.lower()
    url_lower = (application_url or "").lower()
    return (
        "orangehrm" in lower
        or "opensource-demo.orangehrmlive.com" in url_lower
        or "leave module" in lower
        or "apply leave" in lower
        or "my leave" in lower
        or "dashboard" in lower
        or ("login" in lower and "admin" in lower)
    )


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
    is_orangehrm = _is_orangehrm_context(criterion, application_url)

    if (
        is_orangehrm
        and "username" in lower
        and "password" in lower
        and "visible" in lower
    ):
        lines += [
            '    expect(page.locator("input[name=\'username\']")).to_be_visible()',
            '    expect(page.locator("input[name=\'password\']")).to_be_visible()',
        ]

    elif (
        is_orangehrm
        and ("login using valid admin credentials" in lower or "log in using valid admin credentials" in lower)
    ):
        url = application_url or "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
        lines += [
            f'    page.goto("{_safe_py_str(url)}", timeout=60_000)',
            '    page.locator("input[name=\'username\']").fill("Admin")',
            '    page.locator("input[name=\'password\']").fill("admin123")',
            '    page.get_by_role("button", name="Login").click()',
            '    expect(page).to_have_url(re.compile(r".*/dashboard.*"))',
            '    expect(page.locator(".oxd-topbar-header-breadcrumb-module")).to_contain_text("Dashboard")',
        ]

    elif is_orangehrm and "dashboard" in lower and any(
        k in lower for k in ["verify", "visible", "loads successfully", "load successfully"]
    ):
        lines += [
            '    expect(page).to_have_url(re.compile(r".*/dashboard.*"))',
            '    expect(page.locator(".oxd-topbar-header-breadcrumb-module")).to_contain_text("Dashboard")',
        ]

    elif is_orangehrm and "navigate to the leave module" in lower:
        lines += [
            '    page.get_by_role("link", name="Leave").click()',
            '    expect(page.get_by_role("link", name="Apply")).to_be_visible()',
        ]

    elif is_orangehrm and "click apply under leave section" in lower:
        lines += [
            '    page.get_by_role("link", name="Apply").click()',
            '    expect(page).to_have_url(re.compile(r".*/leave/applyLeave.*"))',
        ]

    elif is_orangehrm and "apply leave page is visible" in lower:
        lines += [
            '    expect(page).to_have_url(re.compile(r".*/leave/applyLeave.*"))',
            '    expect(page.locator(".orangehrm-card-container").first).to_be_visible()',
        ]

    elif is_orangehrm and "select leave type" in lower:
        lines += [
            '    page.get_by_role("combobox").first.click()',
            '    page.get_by_role("option").first.click()',
        ]

    elif is_orangehrm and "from date" in lower and "future" in lower:
        lines += [
            '    page.get_by_placeholder("yyyy-mm-dd").nth(0).fill("2099-12-01")',
        ]

    elif is_orangehrm and "to date" in lower and "future" in lower:
        lines += [
            '    page.get_by_placeholder("yyyy-mm-dd").nth(1).fill("2099-12-02")',
        ]

    elif is_orangehrm and "enter leave comment" in lower:
        lines += [
            '    page.locator("textarea").fill("Applying leave through Phoenix automation.")',
        ]

    elif is_orangehrm and "success message appears" in lower:
        lines += [
            '    expect(page.locator(".oxd-toast")).to_be_visible(timeout=10_000)',
            '    expect(page.locator(".oxd-toast")).to_contain_text("Success")',
        ]

    elif is_orangehrm and "navigate to my leave" in lower:
        lines += [
            '    page.get_by_role("link", name="My Leave").click()',
            '    expect(page).to_have_url(re.compile(r".*/leave/viewMyLeaveList.*"))',
        ]

    elif is_orangehrm and "submitted leave request appears in leave list" in lower:
        lines += [
            '    expect(page.locator(".oxd-table-filter, .orangehrm-paper-container").first).to_be_visible()',
        ]

    elif is_orangehrm and "submit leave without selecting leave type" in lower:
        lines += [
            '    page.get_by_role("button", name="Apply").click()',
        ]

    elif is_orangehrm and "validation error messages appear" in lower:
        lines += [
            '    expect(page.locator(".oxd-input-field-error-message").first).to_be_visible()',
        ]

    elif control == ControlType.LOGIN:
        # Extract URL, username, password from step text
        url_match = _LOGIN_URL_RE.search(criterion)
        url = url_match.group(0).rstrip(".,)") if url_match else (application_url or "https://example.com")
        user_match = _LOGIN_USER_RE.search(criterion)
        username = user_match.group(1).strip().strip("'\"") if user_match else "Admin"
        pass_match = _LOGIN_PASS_RE.search(criterion)
        password = pass_match.group(1).strip().strip("'\"") if pass_match else "admin123"
        lines += [
            f'    page.goto("{_safe_py_str(url)}", timeout=60_000)',
            f'    page.locator("input[name=\'username\']").fill("{_safe_py_str(username)}")',
            f'    page.locator("input[name=\'password\']").fill("{_safe_py_str(password)}")',
            '    page.get_by_role("button", name="Login").click()',
            '    page.wait_for_url("**/dashboard**", timeout=30_000)',
            '    expect(page.locator(".oxd-topbar-header-breadcrumb-module")).to_contain_text("Dashboard")',
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
            f'    page.get_by_role("link", name="{_safe_py_str(label)}").click()',
            f'    expect(page.get_by_role("link", name="{_safe_py_str(label)}")).to_be_visible()',
        ]

    elif control == ControlType.NAVIGATE:
        url = _extract_quoted_value(criterion) or application_url or "https://example.com"
        lines += [
            f'    page.goto("{_safe_py_str(url)}", timeout=60_000)',
            '    page.wait_for_load_state("domcontentloaded")',
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
            lines.append(_manual_review_warning_line("No stable button locator could be derived", criterion))

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
            if _looks_like_placeholder_assertion(subject):
                lines.append(_manual_review_warning_line("Assertion text is not DOM-backed", criterion))
            else:
                lines.append(_manual_review_warning_line("No stable assertion locator could be derived", criterion))

    elif control == ControlType.WAIT:
        lines.append('    page.wait_for_load_state("domcontentloaded")')

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

# Maximum manual tests generated per user story (enforced in code, not just in the prompt)
_MAX_MANUAL_TESTS = 5

# Placeholder / comment patterns that indicate unimplemented automation code
_PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*#\s*(WARNING|TODO|FIXME|NOTE|Criterion not mapped|add Playwright action here"
    r"|placeholder|replace this|implement|step completes|needs manual review)",
    re.IGNORECASE,
)


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
      - # WARNING: ...
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
        if _MANUAL_REVIEW_WARNING.lower() in stripped.lower():
            result.append(line)
            continue
        # Drop placeholder/warning comments
        if _PLACEHOLDER_LINE_RE.match(line):
            continue
        # Keep everything else (imports, module-level comments, etc.)
        result.append(line)
    return "".join(result)


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
                user_story, application_url, acceptance_criteria, risk_level
            )
            manual_tests_for_automation = result["manual_tests"]
        elif test_type == "automation":
            # Generate manual internally as input to automation
            manual_tests_for_automation = self._generate_manual_tests(
                user_story, application_url, acceptance_criteria, risk_level
            )
        else:
            manual_tests_for_automation = []

        if test_type in ("automation", "both"):
            result["automation_tests"] = self._generate_automation_tests(
                user_story=user_story,
                application_url=application_url,
                acceptance_criteria=acceptance_criteria,
                knowledge_context=knowledge_context,
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
        risk_level: Optional[str],
        manual_tests: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate one automation script for each manual test.

        Each script is a direct translation of the manual test's numbered steps
        into Playwright code.  This guarantees:
          - Login is always step 1 (it's in the manual test)
          - Steps are in the correct order
          - 1 manual test → 1 automation script
        """
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

        # Fetch the page snapshot once for all tests
        page_snapshot = ""
        if self.mcp_client and application_url:
            try:
                logger.info("Inspecting page via MCP: %s", application_url)
                page_snapshot = self.mcp_client.inspect_page(application_url)
                if page_snapshot:
                    logger.info("MCP snapshot received (%d chars)", len(page_snapshot))
            except Exception as exc:
                logger.warning("MCP page inspection failed: %s", exc)

        results = []
        for manual_test in manual_tests:
            script_code = self._generate_script_for_manual_test(
                manual_test=manual_test,
                application_url=application_url,
                knowledge_context=knowledge_context,
                page_snapshot=page_snapshot,
            )
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
                    "locators": [],
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
        page_snapshot: str = "",
    ) -> str:
        """Translate a single manual test into a Playwright script via LLM or fallback."""
        if not self.llm_client:
            script = self._build_fallback_script_from_manual_test(
                manual_test=manual_test,
                application_url=application_url,
            )
            return _strip_automation_placeholders(script)

        try:
            system_prompt_template = _prompt_loader.get("automation_from_manual")
            system_prompt = system_prompt_template.format(
                knowledge_context=knowledge_context or "(no additional context)"
            )

            # Format the manual test steps clearly for the LLM
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
                    "## Live Page Snapshot (use these roles/names for accurate locators)",
                    page_snapshot[:3000],
                ]
            else:
                user_parts += [
                    "",
                    "## Page Snapshot",
                    "No live snapshot. Use the OrangeHRM locator table from the system prompt.",
                ]

            user_parts += [
                "",
                "## Output instructions",
                "- Return ONLY Python source code. No markdown fences.",
                "- One test function with a comment block for each manual step.",
                "- Include a full login sequence as step 1 (credentials from the step text).",
            ]

            user_prompt = "\n".join(user_parts)
            logger.info(
                "Generating automation via LLM for manual test: %s", manual_test.get("name", "")
            )
            raw = self.llm_client.generate(system_prompt, user_prompt)
            script = _strip_code_fences(raw)
            return _strip_automation_placeholders(script)

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
            return _strip_automation_placeholders(script)

    def _build_fallback_script_from_manual_test(
        self,
        manual_test: Dict[str, Any],
        application_url: Optional[str],
    ) -> str:
        """Build a Playwright script by translating manual steps heuristically.

        Each step's action text is classified and mapped to Playwright code,
        preserving the manual test's order (including login as step 1).
        """
        logger.warning(
            "⚠  Using heuristic fallback for manual test '%s'. "
            "Set ANTHROPIC_API_KEY for LLM-powered generation.",
            manual_test.get("name", ""),
        )
        steps: List[Dict[str, Any]] = manual_test.get("steps", [])
        url = application_url or "https://example.com"

        body_lines: List[str] = []

        # If steps exist, translate them in order
        if steps:
            for step in steps:
                action = step.get("action", "")
                step_num = step.get("step_number", 1)
                expected = step.get("expected_result", "")
                body_lines.append(f"    # --- Step {step_num}: {action} ---")
                # Translate this step
                playwright_lines = _criterion_to_playwright_lines(action, step_num, url)
                # Remove the header comment (already added above)
                playwright_lines = [ln for ln in playwright_lines if not ln.startswith(f"    # Step {step_num}:")]
                body_lines.extend(playwright_lines)
                if expected:
                    body_lines.append(f"    # Expected: {expected}")
        else:
            # No steps at all — bare navigate
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
                "script_code": _strip_automation_placeholders(script_code),
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
    ) -> Dict[str, Any]:
        """Generate one automation script for each supplied manual test.

        This is the entry point for ``phoenix automate`` — the user has already
        reviewed / edited the manual tests on disk and now wants scripts derived
        directly from those tests, with no LLM re-generation of the spec.

        Args:
            manual_tests:    Parsed manual test dicts (from manual_parser).
            application_url: Optional URL for context in the automation prompt.

        Returns:
            dict with key ``automation_tests`` (list of automation test dicts).
        """
        if not manual_tests:
            return {"automation_tests": []}

        knowledge_context = self.get_knowledge_context(query="playwright automation")

        page_snapshot = ""
        if self.mcp_client and application_url:
            try:
                page_snapshot = self.mcp_client.inspect_page(application_url) or ""
            except Exception as exc:
                logger.warning("MCP page inspection failed: %s", exc)

        results = []
        for manual_test in manual_tests:
            script_code = self._generate_script_for_manual_test(
                manual_test=manual_test,
                application_url=application_url,
                knowledge_context=knowledge_context,
                page_snapshot=page_snapshot,
            )
            test_name = self._derive_short_name(manual_test.get("name", "test"))
            results.append(
                {
                    "name": test_name,
                    "description": manual_test.get("description", ""),
                    "manual_test_name": manual_test.get("name", ""),
                    "source_file": manual_test.get("source_file", ""),
                    "script_template": "playwright",
                    "script_code": script_code,
                    "test_steps": [s.get("action", "") for s in manual_test.get("steps", [])],
                    "locators": [],
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
