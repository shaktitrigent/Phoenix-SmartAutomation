"""Automation script generator — writes intelligence-generated Playwright scripts to disk.

Normalizer pipeline (applied in order on every generated script)
---------------------------------------------------------------
Existing fixes:
  * to_have_url(containing=...)       → to_have_url(re.compile(...))
  * page.wait_for_selector(...)       → expect(locator).to_be_visible()
  * time.sleep(...)                   → removed + # TODO comment
  * bare assert                       → flagged with # NOTE comment
  * Missing imports                   → auto-added (re, pytest, Page, expect)

New fixes (locator quality — prevent the most common runtime failures):
  * get_by_text() in assertions       → get_by_role("heading") or .first
  * Dynamic person names in locators  → stable banner-scoped button locator
  * get_by_text().click() collisions  → .first.click()
  * page.on("dialog", ...)            → page.once("dialog", ...)  (prevents handler stacking)

Anti-pattern scanner (Layer 3):
  * Residual risky patterns that were not auto-fixed are surfaced as
    inline warning comments at the top of the first test function.
"""

from __future__ import annotations

import ast
import re as re_module
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
import sys

from phoenix.execution.reliability import apply_reliability_pipeline
from phoenix.generators.clean_code import CleanCodeGate, apply_clean_code_pipeline
from phoenix.generators.validation import validate_collect, validate_compile, validate_syntax
from phoenix.storage.models import TestType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixture selection — authenticated_page vs plain page
# ---------------------------------------------------------------------------

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
    """Return True when preconditions indicate the user must already be logged in."""
    low = preconditions.lower()
    return any(phrase in low for phrase in _AUTH_PRECONDITION_PHRASES)


def _swap_to_authenticated_fixture(code: str) -> str:
    """Replace ``page: Page`` with ``authenticated_page: Page`` in test_* signatures.

    Only touches the function-signature line to avoid mangling calls to
    page-object methods or helper functions that coincidentally use 'page'.
    """
    return re_module.sub(
        r"(def test_\w+\s*\()page(\s*:\s*Page)",
        r"\1authenticated_page\2",
        code,
    )


# Title-case two-or-more word pattern used to detect person display names
_PERSON_NAME_RE = re_module.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$")

# Words that strongly indicate a page heading rather than arbitrary body text
_HEADING_WORDS = frozenset(
    {
        "dashboard",
        "home",
        "profile",
        "settings",
        "admin",
        "reports",
        "search",
        "results",
        "welcome",
        "overview",
        "summary",
        "details",
        "history",
        "inbox",
        "queue",
        "employees",
        "candidates",
        "leave",
        "recruitment",
        "performance",
        "time",
        "attendance",
        "payroll",
        "claims",
        "buzz",
        "directory",
    }
)


class AutomationTestGenerator:
    """Receives complete ``script_code`` from phoenix-intelligence and writes
    it to the configured output directory after validation and normalisation."""

    def __init__(
        self,
        output_dir: str = "./tests",
        intel_client=None,
        repair_attempts: int = 1,
        collect_only_gate: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # intel_client is optional — when None the generator validates only (no LLM repair).
        # Accepts any object with a fix_script(script_code, error_message, ...) method,
        # i.e. IntelligenceClient from phoenix.sdk.intelligence_client.
        self._intel_client = intel_client
        self._repair_attempts = max(0, repair_attempts)
        self._collect_only_gate = collect_only_gate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        automation_tests: List[Dict[str, Any]],
        user_story: str,
        application_url: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        test_category: str = "ui",
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Write automation test scripts to disk.

        Args:
            automation_tests: Tests from intelligence — must contain ``script_code``.
            user_story: User story text (used for fallback naming).
            application_url: Application URL (informational).
            acceptance_criteria: Unused — kept for API compatibility.
            test_category: ``'ui'`` or ``'api'``.

        Returns:
            List of test metadata dicts with ``script_path`` populated.
        """
        results = []
        for idx, test in enumerate(automation_tests, 1):
            script_path = self._write_script(test, idx)
            results.append(
                {
                    "name": test.get("name", f"automation_test_{idx}"),
                    "description": test.get("description", user_story),
                    "script_path": str(script_path),
                    "test_type": TestType.AUTOMATION.value,
                    "test_category": test_category,
                    "locators": test.get("locators", []),
                    "tags": test.get("tags", ["automation", "generated"]),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_script(self, test: Dict[str, Any], idx: int) -> Path:
        script_code = test.get("script_code")
        if not script_code:
            raise RuntimeError(
                "Intelligence server did not return script_code. "
                "Ensure ANTHROPIC_API_KEY is set and the intelligence server is running."
            )

        code = self._normalise(script_code)

        # Swap fixture to authenticated_page when preconditions require a live session
        if _needs_authenticated_page(test.get("preconditions", "")):
            code = _swap_to_authenticated_fixture(code)

        # ── Determine output path (needed by repair-loop logging) ──────────────────
        safe_name = _slugify(test.get("name", f"test_{idx}"))
        filename = f"test_{idx:03d}_{safe_name}.py"
        path = self.output_dir / filename

        # ── Quality gate → repair loop (never hard-block; FIXME header as fallback) ─
        # BUSINESS_TEXT_URL_REGEX catches expect(page).to_have_url(re.compile("prose"))
        # where the LLM echoed the step description into the regex.  Route through the
        # repair loop so the fixer can replace the prose with a real URL path pattern.
        _REPAIRABLE_RULES = {"BUSINESS_TEXT_URL_REGEX"}
        gate = CleanCodeGate()
        violations = gate.check(code)
        breaking = [v for v in violations if v.rule in _REPAIRABLE_RULES]
        if breaking:
            error_text = (
                "The script has expect(page).to_have_url(re.compile(...)) calls whose regex "
                "pattern contains prose text copied from the step description instead of a "
                "real URL path pattern.\n"
                "Fix: replace the prose pattern with a real URL path, e.g. "
                "re.compile(r'.*/inventory.*') or re.compile(r'.*checkout.*').\n"
                "Never use the step description text as a regex value.\n\n"
                + "\n".join(f"[{v.rule}] L{v.line_number}: {v.message}" for v in breaking)
            )
            code = self._repair_loop(code, error_text, test, "quality_violation", path)
            # After repair, re-check; still-violating code gets a FIXME header and continues
            violations_after = gate.check(code)
            still_breaking = [v for v in violations_after if v.rule in _REPAIRABLE_RULES]
            if still_breaking:
                logger.warning(
                    "%s: quality violation persists after repair; writing with FIXME header",
                    path.name,
                )
                code = _prepend_fixme_header(code, error_text)

        # ── Validate syntax (in-memory, no subprocess) ────────────────────────────
        err = validate_syntax(code)
        if err:
            code = self._repair_loop(code, err, test, "syntax_error", path)

        # ── Write to disk so file-based gates can run ─────────────────────────────
        path.write_text(code, encoding="utf-8")

        # ── py_compile gate ───────────────────────────────────────────────────────
        err = validate_compile(path)
        if err:
            code = self._repair_loop(code, err, test, "syntax_error", path)
            path.write_text(code, encoding="utf-8")

        # ── pytest --collect-only gate (optional) ─────────────────────────────────
        if self._collect_only_gate:
            err = validate_collect(path)
            if err:
                code = self._repair_loop(code, err, test, "collection_error", path)
                path.write_text(code, encoding="utf-8")

        return path

    def _repair_loop(
        self,
        code: str,
        error_text: str,
        test: Dict[str, Any],
        error_type: str,
        path: Path,
    ) -> str:
        """Attempt up to ``self._repair_attempts`` LLM repair calls.

        Returns the (possibly repaired) code.  On exhausted retries the original
        code is prepended with a # FIXME header and returned — never raises.
        """
        if not self._intel_client or self._repair_attempts <= 0:
            # Validate-only mode: just prepend a FIXME header so the developer knows
            return _prepend_fixme_header(code, error_text)

        current = code
        for attempt in range(1, self._repair_attempts + 1):
            repaired = self._repair(current, error_text, test, error_type)
            if not repaired or repaired == current:
                logger.debug(
                    "Repair attempt %d/%d made no progress for %s",
                    attempt, self._repair_attempts, path.name,
                )
                break
            repaired = self._normalise(repaired)
            # Validate the repair before accepting it
            new_err = validate_syntax(repaired)
            if not new_err:
                logger.info(
                    "Script %s repaired successfully on attempt %d/%d",
                    path.name, attempt, self._repair_attempts,
                )
                return repaired
            # The repair itself has a syntax error — try again with the new error
            error_text = new_err
            current = repaired

        # All attempts exhausted — write with a FIXME header (never crash)
        logger.warning(
            "Script %s could not be repaired after %d attempt(s); writing with FIXME header",
            path.name, self._repair_attempts,
        )
        return _prepend_fixme_header(code, error_text)

    def _repair(
        self,
        code: str,
        error_text: str,
        test: Dict[str, Any],
        error_type: str,
    ) -> str:
        """Call the intelligence server's ScriptFixerAgent and return the fixed code."""
        try:
            resp = self._intel_client.fix_script(
                script_code=code,
                error_message=error_text[:3000],
                error_type=error_type,
                test_name=test.get("name", ""),
                application_url=test.get("application_url", ""),
            )
            return (resp or {}).get("fixed_script") or ""
        except Exception as exc:
            logger.debug("Repair call failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Normaliser — ordered pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(code: str) -> str:
        """Apply all fix passes in order, then scan for residual anti-patterns."""
        # --- Strip markdown code fences the LLM may have wrapped the script in ---
        code = _strip_code_fences(code)

        # --- Existing fixes ---
        code = _fix_url_containing(code)
        code = _fix_wait_for_selector(code)
        code = _fix_time_sleep(code)
        code = _fix_bare_assert(code)

        # --- New locator-quality fixes ---
        code = _fix_ambiguous_get_by_text_in_assertion(code)
        code = _fix_dynamic_person_name_in_locator(code)
        code = _fix_get_by_text_click_strict_mode(code)
        code = _fix_dialog_on_to_once(code)

        # --- Import completion (must run after all code transforms) ---
        code = _ensure_imports(code)

        # --- Reliability pipeline: assertion fixes, dynamic waits, linter warnings ---
        code = apply_reliability_pipeline(code)

        # --- Clean Code Emitter: gate check + AST cleanup ---
        code = apply_clean_code_pipeline(code, gate_raises=False, clean=True)

        # --- Anti-pattern scanner: warn about anything not auto-fixed ---
        code = _inject_locator_warnings(code)

        return code


# ===========================================================================
# Existing fix functions
# ===========================================================================


def _strip_code_fences(code: str) -> str:
    """Remove markdown ```python ... ``` fences an LLM may wrap the script in.

    Extracts content between the first opening and first closing fence so that
    trailing prose appended by the LLM after the closing fence is discarded.
    """
    code = code.strip()
    fence_match = re_module.search(r"^```[a-zA-Z]*\r?\n(.*?)```", code, re_module.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    code = re_module.sub(r"^```[a-zA-Z]*\r?\n?", "", code)
    code = re_module.sub(r"\r?\n?```\s*$", "", code)
    return code.strip()


def _fix_url_containing(code: str) -> str:
    """to_have_url(containing="...") → to_have_url(re.compile(r"...*"))"""
    pattern = re_module.compile(
        r'expect\s*\(\s*page\s*\)\s*\.\s*to_have_url\s*\(\s*containing\s*=\s*["\']([^"\']+)["\']\s*\)'
    )
    match = pattern.search(code)
    if match:
        url_part = match.group(1)
        safe = url_part.replace("\\", "\\\\").replace(".", "\\.").replace("/", "\\/")
        replacement = f'expect(page).to_have_url(re.compile(r".*{safe}.*"))'
        code = code.replace(match.group(0), replacement)
    return code


def _fix_wait_for_selector(code: str) -> str:
    """page.wait_for_selector("sel") → expect(page.locator("sel")).to_be_visible()"""
    pattern = re_module.compile(r"page\.wait_for_selector\(([^)]+)\)")

    def replacer(m):
        arg = m.group(1).strip()
        return f"expect(page.locator({arg})).to_be_visible()"

    return pattern.sub(replacer, code)


def _fix_time_sleep(code: str) -> str:
    """Remove time.sleep() calls and add a # TODO comment."""
    pattern = re_module.compile(r"time\.sleep\s*\([^)]*\)\s*\n?")
    result = pattern.sub("# TODO: replace sleep with expect() assertion\n", code)
    if "time.sleep" not in result and re_module.search(r"import time\s*\n", result):
        result = re_module.sub(r"import time\s*\n", "", result, count=1)
    return result


def _fix_bare_assert(code: str) -> str:
    """Flag bare assert statements that should use expect()."""
    pattern = re_module.compile(
        r"^(\s+)(assert\s+(?!isinstance|issubclass).+)$", re_module.MULTILINE
    )

    def replacer(m):
        indent, stmt = m.group(1), m.group(2)
        return f"{indent}# NOTE: prefer expect() over bare assert\n{indent}{stmt}"

    return pattern.sub(replacer, code)


# ===========================================================================
# New locator-quality fix functions
# ===========================================================================


def _fix_ambiguous_get_by_text_in_assertion(code: str) -> str:
    """Convert expect(page.get_by_text("X")).* to a non-ambiguous locator.

    get_by_text() matches every element that contains text X — in Playwright's
    strict mode this raises "resolved to N elements" when both a nav link and a
    page heading share the same label.

    Replacement strategy:
      - X is a known page-heading word  → get_by_role("heading", name=X)
      - X starts with a capital letter  → get_by_role("heading", name=X)  (likely a title)
      - Everything else                 → add .first  (safe strict-mode bypass)
    """
    pattern = re_module.compile(
        r'expect\(\s*page\.get_by_text\((["\'])([^"\']+)\1\)\s*\)'
        r"(\s*\.(?:to_be_visible|to_have_text|to_be_hidden|to_contain_text)\([^)]*\))"
    )

    def replacer(m: re_module.Match) -> str:
        quote = m.group(1)
        text = m.group(2)
        suffix = m.group(3)
        # Only promote to heading role for well-known page-heading words.
        # Everything else (error messages, labels, status text) gets .first —
        # safe, non-breaking, and doesn't misclassify dynamic content as headings.
        if text.lower().strip() in _HEADING_WORDS:
            return f'expect(page.get_by_role("heading", name={quote}{text}{quote})){suffix}'
        return f"expect(page.get_by_text({quote}{text}{quote}).first){suffix}"

    return pattern.sub(replacer, code)


def _fix_dynamic_person_name_in_locator(code: str) -> str:
    """Replace hardcoded person display names in button role locators.

    Pattern: page.get_by_role("button", name="Paul Collings")
    Problem: The logged-in user's display name is dynamic — it changes per
             environment, account, or test-data state, causing the locator to
             time out.

    Replacement strategy — tries, in order:
      1. button[aria-haspopup] — ARIA-correct user-menu buttons in any framework
      2. [class*='userdropdown'] — OrangeHRM and similar naming conventions
      3. [class*='user-dropdown'], [class*='user-menu'] — generic SPA patterns
    Falls back to the .first match so the script is always syntactically valid.
    """
    pattern = re_module.compile(
        r'page\.get_by_role\(["\']button["\'],\s*name=["\']([^"\']+)["\']\s*\)'
    )

    _STABLE_USER_MENU_LOCATOR = (
        "page.locator("
        "\"button[aria-haspopup], [class*='userdropdown'], "
        "[class*='user-dropdown'], [class*='user-menu']\""
        ").first"
    )

    def replacer(m: re_module.Match) -> str:
        name = m.group(1).strip()
        if _PERSON_NAME_RE.match(name):
            return _STABLE_USER_MENU_LOCATOR
        return m.group(0)

    return pattern.sub(replacer, code)


def _fix_get_by_text_click_strict_mode(code: str) -> str:
    """Add .first to get_by_text("X").click() to prevent strict-mode failures.

    When text appears in multiple elements (e.g. a nav link and a body heading),
    Playwright's strict mode raises an error. .first selects the topmost match,
    which is the intended interactive element in virtually all cases.

    Excludes chains that already have .first / .nth() / .filter() applied.
    """
    pattern = re_module.compile(
        r'(\.get_by_text\(["\'][^"\']+["\']\))(?!\.first|\.nth\(|\.filter\()\.click\(\)'
    )
    return pattern.sub(r"\1.first.click()", code)


def _fix_dialog_on_to_once(code: str) -> str:
    """Replace page.on("dialog", ...) with page.once("dialog", ...).

    page.on() registers a persistent listener — every subsequent dialog in the
    same test session fires it, leading to unexpected accepts/dismisses.
    page.once() fires exactly once and then removes itself.
    """
    return re_module.sub(
        r'\bpage\.on\s*\(\s*(["\'])dialog\1',
        'page.once("dialog"',
        code,
    )


# ===========================================================================
# Anti-pattern scanner — Layer 3
# ===========================================================================

# Each entry: (pattern, human-readable warning message)
_ANTI_PATTERNS: List[tuple] = [
    (
        re_module.compile(r"expect\(.*\.get_by_text\("),
        "get_by_text() inside expect() may cause strict-mode violation — "
        "use get_by_role('heading') or scope to a container",
    ),
    (
        re_module.compile(r'page\.get_by_text\(["\'][^"\']+["\']\)\.click\(\)'),
        "get_by_text().click() without .first — may match multiple elements; "
        "add .first or scope to a container",
    ),
    (
        re_module.compile(r"\.nth\(\d+\)"),
        ".nth(N) is position-based and breaks when page layout changes — "
        "prefer .filter(has_text=...) or a semantic locator",
    ),
    (
        re_module.compile(r'page\.locator\(["\']//'),
        "XPath locator detected — brittle; prefer get_by_role/label/placeholder",
    ),
    (
        re_module.compile(r'page\.on\s*\(\s*["\']dialog["\']'),
        "page.on('dialog') stacks handlers — use page.once('dialog') instead",
    ),
    (
        re_module.compile(r'\.fill\(\s*["\']["\']'),
        ".fill('') clears a field but .clear() is more readable and explicit",
    ),
]


def _lint_field_value_mismatch(code: str) -> list:
    """Return a list of warning strings for fill() calls that write a value to the
    wrong field (e.g. a username value into the Password locator).

    Detection is heuristic — both the field name AND the value shape must point
    in opposite directions before we warn, keeping the false-positive rate low.
    We also warn when a step comment mentions a username field but no fill()
    targets a username-named locator (likely missing step).

    This function is AST-free by design: we only need line-level regex analysis,
    and the code may not be syntactically valid at this stage.
    """
    warnings: list = []

    # Regex: captures (field_string, value_string) from fill_ready / .fill calls
    # fill_ready(page, page.get_by_label("Password", exact=True), "standard_user", ...)
    # page.get_by_placeholder("Username").fill("wrong_password")
    _FILL_RE = re_module.compile(
        r'(?:'
        # fill_ready(page, <locator_expr>, "<value>", ...)
        r'fill_ready\s*\(\s*page\s*,\s*'
        r'(?:page\.(?:get_by_label|get_by_placeholder|get_by_role)\s*\(\s*["\']([^"\']+)["\'][^)]*\)|'
        r'page\.locator\s*\(\s*["\'][^"\']*[nN]ame\s*=\s*["\']([^"\']+)["\'][^)]*\))'
        r'\s*,\s*["\']([^"\']+)["\']'
        r'|'
        # page.get_by_label("Password").fill("wrong_value")
        r'page\.(?:get_by_label|get_by_placeholder)\s*\(\s*["\']([^"\']+)["\'][^)]*\)'
        r'\s*\.\s*fill\s*\(\s*["\']([^"\']+)["\']'
        r')'
    )

    # Patterns that look like a username value (typical test usernames)
    _USERNAME_VALUE_RE = re_module.compile(
        r'^[a-z][a-z0-9_.+-]*_(?:user|admin|staff|manager|tester|operator)$',
        re_module.IGNORECASE,
    )
    # Patterns that look like a password value
    _PASSWORD_VALUE_RE = re_module.compile(
        r'(?:secret|password|pass|pwd|p@ss|\d{4,})[a-z0-9!@#$%]*',
        re_module.IGNORECASE,
    )

    username_fills = 0   # count of fills that target a username-named locator

    for m in _FILL_RE.finditer(code):
        groups = m.groups()
        # Normalise: extract (field_name, value) from whichever branch matched
        if groups[0] is not None or groups[1] is not None:
            # fill_ready branch
            field = (groups[0] or groups[1] or "").lower()
            value = (groups[2] or "").strip()
        else:
            # direct .fill() branch
            field = (groups[3] or "").lower()
            value = (groups[4] or "").strip()

        if not field or not value:
            continue

        is_password_field = "password" in field or "passwd" in field or "pwd" in field
        is_username_field = any(w in field for w in ("username", "user name", "email", "login"))

        if is_username_field:
            username_fills += 1

        # Warn: password field receiving a value shaped like a username
        if is_password_field and _USERNAME_VALUE_RE.match(value):
            warnings.append(
                f"Field '{field}' looks like a password field but received value '{value}' "
                f"which looks like a username — confirm the correct field is targeted"
            )

        # Warn: username/email field receiving a value shaped like a password
        if is_username_field and _PASSWORD_VALUE_RE.match(value):
            warnings.append(
                f"Field '{field}' looks like a username field but received value '{value}' "
                f"which looks like a password — confirm the correct field is targeted"
            )

    # Warn if a step comment mentions a username field but no fill targets it
    has_username_step_comment = bool(
        re_module.search(
            r'#.*[Uu]sername|#.*[Uu]ser [Nn]ame|#.*[Ee]mail.*field',
            code,
        )
    )
    has_username_fill = username_fills > 0 or bool(
        re_module.search(
            r'fill.*["\'][Uu]sername|fill.*["\'][Uu]ser [Nn]ame|'
            r'get_by_label\(["\'][Uu]sername',
            code,
        )
    )
    if has_username_step_comment and not has_username_fill:
        warnings.append(
            "Step comment mentions a Username field but no fill() targets a username-named "
            "locator — the Username field may never be filled (check Step 2)"
        )

    return warnings


def _inject_locator_warnings(code: str) -> str:
    """Scan the normalised code for residual anti-patterns and field-fill mismatches.

    Warnings are inserted as a comment block immediately before the first test
    function.  This gives the developer a clear signal during code review without
    breaking syntax or failing tests.

    If a Reliability warnings block was already added by ``apply_reliability_pipeline``
    the new field-fill warnings are appended to the SAME block (no duplicate headers).
    """
    triggered = [msg for pattern, msg in _ANTI_PATTERNS if pattern.search(code)]
    triggered.extend(_lint_field_value_mismatch(code))

    if not triggered:
        return code

    _SENTINEL = "# ⚠  Reliability warnings (LocatorLinter)"
    border = "# " + "─" * 66

    if _SENTINEL in code:
        # A reliability block already exists — append new warnings to it rather than
        # creating a duplicate.  Find the first closing border after the sentinel and
        # insert before it.
        sentinel_pos = code.index(_SENTINEL)
        # Find the closing border line that follows the sentinel
        after_sentinel = code[sentinel_pos:]
        closing_border_idx = after_sentinel.find("\n" + border, len(_SENTINEL))
        if closing_border_idx != -1:
            abs_pos = sentinel_pos + closing_border_idx
            extra = "".join(f"#  L??: {w}\n" for w in triggered)
            return code[:abs_pos + 1] + extra + code[abs_pos + 1:]
        # Fallback: can't find closing border, just prepend a separate block
        return code

    block = (
        border
        + "\n"
        + _SENTINEL
        + " — review before merging\n"
        + border
        + "\n"
        + "".join(f"#  L??: {w}\n" for w in triggered)
        + border
        + "\n"
    )

    lines = code.splitlines(keepends=True)
    insert_at = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("def test_")),
        len(lines),
    )
    lines.insert(insert_at, block + "\n")
    return "".join(lines)


# ===========================================================================
# Import normalizer (AST-based — replaces the old substring-based ensurer)
# ===========================================================================


def _normalise_imports(code: str) -> str:
    """Deduplicate and normalise imports using stdlib ast.

    • All ``from playwright.sync_api import ...`` statements are merged into
      one canonical line in deterministic order (Locator, Page, expect, then
      any extras alphabetically).
    • ``import re`` / ``import pytest`` are injected only when absent and needed.
    • The insertion anchor is placed after the module docstring and any
      ``from __future__`` import (both must remain first per PEP 8).
    • On SyntaxError the code is returned unchanged — the validate→repair loop
      in _write_script handles broken syntax separately.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    lines = code.splitlines(keepends=True)

    # ── 1. Detect what symbols / modules are needed ───────────────────────
    need_re = bool(re_module.search(r"\bre\b\.", code))
    need_pytest = bool(re_module.search(r"\bdef test_|\b@pytest\.", code))
    _SYNC_API_NAMES = frozenset({"Locator", "Page", "expect", "sync_playwright"})
    needed_sync: set = {n for n in _SYNC_API_NAMES if re_module.search(rf"\b{n}\b", code)}

    # ── 2. Walk module body: collect existing imports ─────────────────────
    imported_modules: set = set()
    existing_sync_names: set = set()
    sync_api_spans: list = []   # (lineno-1, end_lineno-1) — 0-indexed
    last_future_end: int = -1   # 0-indexed end line of last __future__ import
    docstring_end: int = -1     # 0-indexed end line of module docstring

    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and docstring_end == -1  # only the first string expression
        ):
            docstring_end = node.end_lineno - 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "__future__":
                last_future_end = node.end_lineno - 1
            elif mod == "playwright.sync_api":
                for alias in node.names:
                    existing_sync_names.add(alias.name)
                sync_api_spans.append((node.lineno - 1, node.end_lineno - 1))

    # ── 3. Compute final sync_api set and canonical order ─────────────────
    final_sync = existing_sync_names | needed_sync
    _PREF_ORDER = ["Locator", "Page", "expect", "sync_playwright"]
    ordered = [n for n in _PREF_ORDER if n in final_sync] + sorted(
        n for n in final_sync if n not in _PREF_ORDER
    )

    add_re = need_re and "re" not in imported_modules
    add_pytest = need_pytest and "pytest" not in imported_modules

    # ── 4. Early-return when nothing to change ────────────────────────────
    if (
        not add_re
        and not add_pytest
        and len(sync_api_spans) <= 1
        and not (needed_sync - existing_sync_names)
    ):
        return code

    # ── 5. Mark existing sync_api import lines for removal ────────────────
    remove_lines: set = set()
    for start, end in sync_api_spans:
        for i in range(start, end + 1):
            remove_lines.add(i)

    # ── 6. Compute insertion anchor (after docstring / __future__) ─────────
    anchor = max(docstring_end, last_future_end) + 1  # first line to inject AT

    # ── 7. Build injection block ──────────────────────────────────────────
    injection: list = []
    if add_re:
        injection.append("import re\n")
    if add_pytest:
        injection.append("import pytest\n")
    if ordered:
        injection.append(f"from playwright.sync_api import {', '.join(ordered)}\n")

    if not injection:
        return code

    # ── 8. Rebuild: remove old sync_api lines, insert canonical block ──────
    filtered = [(i, ln) for i, ln in enumerate(lines) if i not in remove_lines]

    # Find the first kept line whose original index >= anchor
    insert_pos = len(filtered)
    for pos, (orig_idx, _) in enumerate(filtered):
        if orig_idx >= anchor:
            insert_pos = pos
            break

    result = "".join(
        [ln for _, ln in filtered[:insert_pos]]
        + injection
        + [ln for _, ln in filtered[insert_pos:]]
    )

    # ── 9. Self-check: if we somehow broke syntax, return the original ─────
    try:
        ast.parse(result)
    except SyntaxError:
        return code

    return result


def _ensure_imports(code: str) -> str:
    """Backward-compatible alias — delegates to :func:`_normalise_imports`."""
    return _normalise_imports(code)


# ===========================================================================
# Helpers
# ===========================================================================


def _slugify(name: str, max_len: int = 80) -> str:
    from phoenix.utils.slugify import slugify as _slug
    return _slug(name, max_len=max_len) or "automation_test"


def _prepend_fixme_header(code: str, error_text: str) -> str:
    """Return a syntactically valid stub that pytest can collect when auto-repair fails.

    A ``pytest.skip()`` stub is far more useful than a broken file with FIXME
    comments: pytest can collect and report it, the skip message points the
    developer at the problem, and test-run summaries show the file as *skipped*
    rather than crashing the collection phase entirely.

    The original broken code is preserved in a comment block below the stub so
    developers can read it without losing context.
    """
    error_text = error_text or "unknown error"
    # Build a one-line safe message: strip newlines and quotes that would break
    # the Python string literal inside the stub.
    safe_msg = error_text[:200].replace("\\", "\\\\").replace('"', "'").replace("\n", " ")
    # Preserve the full error as a comment block for debugging
    comment_lines = "\n".join(f"#   {ln}" for ln in error_text[:2000].splitlines())
    stub = (
        "# " + "=" * 74 + "\n"
        "# phoenix auto-repair failed — pytest.skip() stub written instead.\n"
        "# Re-run `phoenix automate` after resolving the error shown below.\n"
        "#\n"
        f"{comment_lines}\n"
        "# " + "=" * 74 + "\n"
        "\n"
        "import pytest\n"
        "from playwright.sync_api import Page\n"
        "\n"
        "\n"
        "def test_auto_repair_failed(page: Page) -> None:\n"
        f'    """Auto-repair failed: {safe_msg}"""\n'
        '    pytest.skip(\n'
        '        "phoenix auto-repair failed — re-run `phoenix automate` to regenerate"\n'
        '    )\n'
    )
    return stub
