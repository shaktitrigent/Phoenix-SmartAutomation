"""Rich-based terminal output helpers for the Phoenix CLI."""

from __future__ import annotations

import io
import sys
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


def _utf8_console(stderr: bool = False) -> Console:
    """Return a Rich Console that always writes UTF-8 safely.

    On Windows the default stdout/stderr codec is often cp1252, which cannot
    encode many Unicode glyphs (e.g. U+2139 ℹ, U+2713 ✓).  Wrapping the
    underlying binary buffer in a UTF-8 TextIOWrapper with errors='replace'
    guarantees no UnicodeEncodeError is ever raised.
    """
    try:
        stream = sys.stderr if stderr else sys.stdout
        utf8_stream = io.TextIOWrapper(
            stream.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
        return Console(file=utf8_stream, force_terminal=True, legacy_windows=False)
    except AttributeError:
        # stream has no .buffer (IDLE, pytest capsys, etc.) — fall back to defaults
        return Console(stderr=stderr, legacy_windows=False)


console = _utf8_console(stderr=False)
err_console = _utf8_console(stderr=True)


def print_success(message: str) -> None:
    console.print(f"[bold green]✓[/] {message}")


def print_error(message: str) -> None:
    err_console.print(f"[bold red]✗[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]![/] {message}")


def print_info(message: str) -> None:
    console.print(f"[bold cyan]ℹ[/] {message}")


def print_header(title: str) -> None:
    console.print(Panel(f"[bold]{title}[/]", box=box.ROUNDED, style="cyan"))


def print_generate_results(
    manual_tests: List[Dict[str, Any]],
    automation_tests: List[Dict[str, Any]],
    verbose: bool = False,
) -> None:
    print_success(f"Generated {len(manual_tests)} manual test(s)")
    print_success(f"Generated {len(automation_tests)} automation test(s)")

    if manual_tests:
        for test in manual_tests:
            if test.get("file_path"):
                console.print(f"  [dim]Manual:[/] {test['file_path']}")

    if automation_tests:
        for test in automation_tests:
            if test.get("script_path"):
                console.print(f"  [dim]Script:[/] {test['script_path']}")

    if verbose:
        if manual_tests:
            table = Table(title="Manual Tests", box=box.SIMPLE)
            table.add_column("Name", style="cyan")
            table.add_column("Risk", style="yellow")
            for test in manual_tests:
                table.add_row(
                    test.get("name", ""),
                    test.get("risk_level", ""),
                )
            console.print(table)

        if automation_tests:
            table = Table(title="Automation Tests", box=box.SIMPLE)
            table.add_column("Name", style="cyan")
            table.add_column("Script", style="dim")
            for test in automation_tests:
                table.add_row(
                    test.get("name", ""),
                    test.get("script_path", ""),
                )
            console.print(table)


def print_execution_results(result: Dict[str, Any], verbose: bool = False) -> None:
    status = result.get("status", "unknown").upper()
    total = result.get("total_tests", 0)
    passed = result.get("passed_tests", 0)
    failed = result.get("failed_tests", 0)
    skipped = result.get("skipped_tests", 0)

    status_color = "green" if status == "PASSED" else "red" if status == "FAILED" else "yellow"
    console.print(
        f"\n[bold {status_color}]{status}[/]  "
        f"[green]{passed} passed[/] / [red]{failed} failed[/] / [yellow]{skipped} skipped[/]"
        f"  (total: {total})"
    )

    if result.get("report_path"):
        print_info(f"Report: {result['report_path']}")

    if verbose and result.get("test_results"):
        table = Table(title="Test Results", box=box.SIMPLE)
        table.add_column("Status", width=8)
        table.add_column("Name")
        table.add_column("Error", style="dim red")
        for tr in result["test_results"]:
            st = tr.get("status", "")
            icon = "[green]PASS[/]" if st == "passed" else "[red]FAIL[/]"
            table.add_row(icon, tr.get("name", ""), tr.get("error_message", ""))
        console.print(table)


def print_report_summary(report_data: Dict[str, Any]) -> None:
    table = Table(title="Execution History", box=box.ROUNDED)
    table.add_column("ID", style="dim", width=6)
    table.add_column("Status")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Total", justify="right")
    table.add_column("Date")
    table.add_column("Report")

    executions = report_data if isinstance(report_data, list) else [report_data]
    for ex in executions:
        st = ex.get("status", "")
        status_str = (
            f"[green]{st}[/]" if st == "passed" else f"[red]{st}[/]" if st == "failed" else st
        )
        table.add_row(
            str(ex.get("execution_id", "")),
            status_str,
            str(ex.get("passed_tests", 0)),
            str(ex.get("failed_tests", 0)),
            str(ex.get("total_tests", 0)),
            str(ex.get("started_at", ""))[:19],
            ex.get("report_path", ""),
        )

    console.print(table)
