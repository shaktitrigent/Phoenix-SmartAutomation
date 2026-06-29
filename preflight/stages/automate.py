"""AutomateStage — install golden spec, run `phoenix automate`, run T2 checks."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from preflight.assertions.contract import check_cli_exit_zero
from preflight.assertions.result import AssertionResult
from preflight.assertions.structure import (
    check_collect,
    check_imports,
    check_locator_registry,
    check_no_raw_selectors_in_pages,
    check_spec_grouping,
    check_syntax,
    check_test_grouping,
)


class AutomateStage:
    """Place the golden spec in manual_tests/, run phoenix automate, assert T2 quality."""

    def run(self, context: dict) -> List[AssertionResult]:
        results: List[AssertionResult] = []
        adapter = context["adapter"]
        sandbox = context["sandbox"]
        spec = context["spec"]
        python_exe = context["python_exe"]

        # Replace manual_tests/ with ONLY the golden specs so the gate tests
        # our known-good input, not whatever phoenix generate happened to emit.
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        golden_dir = fixtures_dir / "golden_spec"
        golden_specs = [
            "manual_test_tc001_login_success.md",
            "manual_test_tc002_login_failure.md",
        ]

        manual_tests_dir = sandbox / "manual_tests"
        manual_tests_dir.mkdir(parents=True, exist_ok=True)

        # Remove ALL existing .md files left by GenerateStage so the gate only
        # processes our two known-good golden specs.
        for stale in manual_tests_dir.glob("*.md"):
            stale.unlink(missing_ok=True)

        for spec_name in golden_specs:
            shutil.copy2(str(golden_dir / spec_name), str(manual_tests_dir / spec_name))

        # Delete stale generated page objects so the "extend" action in
        # _apply_page_object doesn't preserve the old header (missing runtime helpers).
        # Files without helpers produce NameError at runtime.
        pages_dir = sandbox / "pages"
        if pages_dir.exists():
            for stale_page in pages_dir.glob("manual_test_*_page.py"):
                stale_page.unlink(missing_ok=True)

        # Delete stale generated test files that correspond to our golden specs.
        for stale_dir in (sandbox / "tests").rglob("test_manual_test_*.py"):
            stale_dir.unlink(missing_ok=True)

        # Delete the starter test placed by `phoenix init` — it uses wrong navigation
        # URLs and unset env vars.  phoenix automate will generate a correct replacement.
        starter_test = sandbox / "tests" / "login" / "test_login.py"
        starter_test.unlink(missing_ok=True)

        # Delete fixtures/auth.py so conftest.py falls back to an unauthenticated
        # `authenticated_page` fixture.  The generated login tests (TC001, TC002)
        # need a plain page, not a pre-authenticated one; auth.py would try to read
        # TEST_USERNAME / TEST_PASSWORD env vars that aren't set in the gate context.
        auth_fixture = sandbox / "fixtures" / "auth.py"
        auth_fixture.unlink(missing_ok=True)

        # Run phoenix automate
        cli_result = adapter.run_cli(["automate"], cwd=str(sandbox))

        # T1: CLI exit 0
        results.append(check_cli_exit_zero(cli_result, "automate"))

        # T2 checks (run regardless so we capture evidence on partial failures)
        results.append(check_test_grouping(sandbox, spec))
        results.append(check_spec_grouping(sandbox, spec))
        results.append(check_no_raw_selectors_in_pages(sandbox, spec))
        results.append(check_locator_registry(sandbox, spec))
        results.append(check_imports(sandbox, spec))
        results.append(check_syntax(sandbox))
        results.append(check_collect(sandbox, python_exe))

        return results
