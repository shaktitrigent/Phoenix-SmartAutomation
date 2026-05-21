"""HTML report generator for Phoenix test runs.

Reads JSONL log data and writes a self-contained HTML report to reports/.

This module preserves the original ``generate_html_report`` function signature
for backward compatibility.  The actual rendering is handled by
``phoenix.reporting.render``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from phoenix.execution.logger import AttemptRecord


def generate_html_report(
    run_id: str,
    run_record: Dict[str, Any],
    attempts: List[AttemptRecord],
    reports_dir: Path,
    project_name: str = "Phoenix Project",
    environment: str = "",
) -> Path:
    """Write a self-contained HTML report and return its path.

    Args:
        run_id: The run identifier.
        run_record: RunRecord dict from ExecutionLogger.
        attempts: All AttemptRecords for this run.
        reports_dir: Directory to write the report into.
        project_name: Displayed in the report header.
        environment: Environment label (e.g. "QA", "staging").

    Returns:
        Path to the generated HTML file.
    """
    from phoenix.reporting.render import render_run_report

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"report_{run_id}.html"

    html_content = render_run_report(
        run_record=run_record,
        attempts=attempts,
        trend_runs=[],          # no trend data in the compat shim
        project_name=project_name,
        environment=environment,
    )

    report_path.write_text(html_content, encoding="utf-8")
    return report_path
