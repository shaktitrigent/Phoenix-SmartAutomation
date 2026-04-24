"""Automation script generator — writes intelligence-generated Playwright scripts to disk.

Phase 4 improvements
--------------------
- Python syntax validation (ast.parse) before writing — bad scripts are rejected early
  with a clear error rather than silently saved.
- Extended normalizer fixes common LLM output mistakes:
    * to_have_url(containing=...)  → to_have_url(re.compile(...))
    * page.wait_for_selector(...)  → expect(locator).to_be_visible()
    * time.sleep(...)              → removed with a # TODO comment
    * bare assert                  → flagged for review
    * Missing imports auto-added   (re, pytest, Page, expect)
"""

from __future__ import annotations

import ast
import re as re_module
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.storage.models import TestType


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
            results.append({
                "name": test.get("name", f"automation_test_{idx}"),
                "description": test.get("description", user_story),
                "script_path": str(script_path),
                "test_type": TestType.AUTOMATION.value,
                "test_category": test_category,
                "locators": test.get("locators", []),
                "tags": test.get("tags", ["automation", "generated"]),
            })
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
            raise RuntimeError(
                f"Generated script has a syntax error: {exc}\n\n"
                "The LLM may have returned incomplete code. Try regenerating."
            ) from exc

        safe_name = _slugify(test.get("name", f"test_{idx}"))
        filename = f"test_{idx:03d}_{safe_name}.py"
        path = self.output_dir / filename
        path.write_text(normalised, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Normaliser
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(code: str) -> str:
        """Apply a sequence of fixes to common LLM output problems."""
        code = _fix_url_containing(code)
        code = _fix_wait_for_selector(code)
        code = _fix_time_sleep(code)
        code = _fix_bare_assert(code)
        code = _ensure_imports(code)
        return code


# ------------------------------------------------------------------
# Fix functions (module-level for clarity)
# ------------------------------------------------------------------

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
    pattern = re_module.compile(r'page\.wait_for_selector\(([^)]+)\)')
    def replacer(m):
        arg = m.group(1).strip()
        return f'expect(page.locator({arg})).to_be_visible()'
    return pattern.sub(replacer, code)


def _fix_time_sleep(code: str) -> str:
    """Remove time.sleep() calls and add a # TODO comment."""
    pattern = re_module.compile(r'time\.sleep\s*\([^)]*\)\s*\n?')
    result = pattern.sub('# TODO: replace sleep with expect() assertion\n', code)
    # Also remove the now-unused "import time" if it was only there for sleep
    if 'time.sleep' not in result and re_module.search(r'import time\s*\n', result):
        result = re_module.sub(r'import time\s*\n', '', result, count=1)
    return result


def _fix_bare_assert(code: str) -> str:
    """Flag bare assert statements that should use expect()."""
    pattern = re_module.compile(r'^(\s+)(assert\s+(?!isinstance|issubclass).+)$', re_module.MULTILINE)
    def replacer(m):
        indent, stmt = m.group(1), m.group(2)
        return f'{indent}# NOTE: prefer expect() over bare assert\n{indent}{stmt}'
    return pattern.sub(replacer, code)


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
    # Insert after the module docstring (first non-blank, non-# line)
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


def _slugify(name: str, max_len: int = 60) -> str:
    slug = re_module.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:max_len] if slug else "automation_test"
