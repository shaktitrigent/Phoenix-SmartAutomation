"""Manual test case generator — writes structured Markdown files to disk.

Manual-First Pipeline
---------------------
Manual test cases are generated and validated through a quality gate
*before* automation scripts are generated.  This ensures:

  1. Every automation test has a corresponding, human-readable manual spec.
  2. Placeholder or incomplete tests are rejected before wasting LLM tokens
     on automation generation.
  3. The quality gate produces actionable feedback for the test author.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from phoenix.storage.models import TestType


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

class ManualTestQualityGate:
    """Validates manual test cases before they are saved or passed to automation.

    Returns a list of (test_name, [violations]) tuples for failing tests.
    An empty violations list means all tests passed.

    Threshold defaults are intentionally permissive so that valid short tests
    (single-step scenarios, brief descriptions) are not silently dropped.
    Pass ``strict=True`` for tighter CI-grade validation.
    """

    _PLACEHOLDER_RE = re.compile(
        r"\b(TODO|FIXME|TBD|placeholder|lorem ipsum|xxx)\b", re.IGNORECASE
    )
    # Hard-block markers that indicate the test requires human review before automation
    _REVIEW_MARKERS = [
        "[NEEDS MANUAL REVIEW]",
        "[TODO]",
        "[TBD]",
        "[FIXME]",
        "[PLACEHOLDER]",
    ]

    # Default (permissive) thresholds
    _MIN_NAME_LEN  = 3
    _MIN_DESC_LEN  = 3
    _MIN_STEP_TEXT = 3
    _MIN_STEPS     = 1

    # Strict-mode thresholds (opt-in via strict=True)
    _STRICT_MIN_NAME_LEN  = 5
    _STRICT_MIN_DESC_LEN  = 10
    _STRICT_MIN_STEP_TEXT = 5
    _STRICT_MIN_STEPS     = 2

    def __init__(self, strict: bool = False) -> None:
        self._strict = strict
        if strict:
            self._min_name  = self._STRICT_MIN_NAME_LEN
            self._min_desc  = self._STRICT_MIN_DESC_LEN
            self._min_step  = self._STRICT_MIN_STEP_TEXT
            self._min_steps = self._STRICT_MIN_STEPS
        else:
            self._min_name  = self._MIN_NAME_LEN
            self._min_desc  = self._MIN_DESC_LEN
            self._min_step  = self._MIN_STEP_TEXT
            self._min_steps = self._MIN_STEPS

    def validate_one(self, test: Dict[str, Any]) -> List[str]:
        """Return a list of violation messages for a single test dict."""
        violations: List[str] = []
        name = test.get("name", "")
        description = test.get("description", "")
        steps = test.get("steps", [])
        expected_result = test.get("expected_result", "")

        # Hard block: check the entire serialised test for unresolved review markers.
        # JSON-encode to catch markers inside steps, expected_result, etc.
        import json as _json
        test_text = _json.dumps(test)
        for marker in self._REVIEW_MARKERS:
            if marker in test_text:
                violations.append(
                    f"test contains unresolved marker {marker!r} — "
                    "resolve this before automation generation"
                )

        if len(name) < self._min_name:
            violations.append(f"name too short ({len(name)} chars, need ≥ {self._min_name})")
        if self._PLACEHOLDER_RE.search(name):
            violations.append("name contains placeholder text")

        if len(description) < self._min_desc:
            violations.append(
                f"description too short ({len(description)} chars, need ≥ {self._min_desc})"
            )

        if len(steps) < self._min_steps:
            violations.append(
                f"needs ≥ {self._min_steps} steps, got {len(steps)}"
            )

        for i, step in enumerate(steps, 1):
            action = step.get("action", "") if isinstance(step, dict) else str(step)
            expected = step.get("expected_result", "") if isinstance(step, dict) else ""
            if len(action) < self._min_step:
                violations.append(f"step {i} action too short")
            if self._strict and len(expected) < self._min_step:
                violations.append(f"step {i} expected_result too short")
            if self._PLACEHOLDER_RE.search(action):
                violations.append(f"step {i} contains placeholder text")

        if self._strict and not expected_result:
            violations.append("missing overall expected_result")

        return violations

    def validate_all(
        self, tests: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, List[str]]]]:
        """Validate a list of test dicts.

        Returns:
            (passing_tests, [(name, [violations]), ...]) where passing_tests
            is the subset that passed and the second element lists failures.
        """
        passing: List[Dict[str, Any]] = []
        failures: List[Tuple[str, List[str]]] = []
        for test in tests:
            violations = self.validate_one(test)
            if violations:
                failures.append((test.get("name", "<unnamed>"), violations))
            else:
                passing.append(test)
        return passing, failures


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class ManualTestGenerator:
    """Receives structured test cases from phoenix-intelligence and writes
    them to Markdown files under the configured output directory.

    Manual-First gate:
      By default ``gate=True``, which means tests failing the quality check
      are logged as warnings and excluded from the written output.
      Set ``gate=False`` to write all tests regardless of quality.
    """

    def __init__(
        self,
        output_dir: str = "./manual_tests",
        gate: bool = True,
        strict: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._gate = ManualTestQualityGate(strict=strict) if gate else None

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
            Tests that fail the quality gate are excluded.
        """
        # Apply quality gate
        self._last_gate_failures: List[Tuple[str, List[str]]] = []
        if self._gate is not None:
            passing, failures = self._gate.validate_all(manual_tests)
            self._last_gate_failures = failures
            for name, violations in failures:
                import logging
                logging.getLogger(__name__).warning(
                    "Manual test %r failed quality gate — skipped: %s",
                    name,
                    "; ".join(violations),
                )
            tests_to_write = passing
        else:
            tests_to_write = manual_tests

        results = []
        for idx, test in enumerate(tests_to_write, 1):
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

    def validate(
        self, manual_tests: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, List[str]]]]:
        """Run quality gate without writing files.

        Returns:
            (passing, failures) — same contract as ManualTestQualityGate.validate_all.
        """
        gate = self._gate or ManualTestQualityGate()
        return gate.validate_all(manual_tests)

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
        file_path.write_text(self._render_markdown(test, application_url), encoding="utf-8")
        test["file_path"] = str(file_path)

    def _render_markdown(self, test: Dict[str, Any], application_url: Optional[str]) -> str:
        risk = test.get("risk_level", "regression").upper()
        tags = ", ".join(f"`{t}`" for t in test.get("tags", []))
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines: List[str] = [
            f"# {test['name']}",
            "",
            "## Overview",
            "",
            "| Field | Value |",
            "|-------|-------|",
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
