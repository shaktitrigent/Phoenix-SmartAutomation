"""ModuleAwareWriter — one consolidated file per application module.

Instead of writing one file per test / locator / manual case, this writer
maintains a single canonical file per module and merges incoming content:

  tests/{module}/test_{module}.py   — all Playwright tests for the module
  locators/{module}.json            — all LocatorBundle entries for the module
  manual_tests/{module}.md          — all manual test cases for the module

Merge semantics
---------------
Tests     : dedup by function name — incoming replaces existing definition.
Locators  : dedup by element_id   — incoming replaces existing entry.
Manual    : append-only by case ID — existing cases are never modified.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TestFunction:
    """A single pytest test function ready to be written into a module file."""

    name: str
    body: str                          # full function block including decorators, def line, and body
    marks: List[str] = field(default_factory=list)   # e.g. ["smoke", "login"]


@dataclass
class LocatorElement:
    """A single locator entry to be merged into a module locator file."""

    element_id: str                    # unique identifier (e.g. "username_field")
    data: Dict[str, Any]              # raw dict as expected by LocatorBundle.from_dict()


@dataclass
class ManualCase:
    """A single manual test case to be appended into a module manual file."""

    case_id: str                       # unique identifier (e.g. "TC-001")
    name: str
    description: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    expected_result: str = ""
    preconditions: str = ""
    postconditions: str = ""
    tags: List[str] = field(default_factory=list)
    risk_level: str = "regression"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


class ModuleAwareWriter:
    """Merge-writes test artifacts into per-module consolidated files.

    Args:
        project_root: Root directory of the consumer project (where tests/,
                      locators/, manual_tests/ live).
    """

    _SHARED_IMPORTS = (
        "import os\n"
        "import pytest\n"
        "from playwright.sync_api import Page, expect\n"
    )

    def __init__(self, project_root: str | Path = ".") -> None:
        self.root = Path(project_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_tests(self, module: str, new_tests: List[TestFunction]) -> Path:
        """Merge *new_tests* into ``tests/{module}/test_{module}.py``.

        Existing functions with the same name are replaced by the incoming
        version.  New functions are appended.  Smoke-marked tests are placed
        before regression tests.

        Returns the path to the written file.
        """
        out_dir = self.root / "tests" / module
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"test_{module}.py"

        existing: Dict[str, str] = {}
        if out_path.exists():
            existing = _extract_test_functions(out_path.read_text(encoding="utf-8"))

        # Incoming replaces existing (with marks injected into the body)
        for tf in new_tests:
            existing[tf.name] = _inject_marks(tf.body, tf.marks)

        # Sort: smoke first, then everything else (stable within each group)
        def _sort_key(item: tuple) -> tuple:
            name, body = item
            is_smoke = "@pytest.mark.smoke" in body
            return (0 if is_smoke else 1, name)

        ordered = sorted(existing.items(), key=_sort_key)

        lines: List[str] = [
            f'"""Auto-generated Playwright tests for the {module} module."""\n',
            "\n",
            self._SHARED_IMPORTS,
            "\n",
        ]
        for _name, body in ordered:
            lines.append(body)
            if not body.endswith("\n\n"):
                lines.append("\n" if body.endswith("\n") else "\n\n")

        out_path.write_text("".join(lines), encoding="utf-8")
        return out_path

    def write_locators(self, module: str, new_elements: List[LocatorElement]) -> Path:
        """Merge *new_elements* into ``locators/{module}.json``.

        Existing entries with the same element_id are replaced.

        Returns the path to the written file.
        """
        loc_dir = self.root / "locators"
        loc_dir.mkdir(parents=True, exist_ok=True)
        out_path = loc_dir / f"{module}.json"

        existing: Dict[str, Dict[str, Any]] = {}
        if out_path.exists():
            try:
                raw = json.loads(out_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for entry in raw:
                        eid = entry.get("element_id") or entry.get("element_name", "")
                        if eid:
                            existing[eid] = entry
            except (json.JSONDecodeError, OSError):
                pass

        for elem in new_elements:
            existing[elem.element_id] = elem.data

        out_path.write_text(
            json.dumps(list(existing.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return out_path

    def write_manual(self, module: str, new_cases: List[ManualCase]) -> Path:
        """Append *new_cases* to ``manual_tests/{module}.md``.

        Cases whose case_id already appears in the file are skipped (append-only).

        Returns the path to the written file.
        """
        manual_dir = self.root / "manual_tests"
        manual_dir.mkdir(parents=True, exist_ok=True)
        out_path = manual_dir / f"{module}.md"

        existing_ids: set[str] = set()
        existing_content = ""
        if out_path.exists():
            existing_content = out_path.read_text(encoding="utf-8")
            existing_ids = _extract_case_ids(existing_content)

        new_blocks: List[str] = []
        if not existing_content.strip():
            new_blocks.append(f"# {module.replace('_', ' ').title()} — Manual Test Cases\n\n")

        for case in new_cases:
            if case.case_id in existing_ids:
                continue
            new_blocks.append(_render_manual_case(case))

        if new_blocks:
            separator = "" if existing_content.endswith("\n\n") else "\n"
            out_path.write_text(
                existing_content + separator + "".join(new_blocks),
                encoding="utf-8",
            )
        return out_path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_test_functions(source: str) -> Dict[str, str]:
    """Parse *source* with AST and return {function_name: full_block_with_decorators}.

    The full block includes any decorator lines and the complete function body up
    to (but not including) the blank lines before the next function.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    lines = source.splitlines(keepends=True)
    funcs: Dict[str, str] = {}

    func_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    func_nodes.sort(key=lambda n: n.lineno)

    for i, node in enumerate(func_nodes):
        if not node.name.startswith("test_"):
            continue

        # Find the start line: first decorator or the def itself (1-indexed → 0-indexed)
        if node.decorator_list:
            start_line = node.decorator_list[0].lineno - 1
        else:
            start_line = node.lineno - 1

        # End line: one line before the next top-level function's start (or end of file)
        if i + 1 < len(func_nodes):
            next_node = func_nodes[i + 1]
            if next_node.decorator_list:
                end_line = next_node.decorator_list[0].lineno - 1
            else:
                end_line = next_node.lineno - 1
        else:
            end_line = len(lines)

        # Strip trailing blank lines from the block
        block_lines = lines[start_line:end_line]
        while block_lines and not block_lines[-1].strip():
            block_lines.pop()

        funcs[node.name] = "".join(block_lines)

    return funcs


def _inject_marks(body: str, marks: List[str]) -> str:
    """Prepend @pytest.mark.<tag> decorators to *body* for each mark not already present.

    Hyphens are converted to underscores for valid Python identifiers.
    The 'manual' tag is skipped — it is an internal convention, not a useful marker.
    Decorators are inserted immediately before the first 'def test_' line.
    """
    _SKIP = {"manual"}
    new_marks = []
    for m in marks:
        identifier = re.sub(r"[^a-z0-9_]", "_", m.lower().replace("-", "_"))
        decorator = f"@pytest.mark.{identifier}"
        if identifier not in _SKIP and decorator not in body:
            new_marks.append(decorator)
    if not new_marks:
        return body
    prefix = "\n".join(new_marks) + "\n"
    # Insert before the first `def test_` line (which may already have decorators above it)
    match = re.search(r"^def test_", body, re.MULTILINE)
    if match:
        return body[: match.start()] + prefix + body[match.start() :]
    return prefix + body


def _extract_case_ids(content: str) -> set[str]:
    """Return the set of case IDs (e.g. TC-001) found in *content*."""
    return set(re.findall(r"\bTC-\d+\b", content))


def _render_manual_case(case: ManualCase) -> str:
    """Render a ManualCase as a Markdown section."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    risk = case.risk_level.upper()
    tags = ", ".join(f"`{t}`" for t in case.tags) if case.tags else ""

    lines: List[str] = [
        f"## {case.case_id} — {case.name}\n",
        "\n",
        "| Field | Value |\n",
        "|-------|-------|\n",
        f"| **Case ID** | {case.case_id} |\n",
        f"| **Risk Level** | {risk} |\n",
        f"| **Generated** | {generated_at} |\n",
    ]
    if tags:
        lines.append(f"| **Tags** | {tags} |\n")

    lines += [
        "\n",
        f"{case.description}\n",
    ]

    if case.preconditions:
        lines += ["\n", "**Preconditions:** ", case.preconditions, "\n"]

    lines += [
        "\n",
        "| # | Action | Expected Result | Test Data |\n",
        "|---|--------|----------------|----------|\n",
    ]
    for step in case.steps:
        if isinstance(step, dict):
            num = step.get("step_number", "")
            action = step.get("action", "")
            expected = step.get("expected_result", "")
            data = step.get("test_data", "") or ""
        else:
            num = ""
            action = str(step)
            expected = ""
            data = ""
        lines.append(f"| {num} | {action} | {expected} | {data} |\n")

    lines += [
        "\n",
        f"**Expected Result:** {case.expected_result}\n",
    ]

    if case.postconditions:
        lines += ["\n", f"**Postconditions:** {case.postconditions}\n"]

    lines.append("\n---\n\n")
    return "".join(lines)
