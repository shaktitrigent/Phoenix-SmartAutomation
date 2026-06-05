"""Atlassian Document Format (ADF) → plain text converter.

Jira Cloud returns rich-text fields (description, comments, custom fields) as ADF —
a JSON structure. This module walks the node tree and extracts readable text,
preserving structure (headings, lists, code blocks) as plain text equivalents.
"""

from __future__ import annotations

from typing import Any, Dict, List


def adf_to_text(node: Any, indent: int = 0) -> str:
    """Recursively convert an ADF node (dict or list) to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(adf_to_text(n, indent) for n in node if n)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    # Leaf text node
    if node_type == "text":
        return text

    # Inline marks (bold, italic, code, link) — just extract text
    if node_type in ("strong", "em", "code", "link", "strike", "underline", "subscript", "superscript"):
        return "".join(adf_to_text(c, indent) for c in content)

    # Hard break
    if node_type == "hardBreak":
        return "\n"

    # Paragraph
    if node_type == "paragraph":
        inner = "".join(adf_to_text(c, indent) for c in content)
        return inner + "\n"

    # Headings
    if node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        prefix = "#" * level
        inner = "".join(adf_to_text(c, indent) for c in content)
        return f"{prefix} {inner}\n"

    # Bullet / ordered list
    if node_type in ("bulletList", "orderedList"):
        parts = []
        for i, item in enumerate(content, 1):
            bullet = f"{i}." if node_type == "orderedList" else "-"
            item_text = adf_to_text(item, indent + 2).strip()
            parts.append(f"{'  ' * indent}{bullet} {item_text}")
        return "\n".join(parts) + "\n"

    if node_type == "listItem":
        return "".join(adf_to_text(c, indent) for c in content)

    # Code block
    if node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language", "")
        inner = "".join(adf_to_text(c, indent) for c in content)
        return f"```{lang}\n{inner}\n```\n"

    if node_type == "inlineCode":
        return f"`{text}`"

    # Blockquote
    if node_type == "blockquote":
        inner = "".join(adf_to_text(c, indent) for c in content)
        return "\n".join(f"> {line}" for line in inner.splitlines()) + "\n"

    # Rule / divider
    if node_type == "rule":
        return "---\n"

    # Table
    if node_type == "table":
        rows = []
        for row in content:
            cells = [
                "".join(adf_to_text(c, 0) for c in cell.get("content", [])).strip()
                for cell in row.get("content", [])
            ]
            rows.append(" | ".join(cells))
        return "\n".join(rows) + "\n"

    # Mention / emoji — emit display text
    if node_type == "mention":
        return node.get("attrs", {}).get("text", "@mention")
    if node_type == "emoji":
        return node.get("attrs", {}).get("shortName", "")

    # Media (images/attachments embedded inline) — skip binary, note presence
    if node_type in ("media", "mediaGroup", "mediaSingle"):
        alt = node.get("attrs", {}).get("alt", "")
        return f"[attachment: {alt}]\n" if alt else ""

    # Document root / generic container
    return "".join(adf_to_text(c, indent) for c in content)


def extract_acceptance_criteria(description_text: str) -> List[str]:
    """Parse acceptance criteria lines from plain-text description.

    Looks for a section labelled 'Acceptance Criteria' (case-insensitive)
    and returns the bullet/numbered items beneath it.
    Falls back to empty list if no such section exists.
    """
    import re

    lines = description_text.splitlines()
    in_ac_section = False
    criteria: List[str] = []

    ac_header = re.compile(r"^#{0,3}\s*acceptance\s+criteria\b", re.I)
    next_header = re.compile(r"^#{1,3}\s+\w")
    bullet = re.compile(r"^\s*[-*\d.]+\s+(.+)")

    for line in lines:
        if ac_header.match(line.strip()):
            in_ac_section = True
            continue
        if in_ac_section:
            # Stop at the next heading
            if next_header.match(line) and not ac_header.match(line.strip()):
                break
            m = bullet.match(line)
            if m:
                criteria.append(m.group(1).strip())
            elif line.strip() and not line.startswith("#"):
                # Plain sentence lines also count as criteria
                criteria.append(line.strip())

    return [c for c in criteria if c]
