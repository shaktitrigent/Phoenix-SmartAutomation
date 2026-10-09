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
        cells = [_strip_md_cell(c).replace(r"\|", "|").replace("<br>", "\n") for c in re.split(r"(?<!\\)\|", line.strip("|"))]
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

# BDD/Gherkin keyword patterns
_BDD_KEYWORD_RE = re.compile(
    r"^\s*(?P<keyword>Given|When|Then|And)\s+(?P<text>.+)$",
    re.IGNORECASE
)


def _parse_bdd_steps(block: str) -> List[Dict[str, Any]]:
    """Extract steps from BDD/Gherkin format (Given/When/Then/And).

    Semantic interpretation:
    - Given: setup/context -> becomes action with preconditions context
    - When: the action -> becomes action
    - Then: expected result/assertion -> becomes expected_result
    - And: extends the previous semantic step (never becomes a field/selector/locator)

    Example:
        Given I am on the login page
        When I enter username "x"
        And I enter password "y"
        And I click Login
        Then I should see the dashboard

    Result: 4 steps with proper action/expected_result mapping.

    Compound actions:
        When I enter username "x"
        And I enter password "y"
    Result: 2 separate steps, both with actions.

    Compound assertions:
        Then I should see the dashboard
        And I should see the products list
    Result: 1 step with combined expected_result.
    """
    steps: List[Dict[str, Any]] = []
    lines = block.splitlines()
    
    # Track the previous semantic keyword to handle "And" correctly
    last_keyword = None
    
    for line in lines:
        m = _BDD_KEYWORD_RE.match(line)
        if not m:
            continue
        
        keyword = m.group("keyword").capitalize()  # Normalize to Given/When/Then/And
        text = m.group("text").strip()
        
        if not text:
            continue
        
        # Determine semantic role based on keyword
        if keyword == "Given":
            # Given is setup/context - treat as action
            role = "action"
            last_keyword = "Given"
        elif keyword == "When":
            # When is the action
            role = "action"
            last_keyword = "When"
        elif keyword == "Then":
            # Then is the expected result/assertion
            role = "expected_result"
            last_keyword = "Then"
        elif keyword == "And":
            # And extends the previous semantic step
            if last_keyword == "Then":
                # And after Then: combine into same step's expected_result
                role = "expected_result_append"
            else:
                # And after Given or When: create new action step
                role = "action"
        else:
            # Fallback: treat as action
            role = "action"
        
        step_num = len(steps) + 1
        
        if role == "action":
            # Always create a new step for actions (including And after Given/When)
            steps.append({
                "step_number": step_num,
                "action": text,
                "expected_result": "",
                "test_data": "",
            })
        elif role == "expected_result":
            # Then: create a new step with expected_result
            steps.append({
                "step_number": step_num,
                "action": "",
                "expected_result": text,
                "test_data": "",
            })
        elif role == "expected_result_append":
            # And after Then: append to previous step's expected_result
            if steps:
                steps[-1]["expected_result"] += " " + text
    
    return steps


def _parse_list_steps(block: str) -> List[Dict[str, Any]]:
    """Extract steps from a numbered or bulleted plain list.

    Handles:
        1. Navigate to the login page
        2. Enter username / password
        - Click Login button
    Also handles embedded numbered lists in text blocks.
    """
    steps: List[Dict[str, Any]] = []
    
    # First try the standard line-by-line parsing
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
    
    # If no steps found, try to extract numbered patterns from the entire text
    if not steps:
        # Look for patterns like "1. Action" anywhere in the text
        # This handles cases where steps are embedded in paragraphs like "Main Flow 1. Open 2. Enter"
        # Improved pattern to handle embedded markdown formatting and bullet points
        numbered_pattern = re.compile(r'(?:^|\s)(\d+)\.\s+([^.!?]+[.!?]?)', re.MULTILINE)
        matches = numbered_pattern.findall(block)
        
        for num_str, action in matches:
            action = action.strip()
            # Clean up common markdown artifacts but preserve backticks for value extraction
            action = re.sub(r'\*\*', '', action)  # Remove bold markdown
            # Don't remove backticks - they are needed for value extraction
            if action:
                try:
                    step_num = int(num_str)
                except (TypeError, ValueError):
                    step_num = len(steps) + 1
                steps.append({
                    "step_number": step_num,
                    "action": action,
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
        step_num_raw, action, expected = row[0], row[1], row[2]
        test_data = " | ".join(c for c in row[3:] if c) if len(row) > 4 else row[3]
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

    # Fallback: try BDD/Gherkin format first, then plain numbered/bulleted list
    if not steps and steps_block:
        # Try BDD parsing (Given/When/Then/And)
        steps = _parse_bdd_steps(steps_block)
        
        # If BDD parsing didn't yield steps, try list parsing
        if not steps:
            steps = _parse_list_steps(steps_block)

    # If still no steps, extract steps from description if available (Main Flow, etc.)
    if not steps and description:
        steps = _parse_list_steps(description)

    # Last resort: try extracting steps from alternative blocks
    if not steps:
        for section_key in ("acceptance criteria", "criteria", "steps", "scenario", "main flow", "test case flow", "flow", "mainflow"):
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
