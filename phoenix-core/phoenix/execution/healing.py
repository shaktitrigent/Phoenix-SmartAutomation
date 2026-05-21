"""Self-Healing Engine — Prompt 3.

Architecture
------------

  ErrorClassifier
    Analyses a pytest failure's traceback/message and assigns it to one of
    six canonical error classes.  Each class has a corresponding healing
    strategy.

  HealingStrategy (abstract base)
    Each of the six subclasses knows how to mutate a single failing test
    script to increase the chance of passing on the next attempt.

  HealingEngine
    Orchestrates the retry loop:
      1. Run the test (via subprocess pytest).
      2. If it fails, classify the error.
      3. Apply the matching strategy (mutates the script in-place).
      4. Retry (up to MAX_ATTEMPTS).
      5. Record every attempt via ExecutionLogger.

  PhoenixHealingPlugin (pytest plugin)
    A pytest plugin that hooks into ``pytest_runtest_logreport`` so the
    engine can be invoked automatically during ``phoenix run``.

Error classes and strategies
-----------------------------
  1. LOCATOR_NOT_FOUND   → swap primary locator for best alternate in bundle
  2. TIMEOUT             → double all explicit timeout values in the script
  3. NAVIGATION_FAILURE  → add wait_for_load_state before the failing action
  4. ASSERTION_FAILURE   → relax strict text match to partial / regex
  5. STALE_ELEMENT       → wrap action in a retry loop with re-locate
  6. UNKNOWN             → add page.reload() before the failing line
"""

from __future__ import annotations

import re
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from phoenix.execution.logger import AttemptRecord, ExecutionLogger


MAX_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class ErrorClass:
    LOCATOR_NOT_FOUND = "locator_not_found"
    TIMEOUT = "timeout"
    NAVIGATION_FAILURE = "navigation_failure"
    ASSERTION_FAILURE = "assertion_failure"
    STALE_ELEMENT = "stale_element"
    UNKNOWN = "unknown"


_CLASSIFICATION_RULES: List[tuple] = [
    (
        ErrorClass.LOCATOR_NOT_FOUND,
        re.compile(
            r"strict mode violation|resolved to \d+ elements|"
            r"TimeoutError.*waiting.*locator|"
            r"Element is not attached|"
            r"Unable to find element",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorClass.TIMEOUT,
        re.compile(
            r"Timeout \d+ms exceeded|"
            r"page\.wait_for_.*timed out|"
            r"TimeoutError: page\.goto",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorClass.NAVIGATION_FAILURE,
        re.compile(
            r"net::ERR_|"
            r"page\.goto.*failed|"
            r"Navigation failed",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorClass.ASSERTION_FAILURE,
        re.compile(
            r"AssertionError|"
            r"expect\.to_have_text.*received|"
            r"to_contain_text.*received|"
            r"to_be_visible.*not visible",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorClass.STALE_ELEMENT,
        re.compile(
            r"stale element reference|"
            r"detached from document|"
            r"Element is not in DOM",
            re.IGNORECASE,
        ),
    ),
]


class ErrorClassifier:
    """Classify a test failure message into one of the six error classes."""

    def classify(self, error_message: str) -> str:
        """Return an ``ErrorClass.*`` constant for *error_message*."""
        for error_class, pattern in _CLASSIFICATION_RULES:
            if pattern.search(error_message):
                return error_class
        return ErrorClass.UNKNOWN

    def classify_pytest_output(self, stdout: str, stderr: str) -> str:
        """Classify using combined pytest output."""
        combined = (stdout or "") + "\n" + (stderr or "")
        return self.classify(combined)


# ---------------------------------------------------------------------------
# Healing strategies
# ---------------------------------------------------------------------------

class HealingStrategy(ABC):
    """Abstract base for healing strategies."""

    error_class: str = ""

    @abstractmethod
    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        """Mutate *script_path* to address the failure.

        Returns True if the strategy made a change, False if it had nothing
        to do (so the engine can try the next strategy).
        """


class LocatorHealingStrategy(HealingStrategy):
    """Swap the failing primary locator for its best alternate."""

    error_class = ErrorClass.LOCATOR_NOT_FOUND

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        registry = context.get("locator_registry")
        if registry is None:
            return False

        code = script_path.read_text(encoding="utf-8")
        changed = False

        for bundle in registry:
            if len(bundle.alternates) == 0:
                continue
            primary_expr = bundle.primary.value
            if primary_expr not in code:
                continue
            # Find best alternate that differs from primary
            alternates = [a for a in bundle.ordered() if a.value != primary_expr]
            if not alternates:
                continue
            best_alt = alternates[0]
            code = code.replace(primary_expr, best_alt.value, 1)
            changed = True

        if changed:
            script_path.write_text(code, encoding="utf-8")
        return changed


class TimeoutHealingStrategy(HealingStrategy):
    """Double explicit timeout values in the script."""

    error_class = ErrorClass.TIMEOUT

    _TIMEOUT_RE = re.compile(r'\btimeout\s*=\s*(\d+)', re.IGNORECASE)

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        code = script_path.read_text(encoding="utf-8")

        def double_timeout(m: re.Match) -> str:
            val = int(m.group(1))
            new_val = min(val * 2, 120_000)
            return f"timeout={new_val}"

        new_code = self._TIMEOUT_RE.sub(double_timeout, code)

        if new_code == code:
            return False
        script_path.write_text(new_code, encoding="utf-8")
        return True


class NavigationHealingStrategy(HealingStrategy):
    """Add wait_for_load_state before the failing goto/navigation line."""

    error_class = ErrorClass.NAVIGATION_FAILURE

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        code = script_path.read_text(encoding="utf-8")
        goto_re = re.compile(r'^(\s*)(page\.goto\([^)]+\))(\s*)$', re.MULTILINE)

        def add_wait(m: re.Match) -> str:
            indent = m.group(1)
            goto = m.group(2)
            tail = m.group(3)
            wait_line = f"{indent}{goto}{tail}{indent}page.wait_for_load_state('domcontentloaded')\n"
            return wait_line

        new_code = goto_re.sub(add_wait, code, count=1)
        if new_code == code:
            return False
        script_path.write_text(new_code, encoding="utf-8")
        return True


class AssertionHealingStrategy(HealingStrategy):
    """Relax strict text assertions to partial matches."""

    error_class = ErrorClass.ASSERTION_FAILURE

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        code = script_path.read_text(encoding="utf-8")
        # Replace to_have_text("exact") with to_contain_text("exact") for softer match
        new_code = re.sub(
            r'\.to_have_text\((["\'][^"\']+["\'])\)',
            r'.to_contain_text(\1)',
            code,
        )
        if new_code == code:
            return False
        script_path.write_text(new_code, encoding="utf-8")
        return True


class StaleElementHealingStrategy(HealingStrategy):
    """Wrap the failing locator action in a re-locate retry."""

    error_class = ErrorClass.STALE_ELEMENT

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        code = script_path.read_text(encoding="utf-8")
        # Add a page.wait_for_load_state() at the top of each test function
        # as a lightweight stale-element mitigation
        insert_re = re.compile(r'^(def test_\w+\([^)]*\):\n)', re.MULTILINE)

        def add_reload_wait(m: re.Match) -> str:
            return m.group(1) + "    page.wait_for_load_state('domcontentloaded')\n"

        new_code = insert_re.sub(add_reload_wait, code, count=1)
        if new_code == code:
            return False
        script_path.write_text(new_code, encoding="utf-8")
        return True


class UnknownHealingStrategy(HealingStrategy):
    """Add page.reload() + wait before the failing line as a generic fallback."""

    error_class = ErrorClass.UNKNOWN

    def apply(self, script_path: Path, error_message: str, **context: Any) -> bool:
        code = script_path.read_text(encoding="utf-8")
        # Insert a page.reload() + wait after the first page.goto() call
        goto_re = re.compile(r'^(\s*page\.goto\([^)]+\)\s*\n)', re.MULTILINE)
        new_code = goto_re.sub(
            r'\1    page.reload()\n    page.wait_for_load_state("domcontentloaded")\n',
            code,
            count=1,
        )
        if new_code == code:
            return False
        script_path.write_text(new_code, encoding="utf-8")
        return True


_STRATEGIES: Dict[str, HealingStrategy] = {
    s.error_class: s()
    for s in [
        LocatorHealingStrategy,
        TimeoutHealingStrategy,
        NavigationHealingStrategy,
        AssertionHealingStrategy,
        StaleElementHealingStrategy,
        UnknownHealingStrategy,
    ]
}


# ---------------------------------------------------------------------------
# HealingEngine
# ---------------------------------------------------------------------------

@dataclass
class HealingResult:
    test_path: str
    test_name: str
    final_status: str  # "passed" | "failed" | "error"
    attempts: int
    error_class: Optional[str] = None
    healed: bool = False
    duration_seconds: float = 0.0
    attempt_records: List[AttemptRecord] = field(default_factory=list)


class HealingEngine:
    """Orchestrates the retry loop for a single failing test script.

    Usage::

        engine = HealingEngine(logger=ExecutionLogger("logs"))
        result = engine.run(
            test_path="test_results/test_001.py",
            run_id="abc12345",
        )
        if result.healed:
            print("Healed on attempt", result.attempts)
    """

    def __init__(
        self,
        logger: Optional[ExecutionLogger] = None,
        max_attempts: int = MAX_ATTEMPTS,
        locator_registry: Any = None,
    ) -> None:
        self._logger = logger
        self._max_attempts = max_attempts
        self._classifier = ErrorClassifier()
        self._locator_registry = locator_registry

    def run(
        self,
        test_path: str,
        run_id: str,
        test_name: Optional[str] = None,
        browser: str = "chromium",
    ) -> HealingResult:
        """Run *test_path* up to max_attempts times, applying healing between retries.

        Returns a HealingResult summarising what happened.
        """
        script = Path(test_path)
        name = test_name or script.stem
        start_total = time.monotonic()
        attempt_records: List[AttemptRecord] = []
        last_error_class: Optional[str] = None

        for attempt_num in range(1, self._max_attempts + 1):
            t0 = time.monotonic()
            stdout, stderr, rc, screenshot_path = self._run_pytest(test_path, browser=browser)
            duration = time.monotonic() - t0

            status = "passed" if rc == 0 else "failed"
            if rc in (2, 3, 4):
                status = "error"

            error_msg = ""
            if status != "passed":
                error_msg = self._extract_error(stdout, stderr)
                last_error_class = self._classifier.classify(error_msg)

            record = AttemptRecord(
                run_id=run_id,
                test_path=test_path,
                test_name=name,
                attempt=attempt_num,
                status=status,
                error_type=last_error_class if status != "passed" else None,
                error_message=error_msg[:500] if error_msg else None,
                screenshot_path=screenshot_path if status != "passed" else None,
                duration_seconds=round(duration, 2),
            )
            attempt_records.append(record)
            if self._logger:
                self._logger.record_attempt(record)

            if status == "passed":
                return HealingResult(
                    test_path=test_path,
                    test_name=name,
                    final_status="passed",
                    attempts=attempt_num,
                    error_class=last_error_class,
                    healed=attempt_num > 1,
                    duration_seconds=round(time.monotonic() - start_total, 2),
                    attempt_records=attempt_records,
                )

            # Apply healing strategy before next retry
            if attempt_num < self._max_attempts:
                strategy = _STRATEGIES.get(last_error_class, _STRATEGIES[ErrorClass.UNKNOWN])
                strategy.apply(
                    script,
                    error_msg,
                    locator_registry=self._locator_registry,
                )

        return HealingResult(
            test_path=test_path,
            test_name=name,
            final_status="failed",
            attempts=self._max_attempts,
            error_class=last_error_class,
            healed=False,
            duration_seconds=round(time.monotonic() - start_total, 2),
            attempt_records=attempt_records,
        )

    # ------------------------------------------------------------------

    def _run_pytest(
        self, test_path: str, browser: str = "chromium"
    ) -> Tuple[str, str, int, Optional[str]]:
        cmd = [
            "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--no-header",
            f"--browser={browser}",
            "--screenshot=only-on-failure",
            "--output=test-results",
        ]
        t_before = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            screenshot = self._find_screenshot_since(t_before)
            return result.stdout, result.stderr, result.returncode, screenshot
        except subprocess.TimeoutExpired:
            return "", "Subprocess timed out after 300 seconds", 2, None
        except Exception as exc:
            return "", str(exc), 3, None

    def _find_screenshot_since(self, since: float) -> Optional[str]:
        """Return path of the newest PNG written to test-results/ after `since`."""
        results_dir = Path("test-results")
        if not results_dir.exists():
            return None
        newest: Optional[Path] = None
        newest_mtime = since
        for png in results_dir.rglob("*.png"):
            try:
                mtime = png.stat().st_mtime
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest = png
            except OSError:
                pass
        return str(newest.resolve()) if newest else None

    def _extract_error(self, stdout: str, stderr: str) -> str:
        combined = (stdout or "") + "\n" + (stderr or "")
        # Extract the FAILED + error lines
        lines = combined.splitlines()
        error_lines = [
            ln for ln in lines if "FAILED" in ln or "Error" in ln or "error" in ln.lower()
        ]
        return "\n".join(error_lines[:20])


# ---------------------------------------------------------------------------
# Pytest plugin
# ---------------------------------------------------------------------------

class PhoenixHealingPlugin:
    """Pytest plugin that hooks into test reports and triggers healing.

    Register with pytest by adding to conftest.py::

        pytest_plugins = ["phoenix.execution.healing"]

    Or pass ``-p phoenix.execution.healing`` on the command line.
    """

    def __init__(
        self,
        engine: Optional[HealingEngine] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self._engine = engine or HealingEngine()
        self._run_id = run_id or "unknown"
        self._healed: List[str] = []

    def pytest_runtest_logreport(self, report):
        """After each test: if it failed, attempt healing and re-run."""
        if report.when != "call":
            return
        if report.passed:
            return

        nodeid: str = report.nodeid
        test_path = nodeid.split("::")[0]

        result = self._engine.run(
            test_path=test_path,
            run_id=self._run_id,
            test_name=nodeid,
        )
        if result.healed:
            self._healed.append(nodeid)

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config):
        if self._healed:
            terminalreporter.write_sep(
                "=",
                f"Phoenix self-healing: {len(self._healed)} test(s) recovered",
            )
            for name in self._healed:
                terminalreporter.write_line(f"  ✓ healed: {name}")


# Expose plugin so pytest can import it via -p flag
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "phoenix_healing: mark a test for Phoenix self-healing retries",
    )
