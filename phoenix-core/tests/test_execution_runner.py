import json
import subprocess
import sys
from pathlib import Path

from phoenix.execution.runner import TestRunner


def test_run_tests_uses_current_python_interpreter(tmp_path, monkeypatch):
    runner = TestRunner(test_output_dir=str(tmp_path / "test_results"))
    captured = {}

    def fake_run(cmd, capture_output, text, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd

        json_report = next(
            Path(arg.split("=", 1)[1]) for arg in cmd if arg.startswith("--json-report-file=")
        )
        json_report.parent.mkdir(parents=True, exist_ok=True)
        json_report.write_text(json.dumps({"summary": {"total": 1, "passed": 1}}), encoding="utf-8")

        html_report = Path(cmd[cmd.index("--html") + 1])
        html_report.parent.mkdir(parents=True, exist_ok=True)
        html_report.write_text("<html></html>", encoding="utf-8")

        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.run_tests(["test_results/test_sample.py"])

    assert captured["cmd"][:3] == [sys.executable, "-m", "pytest"]
    assert result["total_tests"] == 1
    assert result["passed_tests"] == 1
    assert result["failed_tests"] == 0


def test_parse_results_falls_back_to_stdout_summary(tmp_path):
    runner = TestRunner(test_output_dir=str(tmp_path / "test_results"))
    result = subprocess.CompletedProcess(
        [sys.executable, "-m", "pytest"],
        0,
        stdout="============================== 1 passed in 0.50s ==============================\n",
        stderr="",
    )

    parsed = runner._parse_results(
        result=result,
        json_report_path=tmp_path / "missing-report.json",
        html_report_path=tmp_path / "missing-report.html",
    )

    assert parsed["total_tests"] == 1
    assert parsed["passed_tests"] == 1
    assert parsed["failed_tests"] == 0
    assert parsed["skipped_tests"] == 0


def test_run_tests_retries_without_reporting_plugins(tmp_path, monkeypatch):
    runner = TestRunner(test_output_dir=str(tmp_path / "test_results"))
    calls = []

    def fake_run(cmd, capture_output, text, cwd):
        calls.append(cmd)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd,
                4,
                stdout="",
                stderr=(
                    "ERROR: usage: __main__.py [options] [file_or_dir] [...]\n"
                    "__main__.py: error: unrecognized arguments: --json-report --html\n"
                ),
            )
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="============================== 1 passed in 0.50s ==============================\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.run_tests(["test_results/test_sample.py"])

    assert len(calls) == 2
    assert "--json-report" in calls[0]
    assert "--html" in calls[0]
    assert "--json-report" not in calls[1]
    assert "--html" not in calls[1]
    assert result["passed_tests"] == 1
    assert result["total_tests"] == 1
