"""Manual test Markdown parser.

Reads the ``manual_test_NNN_<slug>.md`` files written by
:class:`~phoenix.generators.manual.ManualTestGenerator` and reconstructs
structured test-case dicts that can be passed directly to the automation
generation pipeline.

Format expected
---------------
Each file follows this layout (produced by _render_markdown):

    # TC-001: Add New Employee - Happy Path

    ## Overview
    | Field | Value |
    | Risk Level | SMOKE |
    | Tags | `manual`, `smoke` |

    ## Description
    One-sentence summary…

    ## Preconditions
    …

    ## Test Steps
    | # | Action | Expected Result | Test Data |
    |---|--------|----------------|-----------|
    | 1 | Navigate to … | … | … |

    ## Expected Result
    …

    ## Postconditions
    …

The parser is lenient — missing sections are skipped gracefully.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    # ---- Test Steps table ----
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


def load_manual_tests_from_dir(manual_dir: str | Path) -> List[Dict[str, Any]]:
    """Load and parse all ``manual_test_*.md`` files from *manual_dir*.

    Files are returned in filename order so the ordering matches what was
    generated.  Files that cannot be parsed are silently skipped.

    Args:
        manual_dir: Directory containing ``manual_test_NNN_<slug>.md`` files.

    Returns:
        List of structured manual test dicts, ready for automation generation.
    """
    dir_path = Path(manual_dir)
    if not dir_path.exists():
        return []

    results: List[Dict[str, Any]] = []
    for md_file in sorted(dir_path.glob("manual_test_*.md")):
        parsed = parse_manual_test_file(md_file)
        if parsed:
            results.append(parsed)

    return results
