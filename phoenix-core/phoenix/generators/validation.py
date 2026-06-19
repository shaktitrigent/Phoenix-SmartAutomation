"""Script validation gates for generated Playwright/pytest files.

Three lightweight checks run in order after normalisation:

  1. validate_syntax  — stdlib ast.parse, no subprocess.
  2. validate_compile — ``python -m py_compile <path>``, catches import-time errors
                        (missing modules, NameError at import scope, etc.).
  3. validate_collect — ``pytest --collect-only -q <path>``, catches missing fixtures,
                        conftest import failures, and "no test found" (rc 5).

Every function returns ``None`` on success or a short error string on failure.
The error string is fed back to the ScriptFixerAgent for an LLM repair attempt.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Optional


def validate_syntax(code: str) -> Optional[str]:
    """Return an error message if *code* has a Python syntax error, else None."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as exc:
        return f"SyntaxError at line {exc.lineno}: {exc.msg}"


def validate_compile(path: Path) -> Optional[str]:
    """Run ``python -m py_compile`` against *path*.

    Returns None on success or the stderr/stdout tail (≤ 800 chars) on failure.
    Fast — no browser, no pytest plugins required.
    """
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return None
    output = (result.stderr or result.stdout or "py_compile failed").strip()
    return output[-800:]  # trim very long tracebacks


def validate_collect(path: Path, cwd: Optional[Path] = None) -> Optional[str]:
    """Run ``pytest --collect-only -q`` against *path*.

    Exit codes:
      0  → collection succeeded (at least one test found) — returns None
      5  → no tests collected (file has no ``def test_`` function) — returns error
      1  → tests collected but one of them triggered an error during collection
      2  → collection error (import failure, bad fixture, etc.)
      3/4 → internal pytest errors

    No ``--json-report`` / browser plugins needed — this is a lightweight check
    that runs long before ``phoenix run``.

    Returns None on success or the captured output tail (≤ 1200 chars) on failure.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--collect-only", "-q",
        "--no-header",
        "--tb=short",
        str(path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode == 0:
        return None
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 5:
        return f"No test functions found in {path.name} — script may be empty or all defs are missing.\n{output[-400:]}"
    return output[-1200:]
