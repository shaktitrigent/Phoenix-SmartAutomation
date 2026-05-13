"""Execution failure logger — Prompt 7.

Writes per-run JSONL execution logs to ``logs/`` so that failures can be
inspected without opening the SQLite database.

Schema
------
Each line in a ``.jsonl`` file is a JSON object that is either an
``AttemptRecord`` (one test attempt) or a ``RunRecord`` (summary of the
entire run once it completes).

    logs/
    ├── run_20250512_143200.jsonl   ← active run
    └── run_20250511_091500.jsonl   ← completed run

Usage::

    logger = ExecutionLogger(logs_dir="logs")
    run_id = logger.start_run(test_paths=["test_results/test_001.py"])

    logger.record_attempt(AttemptRecord(
        run_id=run_id,
        test_path="test_results/test_001.py",
        test_name="test_employee_creation",
        attempt=1,
        status="failed",
        error_type="locator_not_found",
        error_message="...",
        duration_seconds=3.4,
    ))

    logger.finish_run(run_id, passed=0, failed=1, total=1, duration_seconds=5.1)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AttemptRecord(BaseModel):
    """Record of a single test attempt (one test, one retry cycle)."""

    record_type: Literal["attempt"] = "attempt"
    run_id: str
    test_path: str
    test_name: str
    attempt: int = Field(..., ge=1, description="1-based attempt number")
    status: Literal["passed", "failed", "error", "skipped"]
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    """Summary record written at the end of a complete test run."""

    record_type: Literal["run"] = "run"
    run_id: str
    started_at: str
    finished_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    test_paths: List[str] = Field(default_factory=list)
    status: Literal["passed", "failed", "error"] = "passed"


# ---------------------------------------------------------------------------
# ExecutionLogger
# ---------------------------------------------------------------------------

class ExecutionLogger:
    """Writes AttemptRecords and RunRecords to per-run JSONL files."""

    def __init__(self, logs_dir: str | Path = "logs") -> None:
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._active_runs: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def start_run(self, test_paths: Optional[List[str]] = None) -> str:
        """Create a new run ID and open the JSONL file.

        Returns:
            The new ``run_id`` string.
        """
        run_id = str(uuid.uuid4())[:8]
        ts = datetime.now(timezone.utc)
        filename = f"run_{ts.strftime('%Y%m%d_%H%M%S')}_{run_id}.jsonl"
        log_path = self.logs_dir / filename
        self._active_runs[run_id] = {
            "path": log_path,
            "started_at": ts.isoformat(),
            "test_paths": test_paths or [],
        }
        return run_id

    def record_attempt(self, record: AttemptRecord) -> None:
        """Append an AttemptRecord to the JSONL file for *record.run_id*."""
        self._append(record.run_id, record.model_dump())

    def finish_run(
        self,
        run_id: str,
        *,
        passed: int,
        failed: int,
        total: int,
        skipped: int = 0,
        duration_seconds: float = 0.0,
    ) -> RunRecord:
        """Write the final RunRecord and close the active run entry.

        Returns:
            The completed RunRecord.
        """
        meta = self._active_runs.pop(run_id, {})
        status: Literal["passed", "failed", "error"] = (
            "passed" if failed == 0 and total > 0 else "failed" if failed > 0 else "error"
        )
        record = RunRecord(
            run_id=run_id,
            started_at=meta.get("started_at", datetime.now(timezone.utc).isoformat()),
            finished_at=datetime.now(timezone.utc).isoformat(),
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration_seconds,
            test_paths=meta.get("test_paths", []),
            status=status,
        )
        self._append(run_id, record.model_dump(), meta=meta)
        return record

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all completed runs (newest first)."""
        runs = []
        for log_file in sorted(self.logs_dir.glob("run_*.jsonl"), reverse=True):
            run_record = self._read_run_record(log_file)
            if run_record:
                runs.append(run_record)
        return runs

    def get_attempts(self, run_id: str) -> List[AttemptRecord]:
        """Return all AttemptRecords for a given run_id."""
        log_file = self._find_log_file(run_id)
        if not log_file:
            return []
        attempts = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                if data.get("record_type") == "attempt" and data.get("run_id") == run_id:
                    attempts.append(AttemptRecord.model_validate(data))
            except (json.JSONDecodeError, Exception):
                continue
        return attempts

    def failed_tests(self, run_id: str) -> List[str]:
        """Return test names that failed (or errored) in a run."""
        return [
            a.test_name
            for a in self.get_attempts(run_id)
            if a.status in ("failed", "error") and a.attempt == 1
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, run_id: str, data: Dict[str, Any], meta: Optional[Dict] = None) -> None:
        meta = meta or self._active_runs.get(run_id, {})
        log_path: Optional[Path] = meta.get("path") if meta else None
        if log_path is None:
            log_path = self._find_log_file(run_id) or (
                self.logs_dir / f"run_unknown_{run_id}.jsonl"
            )
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(data) + "\n")

    def _find_log_file(self, run_id: str) -> Optional[Path]:
        for f in self.logs_dir.glob(f"run_*{run_id}*.jsonl"):
            return f
        return None

    def _read_run_record(self, log_file: Path) -> Optional[Dict[str, Any]]:
        try:
            for line in reversed(log_file.read_text(encoding="utf-8").splitlines()):
                data = json.loads(line)
                if data.get("record_type") == "run":
                    return data
        except (json.JSONDecodeError, OSError):
            pass
        return None
