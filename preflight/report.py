"""Reporter — write a Markdown report and print a one-screen console summary."""
from __future__ import annotations

import datetime
import textwrap
from pathlib import Path
from typing import Dict, List

from preflight.assertions.result import AssertionResult

# ANSI colour helpers (gracefully degrade on Windows without ANSI support)
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_VERDICT_COLOUR = {
    "GO": _GREEN,
    "GO-WITH-WARNINGS": _YELLOW,
    "NO-GO": _RED,
}


class Reporter:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def write(
        self,
        run_metadata: dict,
        stage_results: Dict[str, List[AssertionResult]],
        t3_data: dict,
        verdict: str,
        duration_s: float,
    ) -> Path:
        """Write the Markdown report and print the console summary."""
        timestamp = run_metadata.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        safe_ts = timestamp.replace(":", "-").replace(".", "-")
        report_path = self._output_dir / f"{safe_ts}_report.md"

        md = self._build_markdown(run_metadata, stage_results, t3_data, verdict, duration_s, timestamp)
        report_path.write_text(md, encoding="utf-8")

        self._print_console_summary(run_metadata, stage_results, verdict, duration_s, report_path)

        return report_path

    # ------------------------------------------------------------------
    # Markdown construction
    # ------------------------------------------------------------------

    def _build_markdown(
        self,
        run_metadata: dict,
        stage_results: Dict[str, List[AssertionResult]],
        t3_data: dict,
        verdict: str,
        duration_s: float,
        timestamp: str,
    ) -> str:
        lines: List[str] = []

        # ------- Header -------
        lines += [
            "# Phoenix Validation Harness — Preflight Report",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Timestamp** | `{timestamp}` |",
            f"| **Git branch** | `{run_metadata.get('git_branch', 'unknown')}` |",
            f"| **Git commit** | `{run_metadata.get('git_commit', 'unknown')}` |",
            f"| **Model** | `{run_metadata.get('model_id', 'unknown')}` |",
            f"| **Temperature** | `{run_metadata.get('temperature', '?')}` |",
            f"| **Sandbox** | `{run_metadata.get('sandbox_path', 'unknown')}` |",
            f"| **Duration** | `{duration_s:.1f}s` |",
            "",
        ]

        # ------- Verdict -------
        verdict_badge = {
            "GO": "![GO](https://img.shields.io/badge/verdict-GO-brightgreen)",
            "GO-WITH-WARNINGS": "![GO-WITH-WARNINGS](https://img.shields.io/badge/verdict-GO--WITH--WARNINGS-yellow)",
            "NO-GO": "![NO-GO](https://img.shields.io/badge/verdict-NO--GO-red)",
        }.get(verdict, verdict)

        lines += [
            "## Verdict",
            "",
            f"**{verdict}** {verdict_badge}",
            "",
        ]

        # ------- Stage table -------
        lines += [
            "## Stage Summary",
            "",
            "| Stage | T1 | T2 | T3 | Result |",
            "|-------|----|----|----|--------|",
        ]

        for stage_name, results in stage_results.items():
            t1_pass = sum(1 for r in results if r.tier == "T1" and r.passed)
            t1_fail = sum(1 for r in results if r.tier == "T1" and not r.passed)
            t2_pass = sum(1 for r in results if r.tier == "T2" and r.passed)
            t2_fail = sum(1 for r in results if r.tier == "T2" and not r.passed)
            t3_pass = sum(1 for r in results if r.tier == "T3" and r.passed)
            t3_fail = sum(1 for r in results if r.tier == "T3" and not r.passed)

            def _cell(p: int, f: int) -> str:
                if p + f == 0:
                    return "—"
                parts = []
                if p:
                    parts.append(f"{p} ✓")
                if f:
                    parts.append(f"{f} ✗")
                return " / ".join(parts)

            any_fail = t1_fail + t2_fail + t3_fail > 0
            row_icon = "✗" if any_fail else "✓"
            lines.append(
                f"| {stage_name} | {_cell(t1_pass, t1_fail)} | "
                f"{_cell(t2_pass, t2_fail)} | {_cell(t3_pass, t3_fail)} | {row_icon} |"
            )

        lines.append("")

        # ------- T1/T2 pass-fail lists -------
        lines += ["## T1 / T2 Results", ""]
        all_results: List[AssertionResult] = [
            r for rs in stage_results.values() for r in rs if r.tier in ("T1", "T2")
        ]
        passed_list = [r for r in all_results if r.passed]
        failed_list = [r for r in all_results if not r.passed]

        lines += ["### Passed", ""]
        if passed_list:
            for r in passed_list:
                lines.append(f"- [{r.tier}] **{r.name}** — {r.detail}")
        else:
            lines.append("_None_")

        lines += ["", "### Failed", ""]
        if failed_list:
            for r in failed_list:
                lines.append(f"- [{r.tier}] **{r.name}**")
                if r.detail:
                    for dl in r.detail.splitlines():
                        lines.append(f"  - {dl}")
        else:
            lines.append("_None_")

        lines.append("")

        # ------- T3 numbers vs thresholds -------
        t3_results: List[AssertionResult] = [
            r for rs in stage_results.values() for r in rs if r.tier == "T3"
        ]
        lines += ["## T3 Behavioral Results", ""]

        if t3_results:
            lines += [
                "| Check | Passed | Rate | Threshold |",
                "|-------|--------|------|-----------|",
            ]
            for r in t3_results:
                rate = r.data.get("rate")
                threshold = r.data.get("threshold")
                rate_str = f"{rate * 100:.1f}%" if rate is not None else "—"
                threshold_str = f"{threshold * 100:.0f}%" if threshold is not None else "—"
                icon = "✓" if r.passed else "✗"
                lines.append(
                    f"| {r.name} | {icon} | {rate_str} | {threshold_str} |"
                )
        else:
            lines.append("_No T3 checks ran._")

        lines.append("")

        # ------- Failure details -------
        lines += ["## Failure Details", ""]
        failures = [
            r for rs in stage_results.values() for r in rs if not r.passed
        ]
        if failures:
            for r in failures:
                lines += [
                    f"### [{r.tier}] {r.name}",
                    "",
                    "```",
                    r.detail,
                    "```",
                    "",
                ]
        else:
            lines.append("_No failures._")
            lines.append("")

        # ------- Artifacts -------
        lines += ["## Artifacts", ""]
        sandbox = run_metadata.get("sandbox_path", "")
        if sandbox:
            lines.append(f"- Sandbox: `{sandbox}`")
        lines.append(f"- This report: `{self._output_dir}`")
        lines.append("")
        lines.append("---")
        lines.append("_Generated by Phoenix Validation Harness_")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------

    def _print_console_summary(
        self,
        run_metadata: dict,
        stage_results: Dict[str, List[AssertionResult]],
        verdict: str,
        duration_s: float,
        report_path: Path,
    ) -> None:
        all_results: List[AssertionResult] = [
            r for rs in stage_results.values() for r in rs
        ]
        total = len(all_results)
        passed = sum(1 for r in all_results if r.passed)
        failed = total - passed

        colour = _VERDICT_COLOUR.get(verdict, "")

        separator = "=" * 60
        print(separator)
        print(f"{_BOLD}Phoenix Preflight Report{_RESET}")
        print(separator)
        print(f"  Commit  : {run_metadata.get('git_commit', 'unknown')} ({run_metadata.get('git_branch', 'unknown')})")
        print(f"  Model   : {run_metadata.get('model_id', 'unknown')} @ {run_metadata.get('temperature', '?')}")
        print(f"  Duration: {duration_s:.1f}s")
        print()
        print(f"  Checks  : {passed}/{total} passed, {failed} failed")
        print()
        print(f"  Verdict : {colour}{_BOLD}{verdict}{_RESET}")
        print()

        # Per-stage summary
        print("  Stage breakdown:")
        for stage_name, results in stage_results.items():
            stage_failed = sum(1 for r in results if not r.passed)
            icon = f"{_GREEN}[+]{_RESET}" if stage_failed == 0 else f"{_RED}[x]{_RESET}"
            print(f"    {icon} {stage_name} ({len(results)} checks, {stage_failed} failed)")

        # Failure details (first 5)
        failures = [r for r in all_results if not r.passed]
        if failures:
            print()
            print(f"  {_RED}Failures (first 5):{_RESET}")
            for r in failures[:5]:
                print(f"    [{r.tier}] {r.name}")
                first_line = r.detail.splitlines()[0] if r.detail else ""
                if first_line:
                    print(f"          {first_line[:80]}")

        print()
        print(f"  Full report: {report_path}")
        print(separator)
