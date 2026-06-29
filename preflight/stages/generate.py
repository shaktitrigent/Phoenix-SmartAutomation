"""GenerateStage — feed canned_story.md through `phoenix generate`."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from preflight.assertions.contract import check_cli_exit_zero
from preflight.assertions.result import AssertionResult


class GenerateStage:
    """Copy canned_story.md into the sandbox, run phoenix generate, assert outputs."""

    def run(self, context: dict) -> List[AssertionResult]:
        results: List[AssertionResult] = []
        adapter = context["adapter"]
        sandbox = context["sandbox"]

        # Locate canned_story.md — it lives in fixtures/ next to this package
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        story_src = fixtures_dir / "canned_story.md"

        # Ensure user_stories/ directory exists and copy the story in
        user_stories_dir = sandbox / "user_stories"
        user_stories_dir.mkdir(parents=True, exist_ok=True)
        dest = user_stories_dir / "canned_story.md"
        shutil.copy2(str(story_src), str(dest))

        # Run phoenix generate
        cli_result = adapter.run_cli(
            ["generate", "--story-file", "user_stories/canned_story.md", "--no-gate"],
            cwd=str(sandbox),
        )

        # T1: CLI exit 0
        results.append(check_cli_exit_zero(cli_result, "generate --story-file --no-gate"))

        # T3: at least one .md file appears in manual_tests/
        manual_tests_dir = sandbox / "manual_tests"
        md_files = list(manual_tests_dir.glob("*.md")) if manual_tests_dir.exists() else []
        results.append(AssertionResult(
            tier="T3",
            name="T3:generate_produces_spec",
            passed=len(md_files) > 0,
            detail=(
                f"Found {len(md_files)} .md file(s) in manual_tests/: "
                + ", ".join(f.name for f in md_files[:5])
                if md_files
                else "No .md files found in manual_tests/ after generate"
            ),
            data={"md_files": [f.name for f in md_files]},
        ))

        return results
