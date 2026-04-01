"""Test runner for executing tests"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import subprocess
import json
from datetime import datetime
from phoenix.storage.models import ExecutionStatus


class TestRunner:
    """Test runner using pytest"""

    def __init__(self, test_output_dir: str = "./test_results"):
        """
        Initialize test runner.
        
        Args:
            test_output_dir: Directory for test output
        """
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def run_tests(
        self,
        test_paths: List[str],
        project_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run tests using pytest.
        
        Args:
            test_paths: List of test file paths or directories
            project_name: Optional project name
            **kwargs: Additional pytest options
            
        Returns:
            Test execution results
        """
        # Build pytest command
        cmd = ["pytest", "-v", "--tb=short"]
        
        # Add JSON report
        json_report_path = self.test_output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])
        
        # Add HTML report
        html_report_dir = self.test_output_dir / "html_reports"
        html_report_dir.mkdir(exist_ok=True)
        cmd.extend(["--html", str(html_report_dir / "report.html"), "--self-contained-html"])
        
        # Add test paths
        cmd.extend(test_paths)
        
        # Add additional options
        if kwargs.get("parallel"):
            cmd.append("-n")
            cmd.append(str(kwargs.get("workers", "auto")))
        
        if kwargs.get("browser"):
            cmd.extend(["--browser", kwargs["browser"]])
        
        # Run pytest
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            # Parse results
            execution_result = self._parse_results(
                result, json_report_path, html_report_dir / "report.html"
            )
            
            return execution_result
        
        except Exception as e:
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": str(e),
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

    def _parse_results(
        self, result: subprocess.CompletedProcess, json_report_path: Path, html_report_path: Path
    ) -> Dict[str, Any]:
        """Parse pytest execution results"""
        execution_result = {
            "status": ExecutionStatus.PASSED.value if result.returncode == 0 else ExecutionStatus.FAILED.value,
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
        
        # Try to parse JSON report if available
        if json_report_path.exists():
            try:
                with open(json_report_path, "r") as f:
                    json_data = json.load(f)
                summary = json_data.get("summary", {})
                execution_result["total_tests"] = summary.get("total", 0)
                execution_result["passed_tests"] = summary.get("passed", 0)
                execution_result["failed_tests"] = summary.get("failed", 0) + summary.get("error", 0)
                execution_result["skipped_tests"] = summary.get("skipped", 0)
            except Exception:
                pass
        
        # Parse from stdout if JSON not available
        if execution_result["total_tests"] == 0:
            stdout_lines = result.stdout.split("\n")
            for line in stdout_lines:
                if "passed" in line.lower() and "failed" in line.lower():
                    # Try to extract numbers
                    import re
                    numbers = re.findall(r'\d+', line)
                    if len(numbers) >= 3:
                        execution_result["passed_tests"] = int(numbers[0])
                        execution_result["failed_tests"] = int(numbers[1]) if len(numbers) > 1 else 0
                        execution_result["skipped_tests"] = int(numbers[2]) if len(numbers) > 2 else 0
                        execution_result["total_tests"] = (
                            execution_result["passed_tests"] +
                            execution_result["failed_tests"] +
                            execution_result["skipped_tests"]
                        )
        
        return execution_result
