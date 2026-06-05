"""Manual test Markdown parser.

Reads ``manual_test_NNN_<slug>.md`` files (Phoenix canonical format) and also
accepts several alternative naming conventions used by other QA tools:

    manual_test_*.md   — Phoenix canonical
    test_*.md          — common short form
    *_manual.md        — suffix convention
    TC-*.md            — Jira-style ID prefix
    *_test.md          — snake-case suffix
    *.md               — any Markdown file inside the manual_tests directory

Format supported
----------------
*Primary* (Phoenix-generated pipe table):

    ## Test Steps
    | # | Action | Expected Result | Test Data |
    |---|--------|----------------|-----------|
    | 1 | Navigate to … | … | … |

*Fallback* — numbered / bulleted plain list (e.g. from external tools):

    ## Test Steps
    1. Navigate to the login page
    2. Enter credentials
    3. Click Login

    or

    - Navigate to the login page
    - Enter credentials

The parser is lenient — missing sections are skipped gracefully.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Supported filename patterns (tried in order; first match wins per file)
# ---------------------------------------------------------------------------

SUPPORTED_PATTERNS: List[str] = [
    "manual_test_*.md",   # Phoenix canonical
    "test_*.md",          # Common short form
    "*_manual.md",        # Suffix convention
    "TC-*.md",            # Jira-style ID prefix (TC-001-login.md)
    "*_test.md",          # Snake-case suffix
]


# ---------------------------------------------------------------------------
# Row-level helpers
# ---------------------------------------------------------------------------

def _strip_md_cell(cell: str) -> str:
    """Strip whitespace and inline backtick code markers from a table cell."""
    return cell.strip().strip("`").strip()


def _parse_table_rows(block: str) -> List[List[str]]:
    """Extract data rows from a Markdown pipe table (skip header + separator)."""
    rows: List[List[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [_strip_md_cell(c) for c in line.strip("|").split("|")]
        if not cells:
            continue
        # Skip separator rows like |---|---|
        if all(re.match(r"^[-:]+$", c.replace(" ", "")) for c in cells if c):
            continue
        rows.append(cells)
    return rows


_LIST_ITEM_RE = re.compile(
    r"^\s*(?:(?P<num>\d+)[.)]\s+|[-*]\s+)(?P<text>.+)$"
)


def _parse_list_steps(block: str) -> List[Dict[str, Any]]:
    """Extract steps from a numbered or bulleted plain list.

    Handles:
        1. Navigate to the login page
        2. Enter admin / admin123
        - Click Login button
    """
    steps: List[Dict[str, Any]] = []
    for line in block.splitlines():
        m = _LIST_ITEM_RE.match(line)
        if not m:
            continue
        text = m.group("text").strip()
        if not text:
            continue
        num_str = m.group("num")
        try:
            step_num = int(num_str) if num_str else len(steps) + 1
        except (TypeError, ValueError):
            step_num = len(steps) + 1
        steps.append({
            "step_number": step_num,
            "action": text,
            "expected_result": "",
            "test_data": "",
        })
    return steps


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _split_sections(text: str) -> Dict[str, str]:
    """Split markdown into {heading_title: section_body} dict."""
    sections: Dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title.lower()] = text[start:end].strip()
    return sections


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------

def parse_manual_test_file(file_path: str | Path) -> Optional[Dict[str, Any]]:
    """Parse a single manual test Markdown file into a structured dict.

    Returns ``None`` if the file cannot be parsed (e.g. unrecognised format).
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    # ---- Name: first H1 heading ----
    name_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else path.stem

    sections = _split_sections(text)

    # ---- Overview table (risk_level, tags) ----
    risk_level = "regression"
    tags: List[str] = ["manual"]
    overview_block = sections.get("overview", "")
    for row in _parse_table_rows(overview_block):
        if len(row) < 2:
            continue
        key = row[0].lower().replace("*", "").replace(" ", "_")
        val = row[1]
        if "risk" in key:
            risk_level = val.lower()
        elif "tag" in key:
            tags = [t.strip().strip("`") for t in val.split(",") if t.strip()]

    # ---- Description ----
    description = sections.get("description", "").strip() or name

    # ---- Preconditions ----
    preconditions = sections.get("preconditions", "").strip()

    # ---- Test Steps: try pipe table first, fall back to plain list ----
    steps: List[Dict[str, Any]] = []
    steps_block = sections.get("test steps", "")
    rows = _parse_table_rows(steps_block)
    # First row is the header: # | Action | Expected Result | Test Data
    data_rows = rows[1:] if rows else []
    for row in data_rows:
        # Pad to at least 4 cells
        while len(row) < 4:
            row.append("")
        step_num_raw, action, expected, test_data = row[0], row[1], row[2], row[3]
        try:
            step_num = int(step_num_raw)
        except ValueError:
            step_num = len(steps) + 1
        if not action:
            continue
        steps.append(
            {
                "step_number": step_num,
                "action": action,
                "expected_result": expected,
                "test_data": test_data,
            }
        )

    # Fallback: plain numbered/bulleted list when no pipe table was found
    if not steps and steps_block:
        steps = _parse_list_steps(steps_block)

    # Last resort: try extracting steps from description or acceptance criteria blocks
    if not steps:
        for section_key in ("acceptance criteria", "criteria", "steps", "scenario"):
            alt_block = sections.get(section_key, "")
            if alt_block:
                steps = _parse_list_steps(alt_block)
                if steps:
                    break

    # ---- Expected Result ----
    expected_result = sections.get("expected result", "").strip()

    # ---- Postconditions ----
    postconditions = sections.get("postconditions", "").strip()

    if not steps:
        return None  # Cannot automate a test with no steps

    return {
        "name": name,
        "description": description,
        "risk_level": risk_level,
        "preconditions": preconditions,
        "steps": steps,
        "expected_result": expected_result,
        "postconditions": postconditions,
        "tags": tags,
        "source_file": str(path),
    }


def load_manual_tests_from_file(manual_file: str | Path) -> List[Dict[str, Any]]:
    """Load and parse a single manual test Markdown file.

    Args:
        manual_file: Path to a ``manual_test_*.md`` file.

    Returns:
        List of structured manual test dicts (empty list if parsing fails).
    """
    path = Path(manual_file)
    if not path.exists():
        return []
    parsed = parse_manual_test_file(path)
    return [parsed] if parsed else []


def load_manual_tests_from_dir(manual_dir: str | Path) -> List[Dict[str, Any]]:
    """Load and parse manual test Markdown files from *manual_dir*.

    Tries multiple naming patterns so that files written by Phoenix, Jira
    exports, or other QA tools are all discovered automatically:

        manual_test_*.md  — Phoenix canonical
        test_*.md         — common short form
        *_manual.md       — suffix convention
        TC-*.md           — Jira-style ID prefix
        *_test.md         — snake-case suffix

    Files are returned in filename order.  Files that cannot be parsed are
    silently skipped.

    Args:
        manual_dir: Directory containing manual test Markdown files.

    Returns:
        List of structured manual test dicts, ready for automation generation.
    """
    dir_path = Path(manual_dir)
    if not dir_path.exists():
        return []

    # Collect unique paths across all supported patterns (preserve order)
    seen: set = set()
    candidates: List[Path] = []
    for pattern in SUPPORTED_PATTERNS:
        for md_file in sorted(dir_path.glob(pattern)):
            if md_file not in seen:
                seen.add(md_file)
                candidates.append(md_file)

    results: List[Dict[str, Any]] = []
    for md_file in sorted(candidates):
        parsed = parse_manual_test_file(md_file)
        if parsed:
            results.append(parsed)

    return results
