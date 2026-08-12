"""Test runner for executing tests"""

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.storage.models import ExecutionStatus
from phoenix.execution.healing import HealingEngine
from phoenix.pool import BrowserPool
from phoenix.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from phoenix.session_recovery import SessionRecovery
from phoenix.dom_cache import DOMCache
from phoenix.metrics import MetricsCollector
from phoenix.execution.intelligent_runtime import IntelligentRuntime

logger = logging.getLogger(__name__)

# pytest exit-code meanings (from pytest docs)
_PYTEST_EXIT_CODES = {
    0: "all tests passed",
    1: "some tests failed",
    2: "test run was interrupted",
    3: "internal pytest error",
    4: "pytest command line usage error (missing plugin?)",
    5: "no tests were collected",
}

# Pytest exit codes that indicate pytest itself failed (not test failures)
_PYTEST_FATAL_EXIT_CODES = {2, 3, 4}


def _preflight_check() -> List[str]:
    """Verify required pytest plugins are installed before execution."""
    missing = []
    try:
        import pytest_jsonreport  # noqa: F401
    except ImportError:
        missing.append("pytest-json-report")
    try:
        import pytest_html  # noqa: F401
    except ImportError:
        missing.append("pytest-html")
    return missing


class TestRunner:
    """Test runner using pytest with healing capabilities."""

    def __init__(
        self,
        test_output_dir: str = "./tests",
        reports_dir: str = "./reports",
        headed: bool = False,
        slow_mo: int = 0,
        enable_healing: bool = True,
        enable_intelligent_runtime: bool = True,
        project_name: str = "default",
    ):
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.headed = headed
        self.slow_mo = slow_mo
        self.enable_healing = enable_healing
        self.enable_intelligent_runtime = enable_intelligent_runtime
        self.project_name = project_name
        
        # Initialize intelligent runtime (self-learning execution engine)
        if enable_intelligent_runtime:
            self.intelligent_runtime = IntelligentRuntime(
                base_dir="phoenix_runtime",
                project_name=project_name,
                enable_cache=True,
                enable_repository=True,
                enable_diff=True,
                enable_healing=enable_healing,
                enable_metrics=True,
                enable_timeline=True
            )
            logger.info("Intelligent Runtime ENABLED - Self-learning execution engine active")
        else:
            self.intelligent_runtime = None
            logger.info("Intelligent Runtime DISABLED")
        
        # Initialize legacy components (only if intelligent runtime is disabled)
        if not enable_intelligent_runtime:
            # Initialize healing engine
            self.healing_engine = HealingEngine() if enable_healing else None
            
            # Initialize browser pool
            self.browser_pool = BrowserPool(
                max_browsers=5,
                max_contexts_per_browser=5,
                max_pages_per_context=10,
                idle_timeout_ms=30000,
                enable_auto_cleanup=True
            )
            
            # Initialize circuit breaker
            circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_ms=60000
            )
            self.circuit_breaker = CircuitBreaker(config=circuit_breaker_config)
            
            # Initialize session recovery
            self.session_recovery = SessionRecovery(
                enable_auto_recovery=True,
                check_logout_indicators=True,
                save_session_state=True
            )
            
            # Initialize DOM cache
            self.dom_cache = DOMCache(
                default_ttl_ms=30000,
                max_size_bytes=10485760,
                max_entries=100
            )
            
            # Initialize metrics collector
            self.metrics_collector = MetricsCollector()
            
            if self.healing_engine:
                logger.info("Healing Engine ENABLED for test execution")
            else:
                logger.info("Healing Engine DISABLED for test execution")
            
            logger.info("Browser Pool initialized")
            logger.info("Circuit Breaker initialized")
            logger.info("Session Recovery initialized")
            logger.info("DOM Cache initialized")
            logger.info("Metrics Collector initialized")

    def run_tests(
        self, test_paths: List[str], project_name: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Run tests using pytest.

        Returns:
            Test execution results dict.  If pytest itself fails (exit codes 2–4),
            ``status`` is set to ``error`` and ``error`` contains a clear message.
        """
        # Start intelligent execution
        execution_id = None
        if self.intelligent_runtime:
            test_name = "_".join(test_paths) if test_paths else "all_tests"
            execution_id = self.intelligent_runtime.start_execution(test_name)
            logger.info(f"Intelligent execution started: {execution_id}")
            
            # Save execution context for pytest subprocess to load
            import json as _json
            from pathlib import Path as _Path
            execution_context = {
                "execution_id": execution_id,
                "project_name": self.project_name,
                "test_name": test_name,
                "enable_intelligent_runtime": True
            }
            context_path = _Path("phoenix_runtime") / ".execution_context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            with open(context_path, 'w', encoding='utf-8') as f:
                _json.dump(execution_context, f, indent=2)
            logger.info(f"Execution context saved to {context_path}")
        
        # Preflight: make sure required plugins are present
        missing_plugins = _preflight_check()
        if missing_plugins:
            msg = (
                f"Required pytest plugin(s) not installed: {', '.join(missing_plugins)}. "
                "Run: pip install " + " ".join(missing_plugins)
            )
            print(f"ERROR: {msg}")
            
            # End intelligent execution with error
            if self.intelligent_runtime:
                self.intelligent_runtime.end_execution(status="error")
            
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": msg,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        # Build pytest command
        cmd = ["pytest", "-v", "--tb=short"]

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_report_path = self.test_output_dir / f"report_{ts}.json"
        cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])

        html_report_path = self.reports_dir / f"report_{ts}.html"
        cmd.extend(["--html", str(html_report_path), "--self-contained-html"])

        cmd.extend(["--screenshot=only-on-failure", "--output=test-results"])

        cmd.extend(test_paths)

        if kwargs.get("parallel"):
            cmd += ["-n", str(kwargs.get("workers", "auto"))]

        if kwargs.get("browser"):
            cmd += ["--browser", kwargs["browser"]]

        import os as _os
        env = _os.environ.copy()
        if self.headed or kwargs.get("headed"):
            env["PWHEADED"] = "1"
        slow = self.slow_mo or kwargs.get("slow_mo", 0)
