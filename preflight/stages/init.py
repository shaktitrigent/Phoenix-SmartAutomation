"""InitStage — run `phoenix init` and verify project scaffold was created."""
from __future__ import annotations

from typing import List

from preflight.assertions.contract import check_cli_exit_zero
from preflight.assertions.result import AssertionResult
from preflight.assertions.structure import check_required_files, check_required_folders


class InitStage:
    """Run `phoenix init --base-url <aut>` and assert the scaffold is correct."""

    def run(self, context: dict) -> List[AssertionResult]:
        results: List[AssertionResult] = []
        adapter = context["adapter"]
        sandbox = context["sandbox"]
        spec = context["spec"]
        config = context["config"]

        # Prefer the URL stored by BootStage (works for both local and external AUT)
        if context.get("aut_url"):
            base_url = context["aut_url"]
        else:
            aut_port: int = int(context.get("aut_port", config.get("aut_port", 9000)))
            base_url = f"http://127.0.0.1:{aut_port}"

        cli_result = adapter.run_cli(
            ["init", "--base-url", base_url],
            cwd=str(sandbox),
        )

        # T1: exit code 0
        results.append(check_cli_exit_zero(cli_result, "init --base-url"))

        # T2: scaffold structure (only meaningful if init succeeded)
        if cli_result.exit_code == 0:
            results.append(check_required_folders(sandbox, spec))
            results.append(check_required_files(sandbox, spec))

        return results
