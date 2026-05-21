"""Test runner for executing tests"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.storage.models import ExecutionStatus

# pytest exit-code meanings (from pytest docs)
_PYTEST_EXIT_CODES = {
    0: "all tests passed",
    1: "some tests failed",
    2: "test run was interrupted",
    3: "internal pytest error",
    4: "pytest command line usage error (missing plugin?)",
    5: "no tests were collected",
}

# Pytest exit codes that indicate pytest itself failed (not test failures)
_PYTEST_FATAL_EXIT_CODES = {2, 3, 4}


def _preflight_check() -> List[str]:
    """Verify required pytest plugins are installed before execution."""
    missing = []
    try:
        import pytest_jsonreport  # noqa: F401
    except ImportError:
        missing.append("pytest-json-report")
    try:
        import pytest_html  # noqa: F401
    except ImportError:
        missing.append("pytest-html")
    return missing


class TestRunner:
    """Test runner using pytest"""

    def __init__(
        self,
        test_output_dir: str = "./test_results",
        reports_dir: str = "./reports",
    ):
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run_tests(
        self, test_paths: List[str], project_name: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Run tests using pytest.

        Returns:
            Test execution results dict.  If pytest itself fails (exit codes 2–4),
            ``status`` is set to ``error`` and ``error`` contains a clear message.
        """
        # Preflight: make sure required plugins are present
        missing_plugins = _preflight_check()
        if missing_plugins:
            msg = (
                f"Required pytest plugin(s) not installed: {', '.join(missing_plugins)}. "
                "Run: pip install " + " ".join(missing_plugins)
            )
            print(f"ERROR: {msg}")
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": msg,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        # Build pytest command
        cmd = ["pytest", "-v", "--tb=short"]

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_report_path = self.test_output_dir / f"report_{ts}.json"
        cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])

        html_report_path = self.reports_dir / f"report_{ts}.html"
        cmd.extend(["--html", str(html_report_path), "--self-contained-html"])

        cmd.extend(["--screenshot=only-on-failure", "--output=test-results"])

        cmd.extend(test_paths)

        if kwargs.get("parallel"):
            cmd += ["-n", str(kwargs.get("workers", "auto"))]

        if kwargs.get("browser"):
            cmd += ["--browser", kwargs["browser"]]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        except Exception as exc:
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": str(exc),
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        # Surface fatal pytest errors rather than silently reporting "0 passed"
        if result.returncode in _PYTEST_FATAL_EXIT_CODES:
            meaning = _PYTEST_EXIT_CODES.get(result.returncode, "unknown error")
            msg = (
                f"pytest exited with code {result.returncode} ({meaning}). "
                "Tests did not run. Check stderr for details."
            )
            if result.returncode == 4:
                msg += (
                    " This usually means a required plugin is missing or "
                    "an unrecognised command-line argument was passed."
                )
            print(f"ERROR: {msg}")
            if result.stderr:
                print(f"pytest stderr:\n{result.stderr[:2000]}")
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": msg,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        return self._parse_results(result, json_report_path, html_report_path)

    def _parse_results(
        self,
        result: subprocess.CompletedProcess,
        json_report_path: Path,
        html_report_path: Path,
    ) -> Dict[str, Any]:
        """Parse pytest execution results."""
        execution_result: Dict[str, Any] = {
            "status": ExecutionStatus.PASSED.value
            if result.returncode == 0
            else ExecutionStatus.FAILED.value,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "json_report_path": str(json_report_path) if json_report_path.exists() else None,
            "html_report_path": str(html_report_path) if html_report_path.exists() else None,
        }

        # Exit code 5 = no tests collected — surface it clearly
        if result.returncode == 5:
            execution_result["status"] = ExecutionStatus.SKIPPED.value
            execution_result["error"] = (
                "pytest collected no tests (exit code 5). "
                "Check that test files match the pytest naming convention."
            )
            return execution_result

        # Try JSON report first
        if json_report_path.exists():
            try:
                with open(json_report_path, "r") as f:
                    json_data = json.load(f)
                summary = json_data.get("summary", {})
                execution_result["total_tests"] = summary.get("total", 0)
                execution_result["passed_tests"] = summary.get("passed", 0)
                execution_result["failed_tests"] = summary.get("failed", 0) + summary.get(
                    "error", 0
                )
                execution_result["skipped_tests"] = summary.get("skipped", 0)
            except Exception:
                pass

        # Fallback: parse from stdout summary line
        if execution_result["total_tests"] == 0:
            for line in result.stdout.split("\n"):
                # e.g. "3 passed, 1 failed, 2 skipped"
                numbers = re.findall(r"(\d+)\s+(passed|failed|skipped|error)", line.lower())
                if numbers:
                    counts: Dict[str, int] = {}
                    for val, label in numbers:
                        counts[label] = counts.get(label, 0) + int(val)
                    execution_result["passed_tests"] = counts.get("passed", 0)
                    execution_result["failed_tests"] = counts.get("failed", 0) + counts.get(
                        "error", 0
                    )
                    execution_result["skipped_tests"] = counts.get("skipped", 0)
                    execution_result["total_tests"] = sum(counts.values())
                    break

        return execution_result
