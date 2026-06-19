"""Heal-log audit helper — appends JSONL records to logs/heal_log.jsonl.

Every automatic locator swap (whether triggered by the healing engine during
``phoenix run --heal`` or by ``phoenix fix`` falling back to a registry
alternate) is recorded here so engineers can audit what was changed and why.

Record shape::

    {
        "ts": "2026-06-18T12:34:56Z",   # ISO-8601 UTC timestamp
        "page": "login",
        "element_name": "username_field",
        "old_value": "[name='user-name']",
        "new_value": "[data-test='login-username']",
        "new_strategy": "test-id",
        "confidence": 0.95,
        "outcome": "committed",          # committed | registry_fix | needs_review
        "script": "tests/test_001_login.py"
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_LOG_FILENAME = "heal_log.jsonl"


def append_heal_record(
    *,
    logs_dir: Path,
    page: str,
    element_name: str,
    old_value: str,
    new_value: str,
    new_strategy: str,
    confidence: float,
    outcome: str,
    script: str = "",
) -> None:
    """Append one JSONL record to ``logs_dir/heal_log.jsonl``.

    Creates the file (and any parent directories) if they do not exist.
    Swallows all I/O errors so a logging failure never breaks a test run.
    """
    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "page": page,
        "element_name": element_name,
        "old_value": old_value,
        "new_value": new_value,
        "new_strategy": new_strategy,
        "confidence": round(float(confidence), 3),
        "outcome": outcome,
        "script": script,
    }
    try:
        logs_dir = Path(logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / _LOG_FILENAME
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.debug("heal_log write failed: %s", exc)
