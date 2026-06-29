"""RunStage — execute the generated test suite via `phoenix run tests/`."""
from __future__ import annotations

from typing import List

from preflight.assertions.behavior import run_tests
from preflight.assertions.result import AssertionResult


class RunStage:
    """Run the generated tests and capture first-run green rate."""

    def run(self, context: dict) -> List[AssertionResult]:
        results: List[AssertionResult] = []
        adapter = context["adapter"]
        sandbox = context["sandbox"]
        config = context["config"]
        python_exe = context["python_exe"]

        t3_threshold: float = float(config.get("t3_first_run_green_min", 0.70))

        # Run phoenix run tests/ via the CLI
        cli_result = adapter.run_cli(["run", "tests/"], cwd=str(sandbox))

        # T1: exit 0 or 1 is acceptable (tests may fail); 2/3/4 = tool crash
        acceptable_exit = cli_result.exit_code in (0, 1)
        results.append(AssertionResult(
            tier="T1",
            name="T1:cli_exit_run",
            passed=acceptable_exit,
            detail=(
                f"exit_code={cli_result.exit_code} ({'ok' if acceptable_exit else 'TOOL CRASH'}), "
                f"duration={cli_result.duration_s:.2f}s"
                if acceptable_exit
                else (
                    f"exit_code={cli_result.exit_code} — tool crash (expected 0 or 1)\n"
                    f"stdout: {cli_result.stdout[-400:]}\n"
                    f"stderr: {cli_result.stderr[-400:]}"
                )
            ),
        ))

        # T3: behavior — green rate vs threshold
        behavior = run_tests(sandbox, python_exe, test_path="tests/")
        rate_pct = behavior.rate * 100

        passes_threshold = behavior.rate >= t3_threshold
        warned = behavior.total > 0 and passes_threshold and behavior.rate < 1.0

        results.append(AssertionResult(
            tier="T3",
            name="T3:first_run_green_rate",
            passed=passes_threshold,
            detail=(
                f"{behavior.pass_count}/{behavior.total} tests passed "
                f"({rate_pct:.1f}%) — threshold {t3_threshold * 100:.0f}%"
            ),
            data={
                "pass_count": behavior.pass_count,
                "total": behavior.total,
                "rate": behavior.rate,
                "threshold": t3_threshold,
                "warned": warned,
            },
        ))

        # Store behavior result in context for fix stage reference
        context["first_run_behavior"] = behavior

        return results
