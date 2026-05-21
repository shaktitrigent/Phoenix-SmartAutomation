"""Data loader for Phoenix JSONL execution logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from phoenix.execution.logger import AttemptRecord


class DataLoader:
    """Reads AttemptRecord and RunRecord data from JSONL log files."""

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = Path(logs_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_run(self, run_id: str) -> Tuple[Dict[str, Any], List[AttemptRecord]]:
        """Return (run_record_dict, list_of_attempts) for one run."""
        log_file = self._find_log_file(run_id)
        if log_file is None:
            return {}, []
        return self._parse_file(log_file, run_id)

    def load_last_n_runs(self, n: int) -> List[Tuple[Dict[str, Any], List[AttemptRecord]]]:
        """Return the n most recent runs, newest first."""
        files = sorted(self.logs_dir.glob("run_*.jsonl"), reverse=True)
        results: List[Tuple[Dict[str, Any], List[AttemptRecord]]] = []
        for log_file in files:
            if len(results) >= n:
                break
            run_record, attempts = self._parse_file(log_file, run_id=None)
            if run_record:
                results.append((run_record, attempts))
        return results

    def list_run_ids(self) -> List[str]:
        """Return run_ids for all completed runs, newest first."""
        run_ids: List[str] = []
        for log_file in sorted(self.logs_dir.glob("run_*.jsonl"), reverse=True):
            rr, _ = self._parse_file(log_file, run_id=None)
            rid = rr.get("run_id")
            if rid:
                run_ids.append(rid)
        return run_ids

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_log_file(self, run_id: str) -> Optional[Path]:
        for f in self.logs_dir.glob(f"run_*{run_id}*.jsonl"):
            return f
        return None

    def _parse_file(
        self,
        log_file: Path,
        run_id: Optional[str],
    ) -> Tuple[Dict[str, Any], List[AttemptRecord]]:
        """Parse a JSONL file and return (run_record, attempts)."""
        run_record: Dict[str, Any] = {}
        attempts: List[AttemptRecord] = []
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            return run_record, attempts

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            rt = data.get("record_type")
            if rt == "run":
                if run_id is None or data.get("run_id") == run_id:
                    run_record = data
            elif rt == "attempt":
                if run_id is None or data.get("run_id") == run_id:
                    try:
                        attempts.append(AttemptRecord.model_validate(data))
                    except Exception:
                        continue

        return run_record, attempts
