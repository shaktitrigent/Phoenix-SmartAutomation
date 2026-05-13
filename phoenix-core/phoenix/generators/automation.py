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

from phoenix.execution.reliability import apply_reliability_pipeline
from phoenix.generators.clean_code import apply_clean_code_pipeline
from phoenix.storage.models import TestType

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

    def __init__(self, output_dir: str = "./test_results") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

        normalised = self._normalise(script_code)

        # Validate Python syntax before writing
        try:
            ast.parse(normalised)
        except SyntaxError as exc:
            # Dump the broken script next to the output dir so it can be inspected
            dump_path = self.output_dir / f"_syntax_error_dump_{idx}.py"
            dump_path.write_text(normalised, encoding="utf-8")
            raise RuntimeError(
                f"Generated script has a syntax error: {exc}\n\n"
                f"Broken script saved to: {dump_path}\n"
                "Open that file to inspect what the LLM returned."
            ) from exc

        safe_name = _slugify(test.get("name", f"test_{idx}"))
        filename = f"test_{idx:03d}_{safe_name}.py"
        path = self.output_dir / filename
        path.write_text(normalised, encoding="utf-8")
        return path

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
    """Remove markdown ```python ... ``` fences an LLM may wrap the script in."""
    code = code.strip()
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


def _inject_locator_warnings(code: str) -> str:
    """Scan the normalised code for residual anti-patterns.

    Any pattern that survived the auto-fix passes is flagged as a warning
    comment block inserted immediately before the first test function.
    This gives the developer a clear signal during code review without
    breaking syntax or failing tests.
    """
    triggered = [msg for pattern, msg in _ANTI_PATTERNS if pattern.search(code)]
    if not triggered:
        return code

    _SENTINEL = "# ⚠  Locator quality warnings"
    if _SENTINEL in code:
        # Warning block already present — don't duplicate on re-runs
        return code

    border = "# " + "─" * 66
    block = (
        border
        + "\n"
        + _SENTINEL
        + " — review before merging to CI\n"
        + border
        + "\n"
        + "".join(f"#    • {w}\n" for w in triggered)
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
# Import ensurer
# ===========================================================================


def _ensure_imports(code: str) -> str:
    """Add missing standard imports."""
    needed = {
        "import re": "re.compile" in code,
        "import pytest": "def test_" in code,
        "from playwright.sync_api import Page, expect": "expect(" in code or "Page" in code,
    }
    missing = [imp for imp, needed_flag in needed.items() if needed_flag and imp not in code]
    if not missing:
        return code
    lines = code.splitlines(keepends=True)
    insert_at = 0
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped.startswith(('"""', "'''")):
            in_docstring = True
            insert_at = i + 1
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                in_docstring = False
            continue
        if in_docstring:
            insert_at = i + 1
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
            continue
        if stripped.startswith("import") or stripped.startswith("from"):
            insert_at = i
            break
        if stripped and not stripped.startswith("#"):
            insert_at = i
            break
    injection = "".join(f"{imp}\n" for imp in missing)
    lines.insert(insert_at, injection)
    return "".join(lines)


# ===========================================================================
# Helpers
# ===========================================================================


def _slugify(name: str, max_len: int = 60) -> str:
    slug = re_module.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:max_len] if slug else "automation_test"
