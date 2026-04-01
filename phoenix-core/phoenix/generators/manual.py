"""Manual test case generator — writes structured Markdown files to disk."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.storage.models import TestType


class ManualTestGenerator:
    """Receives structured test cases from phoenix-intelligence and writes
    them to Markdown files under the configured output directory."""

    def __init__(self, output_dir: str = "./manual_tests") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        manual_tests: List[Dict[str, Any]],
        user_story: str,
        application_url: Optional[str] = None,
        risk_level: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Format and save manual test cases as Markdown files.

        Args:
            manual_tests: Structured test cases from phoenix-intelligence.
            user_story: The original user story text.
            application_url: Application URL (shown in the file header).
            risk_level: Default risk level when the test case doesn't specify one.

        Returns:
            List of enriched test-case dicts with ``file_path`` populated.
        """
        results = []
        for idx, test in enumerate(manual_tests, 1):
            enriched = {
                "name": test.get("name", f"TC-{idx:03d}"),
                "description": test.get("description", user_story),
                "risk_level": test.get("risk_level", risk_level or "regression"),
                "preconditions": test.get("preconditions", ""),
                "steps": test.get("steps", []),
                "expected_result": test.get("expected_result", ""),
                "postconditions": test.get("postconditions", ""),
                "tags": test.get("tags", ["manual", "generated"]),
                "test_type": TestType.MANUAL.value,
            }
            self._save(enriched, idx, application_url)
            results.append(enriched)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save(
        self,
        test: Dict[str, Any],
        index: int,
        application_url: Optional[str],
    ) -> None:
        slug = _slugify(test["name"])
        filename = f"manual_test_{index:03d}_{slug}.md"
        file_path = self.output_dir / filename
        file_path.write_text(
            self._render_markdown(test, application_url), encoding="utf-8"
        )
        test["file_path"] = str(file_path)

    def _render_markdown(
        self, test: Dict[str, Any], application_url: Optional[str]
    ) -> str:
        risk = test.get("risk_level", "regression").upper()
        tags = ", ".join(f"`{t}`" for t in test.get("tags", []))
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines: List[str] = [
            f"# {test['name']}",
            "",
            "## Overview",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Risk Level** | {risk} |",
            f"| **Tags** | {tags} |",
            f"| **Generated** | {generated_at} |",
        ]
        if application_url:
            lines.append(f"| **Application URL** | {application_url} |")

        lines += [
            "",
            "## Description",
            "",
            test.get("description", ""),
        ]

        if test.get("preconditions"):
            lines += [
                "",
                "## Preconditions",
                "",
                test["preconditions"],
            ]

        lines += [
            "",
            "## Test Steps",
            "",
            "| # | Action | Expected Result | Test Data |",
            "|---|--------|----------------|-----------|",
        ]

        steps = test.get("steps", [])
        if steps and isinstance(steps[0], dict):
            for step in steps:
                action = step.get("action", "")
                expected = step.get("expected_result", "")
                data = step.get("test_data", "") or ""
                num = step.get("step_number", "")
                lines.append(f"| {num} | {action} | {expected} | {data} |")
        else:
            # Fallback: plain string steps
            for num, step in enumerate(steps, 1):
                lines.append(f"| {num} | {step} | | |")

        lines += [
            "",
            "## Expected Result",
            "",
            test.get("expected_result", ""),
        ]

        if test.get("postconditions"):
            lines += [
                "",
                "## Postconditions",
                "",
                test["postconditions"],
            ]

        lines.append("")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _slugify(name: str, max_len: int = 60) -> str:
    """Convert a test name to a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:max_len] if slug else "manual_test"
