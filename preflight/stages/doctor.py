"""DoctorStage — run `phoenix doctor` and verify clean exit."""
from __future__ import annotations

from typing import List

from preflight.assertions.contract import check_cli_exit_zero
from preflight.assertions.result import AssertionResult


class DoctorStage:
    """Run `phoenix doctor` in the sandbox and assert exit code 0."""

    def run(self, context: dict) -> List[AssertionResult]:
        adapter = context["adapter"]
        sandbox = context["sandbox"]

        result = adapter.run_cli(["doctor"], cwd=str(sandbox))
        return [check_cli_exit_zero(result, "doctor")]
