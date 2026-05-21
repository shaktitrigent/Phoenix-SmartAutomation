"""Aggregators that compute derived metrics from raw Phoenix run data."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from phoenix.execution.logger import AttemptRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _module_from_test_name(test_name: str) -> str:
    """Extract module from test_name.

    test_001_login_add_employee  →  login
    test_checkout_flow           →  checkout
    """
    # Strip leading 'test_' prefix, then strip leading numeric segment
    name = re.sub(r"^test_", "", test_name, flags=re.IGNORECASE)
    name = re.sub(r"^\d+_", "", name)
    # First word segment is the module
    parts = name.split("_")
    return parts[0].lower() if parts else "unknown"


def _final_attempts(attempts: List[AttemptRecord]) -> Dict[str, AttemptRecord]:
    """Return a mapping of test_name → final (highest-attempt) AttemptRecord."""
    final: Dict[str, AttemptRecord] = {}
    for a in attempts:
        if a.test_name not in final or a.attempt > final[a.test_name].attempt:
            final[a.test_name] = a
    return final


def _is_healed(final_attempt: AttemptRecord, all_attempts: List[AttemptRecord]) -> bool:
    """True when the final attempt passed but the test was attempted more than once."""
    if final_attempt.status != "passed":
        return False
    earlier = [a for a in all_attempts if a.test_name == final_attempt.test_name]
    return any(a.attempt < final_attempt.attempt for a in earlier)


# ---------------------------------------------------------------------------
# RunAggregator
# ---------------------------------------------------------------------------

class RunAggregator:
    """Computes metrics for a single test run."""

    def __init__(self, run_record: Dict[str, Any], attempts: List[AttemptRecord]) -> None:
        self.run_record = run_record
        self.attempts = attempts
        self._final = _final_attempts(attempts)

    # ------------------------------------------------------------------
    # Basic metrics
    # ------------------------------------------------------------------

    @property
    def pass_rate(self) -> float:
        """0–100 pass rate based on final outcomes."""
        total = self.run_record.get("total", 0) or len(self._final)
        if total == 0:
            return 0.0
        passed = sum(1 for a in self._final.values() if a.status == "passed")
        return round(passed / total * 100, 1)

    @property
    def healed_count(self) -> int:
        """Number of tests that passed only after a retry."""
        return sum(
            1 for a in self._final.values() if _is_healed(a, self.attempts)
        )

    @property
    def healed_pct(self) -> float:
        total = self.run_record.get("total", 0) or len(self._final)
        if total == 0:
            return 0.0
        return round(self.healed_count / total * 100, 1)

    @property
    def flaky_count(self) -> int:
        """Within a single run, a test is flaky if it had mixed attempt outcomes.

        More meaningful across runs (TrendAggregator.flaky_tests), but we expose
        a run-level version: tests that failed at least once and also passed.
        """
        count = 0
        for test_name, final_a in self._final.items():
            test_attempts = [a for a in self.attempts if a.test_name == test_name]
            statuses = {a.status for a in test_attempts}
            if "passed" in statuses and ("failed" in statuses or "error" in statuses):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Breakdowns
    # ------------------------------------------------------------------

    def module_breakdown(self) -> List[Dict[str, Any]]:
        """[{module, total, passed, healed, failed}] sorted by failed desc."""
        modules: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "healed": 0, "failed": 0}
        )
        for test_name, final_a in self._final.items():
            mod = _module_from_test_name(test_name)
            row = modules[mod]
            row["total"] += 1
            if final_a.status == "passed":
                if _is_healed(final_a, self.attempts):
                    row["healed"] += 1
                else:
                    row["passed"] += 1
            elif final_a.status in ("failed", "error"):
                row["failed"] += 1

        result = [
            {"module": mod, **counts}
            for mod, counts in modules.items()
        ]
        result.sort(key=lambda x: (-x["failed"], x["module"]))
        return result

    def per_test_summary(self) -> List[Dict[str, Any]]:
        """Final attempt per test, enriched with healed flag and module."""
        rows: List[Dict[str, Any]] = []
        for test_name, final_a in self._final.items():
            healed = _is_healed(final_a, self.attempts)
            total_attempts = max(
                (a.attempt for a in self.attempts if a.test_name == test_name),
                default=final_a.attempt,
            )
            all_test_attempts = sorted(
                [a for a in self.attempts if a.test_name == test_name],
                key=lambda a: a.attempt,
            )
            rows.append(
                {
                    "test_name": test_name,
                    "test_path": final_a.test_path,
                    "module": _module_from_test_name(test_name),
                    "status": final_a.status,
                    "healed": healed,
                    "attempt": final_a.attempt,
                    "total_attempts": total_attempts,
                    "duration_seconds": final_a.duration_seconds,
                    "error_type": final_a.error_type,
                    "error_message": final_a.error_message,
                    "screenshot_path": final_a.screenshot_path,
                    "timestamp": final_a.timestamp,
                    "all_attempts": [
                        {
                            "attempt": a.attempt,
                            "status": a.status,
                            "error_type": a.error_type,
                            "error_message": a.error_message,
                            "duration_seconds": a.duration_seconds,
                            "screenshot_path": a.screenshot_path,
                        }
                        for a in all_test_attempts
                    ],
                }
            )

        # Sort: failed first, then healed, then passed; within each by duration desc
        status_order = {"failed": 0, "error": 1, "healed": 2, "passed": 3, "skipped": 4}

        def sort_key(row: Dict[str, Any]) -> Tuple:
            effective = "healed" if row["healed"] else row["status"]
            return (status_order.get(effective, 9), -row["duration_seconds"])

        rows.sort(key=sort_key)
        return rows

    def error_type_counts(self) -> Dict[str, int]:
        """{'assertion_failure': 3, 'timeout': 1, ...} across all attempts."""
        counts: Dict[str, int] = defaultdict(int)
        for a in self.attempts:
            if a.error_type:
                counts[a.error_type] += 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def error_type_healing(self) -> Dict[str, Dict[str, int]]:
        """Per error_type: how many tests healed vs failed.

        Returns {error_type: {count, healed, failed}}
        """
        # Group all attempts by error_type
        et_attempts: Dict[str, List[AttemptRecord]] = defaultdict(list)
        for a in self.attempts:
            if a.error_type:
                et_attempts[a.error_type].append(a)

        result: Dict[str, Dict[str, int]] = {}
        for et, atts in et_attempts.items():
            test_names = {a.test_name for a in atts}
            healed = sum(
                1 for tn in test_names
                if self._final.get(tn) and _is_healed(self._final[tn], self.attempts)
            )
            failed_final = sum(
                1 for tn in test_names
                if self._final.get(tn) and self._final[tn].status in ("failed", "error")
            )
            result[et] = {"count": len(atts), "healed": healed, "failed": failed_final}
        return result


# ---------------------------------------------------------------------------
# TrendAggregator
# ---------------------------------------------------------------------------

class TrendAggregator:
    """Computes metrics across multiple runs."""

    def __init__(self, runs: List[Tuple[Dict[str, Any], List[AttemptRecord]]]) -> None:
        # runs is newest-first
        self.runs = runs

    # ------------------------------------------------------------------
    # Trend series
    # ------------------------------------------------------------------

    def pass_rate_trend(self) -> List[Dict[str, Any]]:
        """[{run_id, started_at, pass_rate, total}] oldest-first for charts."""
        rows = []
        for run_record, attempts in reversed(self.runs):
            agg = RunAggregator(run_record, attempts)
            rows.append(
                {
                    "run_id": run_record.get("run_id", ""),
                    "started_at": run_record.get("started_at", ""),
                    "pass_rate": agg.pass_rate,
                    "total": run_record.get("total", 0),
                }
            )
        return rows

    def duration_trend(self) -> List[Dict[str, Any]]:
        """[{run_id, started_at, duration_seconds}] oldest-first."""
        rows = []
        for run_record, attempts in reversed(self.runs):
            rows.append(
                {
                    "run_id": run_record.get("run_id", ""),
                    "started_at": run_record.get("started_at", ""),
                    "duration_seconds": run_record.get("duration_seconds", 0.0),
                }
            )
        return rows

    def healing_trend(self) -> List[Dict[str, Any]]:
        """[{run_id, started_at, passed_first, healed, failed}] oldest-first."""
        rows = []
        for run_record, attempts in reversed(self.runs):
            agg = RunAggregator(run_record, attempts)
            final = _final_attempts(attempts)
            healed = agg.healed_count
            passed_total = sum(1 for a in final.values() if a.status == "passed")
            passed_first = passed_total - healed
            failed = sum(1 for a in final.values() if a.status in ("failed", "error"))
            rows.append(
                {
                    "run_id": run_record.get("run_id", ""),
                    "started_at": run_record.get("started_at", ""),
                    "passed_first": passed_first,
                    "healed": healed,
                    "failed": failed,
                }
            )
        return rows

    def flaky_tests(self) -> List[Dict[str, Any]]:
        """Tests that have both passing and failing outcomes across runs.

        Returns [{ test_name, runs_history, flake_rate, first_flaked }]
        """
        # Build per-test history: test_name → list of (started_at, status)
        test_history: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        for run_record, attempts in reversed(self.runs):
            final = _final_attempts(attempts)
            started_at = run_record.get("started_at", "")
            for test_name, final_a in final.items():
                test_history[test_name].append(
                    {
                        "run_id": run_record.get("run_id", ""),
                        "started_at": started_at,
                        "status": "pass" if final_a.status == "passed" else "fail",
                    }
                )

        flaky: List[Dict[str, Any]] = []
        for test_name, history in test_history.items():
            if len(history) < 2:
                continue
            statuses = {h["status"] for h in history}
            if "pass" not in statuses or "fail" not in statuses:
                continue
            fail_count = sum(1 for h in history if h["status"] == "fail")
            flake_rate = round(fail_count / len(history) * 100, 1)
            first_flaked = next(
                (h["started_at"] for h in history if h["status"] == "fail"), ""
            )
            flaky.append(
                {
                    "test_name": test_name,
                    "runs_history": [h["status"] for h in history],
                    "flake_rate": flake_rate,
                    "first_flaked": first_flaked,
                    "total_runs": len(history),
                }
            )

        flaky.sort(key=lambda x: -x["flake_rate"])
        return flaky

    def prev_run_delta(self) -> Dict[str, Any]:
        """Compare latest run vs second-latest.

        Returns {pass_rate_delta, duration_delta}
        """
        if len(self.runs) < 2:
            return {"pass_rate_delta": None, "duration_delta": None}

        latest_rr, latest_att = self.runs[0]
        prev_rr, prev_att = self.runs[1]

        latest_pr = RunAggregator(latest_rr, latest_att).pass_rate
        prev_pr = RunAggregator(prev_rr, prev_att).pass_rate

        latest_dur = latest_rr.get("duration_seconds", 0.0)
        prev_dur = prev_rr.get("duration_seconds", 0.0)

        return {
            "pass_rate_delta": round(latest_pr - prev_pr, 1),
            "duration_delta": round(latest_dur - prev_dur, 1),
        }
