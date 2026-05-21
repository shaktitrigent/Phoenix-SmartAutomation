"""ReportGenerator — high-level API for producing Phoenix HTML reports."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Optional

from phoenix.reporting.data_loader import DataLoader
from phoenix.reporting.render import render_run_report


class ReportGenerator:
    """Generate HTML reports from Phoenix JSONL execution logs."""

    def __init__(
        self,
        logs_dir: Path = Path("logs"),
        reports_dir: Path = Path("reports"),
    ) -> None:
        self.logs_dir = Path(logs_dir)
        self.reports_dir = Path(reports_dir)
        self._loader = DataLoader(self.logs_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_run_report(
        self,
        run_id: str = "latest",
        open_browser: bool = False,
        project_name: str = "Phoenix Project",
        environment: str = "",
    ) -> Path:
        """Generate HTML report for one run.

        Args:
            run_id: The run ID to report on, or ``"latest"`` for the most recent run.
            open_browser: If True, open the report in the default web browser.
            project_name: Displayed in the report header.
            environment: Environment label (e.g. "QA", "staging", "prod").

        Returns:
            Absolute path to the generated ``.html`` file.
        """
        # Resolve "latest"
        if run_id == "latest":
            ids = self._loader.list_run_ids()
            if not ids:
                raise FileNotFoundError(f"No completed runs found in {self.logs_dir}/")
            run_id = ids[0]

        run_record, attempts = self._loader.load_run(run_id)
        if not run_record:
            raise FileNotFoundError(f"Run ID '{run_id}' not found in {self.logs_dir}/")

        # Load up to 20 trend runs (includes the current run)
        trend_runs = self._loader.load_last_n_runs(20)

        html_content = render_run_report(
            run_record=run_record,
            attempts=attempts,
            trend_runs=trend_runs,
            project_name=project_name,
            environment=environment,
        )

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reports_dir / f"report_{run_id}.html"
        report_path.write_text(html_content, encoding="utf-8")

        if open_browser:
            webbrowser.open(report_path.resolve().as_uri())

        return report_path

    def generate_trend_report(self, last_n_runs: int = 20) -> Path:
        """Generate aggregate trend report across N runs.

        Produces a report focused on multi-run trends (pass rate, duration,
        healing activity, and flakiness).  The "current run" is the most
        recent completed run.

        Args:
            last_n_runs: How many recent runs to include in trend data.

        Returns:
            Absolute path to the generated ``.html`` file.
        """
        runs = self._loader.load_last_n_runs(last_n_runs)
        if not runs:
            raise FileNotFoundError(f"No completed runs found in {self.logs_dir}/")

        # Use the most recent run as the primary run
        run_record, attempts = runs[0]
        run_id = run_record.get("run_id", "trend")

        html_content = render_run_report(
            run_record=run_record,
            attempts=attempts,
            trend_runs=runs,
            project_name="Phoenix Trend Report",
            environment="",
        )

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reports_dir / f"trend_report_{run_id}.html"
        report_path.write_text(html_content, encoding="utf-8")
        return report_path
