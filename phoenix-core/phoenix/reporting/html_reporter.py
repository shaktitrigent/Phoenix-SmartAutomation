"""HTML report generator"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from phoenix.storage.models import ExecutionStatus


class HTMLReporter:
    """HTML report generator"""

    def __init__(self, template_dir: Optional[Path] = None, output_dir: str = "./reports"):
        """
        Initialize HTML reporter.

        Args:
            template_dir: Directory containing Jinja2 templates
            output_dir: Directory for generated reports
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_report(
        self, execution_data: Dict[str, Any], test_executions: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Generate HTML report for test execution.

        Args:
            execution_data: Execution metadata
            test_executions: List of individual test execution results

        Returns:
            Path to generated HTML report
        """
        executions = test_executions or []
        total = execution_data.get("total_tests", 0)
        passed = execution_data.get("passed_tests", 0)
        failed = execution_data.get("failed_tests", 0)

        # Per-test duration stats
        durations = [
            float(te.get("duration_seconds", 0))
            for te in executions
            if te.get("duration_seconds") is not None
        ]
        stats = None
        if durations:
            stats = {
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "failure_rate": (failed / total * 100) if total > 0 else 0.0,
            }

        # Prepare template data
        template_data = {
            "execution": execution_data,
            "test_executions": executions,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": failed,
            "skipped_tests": execution_data.get("skipped_tests", 0),
            "status": execution_data.get("status", ExecutionStatus.PENDING.value),
            "stats": stats,
        }

        # Calculate pass rate
        if template_data["total_tests"] > 0:
            template_data["pass_rate"] = (
                template_data["passed_tests"] / template_data["total_tests"] * 100
            )
        else:
            template_data["pass_rate"] = 0.0

        # Render template
        template = self.env.get_template("execution_report.html")
        html_content = template.render(**template_data)

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{timestamp}.html"
        report_path = self.output_dir / report_filename

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path

    def generate_test_case_report(self, test_case: Dict[str, Any]) -> Path:
        """
        Generate HTML report for a single test case.

        Args:
            test_case: Test case data

        Returns:
            Path to generated HTML report
        """
        template_data = {
            "test_case": test_case,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        template = self.env.get_template("test_case_detail.html")
        html_content = template.render(**template_data)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"test_case_{test_case.get('id', 'unknown')}_{timestamp}.html"
        report_path = self.output_dir / report_filename

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path
