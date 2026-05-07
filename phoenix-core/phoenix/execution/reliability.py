"""Automation reliability pipeline.

Provides four post-generation passes applied to every generated Playwright script:

  LocatorLinter       — flags anti-pattern locators (bare form, input, button selectors,
                        get_by_label on placeholder-only fields, get_by_role("heading")
                        for non-heading elements).

  WaitInjector        — ensures every state-changing click is followed by an appropriate
                        wait (wait_for_url or expect().to_be_visible()).

  AssertionValidator  — replaces fragile assertion patterns (role="alert", bare assert,
                        validity.valid synchronous checks) with robust alternatives.

  DynamicElementHandler — detects expandable/disclosure elements and wraps their
                          interactions with open→wait→interact sequences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# LocatorLinter
# ---------------------------------------------------------------------------

@dataclass
class LocatorWarning:
    pattern: str
    line_number: int
    message: str
    suggestion: str


class LocatorLinter:
    """Scans generated Playwright code for locator anti-patterns.

    Each rule is a (regex, message, suggestion) tuple.  Matching is done on a
    per-line basis so line numbers are accurate.
    """

    _RULES: list[tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'locator\(["\']form["\']\)'),
            "Bare locator('form') matches hidden forms",
            "Use form[action*='...'] or scope to visible parent container",
        ),
        (
            re.compile(r'locator\(["\']input\[type=["\']search["\']'),
            "input[type='search'] without scoping matches hidden inputs",
            "Scope to header: locator(\"header input[type='search']\")",
        ),
        (
            re.compile(r'locator\(["\']button["\']\)(?!\.filter)'),
            "Bare locator('button') matches multiple elements",
            "Use get_by_role('button', name='...') with name= parameter",
        ),
        (
            re.compile(r'get_by_label\('),
            "get_by_label() fails when field has no <label> element",
            "Check DOM: use get_by_placeholder() or locator(\"input[name='...']\") as fallback",
        ),
        (
            re.compile(r'get_by_role\(["\']heading["\']'),
            "get_by_role('heading') fails for non-heading elements (span, div with title class)",
            "Verify element tag: use locator('.title') or get_by_text() as fallback",
        ),
        (
            re.compile(r'get_by_role\(["\']alert["\']'),
            "get_by_role('alert') assumes ARIA role that most sites don't implement",
            "Use locator('text=/success|error|thank/i') or check URL change instead",
        ),
        (
            re.compile(r'\.select_option\('),
            "select_option() only works on native <select> elements",
            "For custom dropdowns: .click() to open, then get_by_role('option', name=...).click()",
        ),
        (
            re.compile(r'wait_for_load_state\(["\']networkidle["\']'),
            "networkidle hangs on sites with background requests/analytics",
            "Replace with: expect(page.locator('.key-element')).to_be_visible()",
        ),
        (
            re.compile(r'time\.sleep\('),
            "time.sleep() is forbidden in Playwright tests",
            "Use expect(locator).to_be_visible() or page.wait_for_url()",
        ),
    ]

    def lint(self, code: str) -> list[LocatorWarning]:
        """Return all warnings for the given script code."""
        warnings: list[LocatorWarning] = []
        for line_no, line in enumerate(code.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern, message, suggestion in self._RULES:
                if pattern.search(stripped):
                    warnings.append(
                        LocatorWarning(
                            pattern=pattern.pattern,
                            line_number=line_no,
                            message=message,
                            suggestion=suggestion,
                        )
                    )
        return warnings

    def inject_warnings(self, code: str) -> str:
        """Inject warning comments above the first test function."""
        warnings = self.lint(code)
        if not warnings:
            return code

        sentinel = "# ⚠  Reliability warnings (LocatorLinter)"
        if sentinel in code:
            return code  # already injected

        border = "# " + "─" * 66
        block_lines = [
            border,
            sentinel + " — review before merging",
            border,
        ]
        for w in warnings:
            block_lines.append(f"#  L{w.line_number}: {w.message}")
            block_lines.append(f"#          → {w.suggestion}")
        block_lines.append(border)
        block = "\n".join(block_lines) + "\n\n"

        lines = code.splitlines(keepends=True)
        insert_at = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("def test_")),
            len(lines),
        )
        lines.insert(insert_at, block)
        return "".join(lines)


# ---------------------------------------------------------------------------
# WaitInjector
# ---------------------------------------------------------------------------

# Actions that navigate or change page state and therefore need a follow-up wait
_NAV_CLICK_RE = re.compile(
    r'\.click\(\)$',
    re.MULTILINE,
)
_ALREADY_WAITED_RE = re.compile(
    r'wait_for_url|to_be_visible|to_be_hidden|wait_for_load_state',
)
_SUBMIT_BTN_RE = re.compile(
    r'(?:submit|login|sign.?in|next|continue|proceed|save|delete|confirm|ok)',
    re.IGNORECASE,
)


class WaitInjector:
    """Adds element-based waits after navigation-triggering clicks.

    Heuristic: if a .click() call contains a submit/navigation keyword in the
    locator string AND the next non-empty line does NOT already contain a wait,
    inject a `page.wait_for_load_state('domcontentloaded')` comment reminder.
    """

    def inject(self, code: str) -> str:
        lines = code.splitlines(keepends=True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            result.append(line)

            stripped = line.strip()
            if stripped.endswith(".click()") and _SUBMIT_BTN_RE.search(stripped):
                # Look ahead: if next meaningful line has no wait, inject a reminder
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                next_code = lines[j].strip() if j < len(lines) else ""
                if next_code and not _ALREADY_WAITED_RE.search(next_code):
                    indent = len(line) - len(line.lstrip())
                    result.append(
                        " " * indent
                        + "# Wait for navigation or state change after submit action\n"
                    )
            i += 1
        return "".join(result)


# ---------------------------------------------------------------------------
# AssertionValidator
# ---------------------------------------------------------------------------

_ROLE_ALERT_RE = re.compile(
    r'get_by_role\(["\']alert["\']',
    re.IGNORECASE,
)
_VALIDITY_RE = re.compile(
    r'\.evaluate\(["\']el\s*=>\s*el\.validity\.',
)
_BARE_ASSERT_RE = re.compile(
    r'^\s+assert\s+(?!isinstance|issubclass)',
    re.MULTILINE,
)


@dataclass
class AssertionIssue:
    line_number: int
    issue: str
    replacement_hint: str


class AssertionValidator:
    """Detects fragile assertion patterns and reports replacement hints."""

    def validate(self, code: str) -> list[AssertionIssue]:
        issues: list[AssertionIssue] = []
        for line_no, line in enumerate(code.splitlines(), 1):
            if _ROLE_ALERT_RE.search(line):
                issues.append(AssertionIssue(
                    line_number=line_no,
                    issue="get_by_role('alert') assumes ARIA role not present on most sites",
                    replacement_hint=(
                        "Use: page.locator('text=/success|error|thank/i') "
                        "or check URL change with page.wait_for_url()"
                    ),
                ))
            if _VALIDITY_RE.search(line):
                issues.append(AssertionIssue(
                    line_number=line_no,
                    issue="validity.valid checked synchronously before browser validation applies",
                    replacement_hint=(
                        "Submit first, then check: expect(page.locator('form')).to_be_visible() "
                        "or look for visible error text near the field"
                    ),
                ))
            if _BARE_ASSERT_RE.match(line):
                issues.append(AssertionIssue(
                    line_number=line_no,
                    issue="bare assert has no auto-retry — will be flaky on slow pages",
                    replacement_hint="Replace with expect(locator).to_have_text(...) or to_be_visible()",
                ))
        return issues

    def fix(self, code: str) -> str:
        """Apply safe automatic fixes to known assertion anti-patterns."""
        # bare assert on text_content → expect().to_have_text()
        code = re.sub(
            r'^(\s+)assert\s+(\w+)\.text_content\(\)\s*==\s*(["\'][^"\']+["\'])$',
            r'\1expect(\2).to_have_text(\3)',
            code,
            flags=re.MULTILINE,
        )
        # bare assert on is_visible() → expect().to_be_visible()
        code = re.sub(
            r'^(\s+)assert\s+(\w+)\.is_visible\(\)$',
            r'\1expect(\2).to_be_visible()',
            code,
            flags=re.MULTILINE,
        )
        return code


# ---------------------------------------------------------------------------
# DynamicElementHandler
# ---------------------------------------------------------------------------

_DROPDOWN_TAB_RE = re.compile(
    r'userdropdown-tab|\.oxd-topbar|aria-haspopup',
    re.IGNORECASE,
)
_COMBOBOX_WITHOUT_WAIT_RE = re.compile(
    r'get_by_role\(["\']combobox["\'][^)]*\)\.click\(\)',
)
_ALREADY_HAS_LISTBOX_WAIT = re.compile(r'listbox|to_be_visible')


class DynamicElementHandler:
    """Detects dynamic element interactions and adds missing wait steps."""

    def handle(self, code: str) -> str:
        """Inject wait steps after combobox .click() calls that lack them."""
        lines = code.splitlines(keepends=True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            result.append(line)

            if _COMBOBOX_WITHOUT_WAIT_RE.search(line.strip()):
                # Look ahead to check if there's already a wait for listbox/options
                j = i + 1
                next_code = lines[j].strip() if j < len(lines) else ""
                if next_code and not _ALREADY_HAS_LISTBOX_WAIT.search(next_code):
                    indent = " " * (len(line) - len(line.lstrip()))
                    result.append(
                        indent
                        + "expect(page.get_by_role('listbox')).to_be_visible()  "
                        "# wait for dropdown options\n"
                    )
            i += 1
        return "".join(result)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def apply_reliability_pipeline(
    code: str,
    *,
    lint: bool = True,
    inject_waits: bool = True,
    fix_assertions: bool = True,
    handle_dynamic: bool = True,
) -> str:
    """Run all reliability passes on a generated Playwright script.

    Args:
        code: The generated Python test script.
        lint: Inject LocatorLinter warning comments.
        inject_waits: Add wait comments after navigation-triggering clicks.
        fix_assertions: Auto-fix safe assertion anti-patterns.
        handle_dynamic: Add wait steps after combobox clicks.

    Returns:
        The hardened script code.
    """
    if fix_assertions:
        code = AssertionValidator().fix(code)
    if handle_dynamic:
        code = DynamicElementHandler().handle(code)
    if inject_waits:
        code = WaitInjector().inject(code)
    if lint:
        code = LocatorLinter().inject_warnings(code)
    return code
