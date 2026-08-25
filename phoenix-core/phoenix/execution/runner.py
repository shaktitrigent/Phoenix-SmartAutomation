"""Test runner for executing tests"""

import json
import re
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.storage.models import ExecutionStatus
from phoenix.execution.logger import ExecutionLogger, AttemptRecord

# Intelligent Runtime integration
try:
    from phoenix.execution.intelligent_runtime import IntelligentRuntime
    INTELLIGENT_RUNTIME_AVAILABLE = True
except ImportError:
    INTELLIGENT_RUNTIME_AVAILABLE = False

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
    """Test runner using pytest"""

    def __init__(
        self,
        test_output_dir: str = "./tests",
        reports_dir: str = "./reports",
        headed: bool = False,
        slow_mo: int = 0,
        enable_healing: bool = False,
        enable_intelligent_runtime: bool = False,
        project_name: str = "default",
        logs_dir: str = "logs",
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
        self.logs_dir = logs_dir
        
        # Initialize ExecutionLogger for failure tracking
        self.execution_logger = ExecutionLogger(logs_dir=logs_dir)
        
        # Initialize IntelligentRuntime if enabled
        self.intelligent_runtime = None
        if enable_intelligent_runtime and INTELLIGENT_RUNTIME_AVAILABLE:
            self.intelligent_runtime = IntelligentRuntime(
                base_dir="phoenix_runtime",
                project_name=project_name,
                enable_cache=True,
                enable_repository=True,
                enable_diff=True,
                enable_healing=enable_healing,
                enable_metrics=True,
                enable_timeline=True,
                enable_semantic=True,  # Priority 20: Semantic Understanding
            )
            print(f"[INTELLIGENT RUNTIME] Initialized for project: {project_name}")
            
            # Check for Priority 25 execution intelligence
            try:
                from phoenix.execution.runtime_intelligence_integration import PRIORITY25_AVAILABLE
                if PRIORITY25_AVAILABLE:
                    print("[PHOENIX] Priority 25 Execution Intelligence: AVAILABLE")
                    print("[PHOENIX] Universal Execution Orchestrator: INTEGRATED")
                    print("[PHOENIX] Action-Level Intelligence: INTEGRATED")
                    print("[PHOENIX] Enhanced Failure Intelligence: INTEGRATED")
                    print("[PHOENIX] Multi-Level Recovery: INTEGRATED")
                    print("[PHOENIX] Smart Retry Policy: INTEGRATED")
                    print("[PHOENIX] Runtime Regression Detection: INTEGRATED")
                    print("[PHOENIX] Execution Intelligence Scoring: INTEGRATED")
                    print("[PHOENIX] Enterprise Reporting: INTEGRATED")
                else:
                    print("[PHOENIX] Priority 25 Execution Intelligence: NOT AVAILABLE")
            except ImportError:
                print("[PHOENIX] Priority 25 Execution Intelligence: NOT AVAILABLE")
        elif enable_intelligent_runtime:
            print("[WARNING] Intelligent Runtime requested but dependencies not available")

    def run_tests(
        self, test_paths: List[str], project_name: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Run tests using pytest.

        Returns:
            Test execution results dict.  If pytest itself fails (exit codes 2–4),
            ``status`` is set to ``error`` and ``error`` contains a clear message.
        """
        # Track start time for duration calculation
        import time as _time
        start_time = _time.monotonic()
        
        # Preflight: make sure required plugins are present
        missing_plugins = _preflight_check()
        if missing_plugins:
            msg = (
                f"Required pytest plugin(s) not installed: {', '.join(missing_plugins)}. "
                "Run: pip install " + " ".join(missing_plugins)
            )
            print(f"ERROR: {msg}")
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": msg,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }
        
        # Start ExecutionLogger run for failure tracking
        run_id = self.execution_logger.start_run(test_paths=test_paths)
        print(f"[EXECUTION LOGGER] Started run: {run_id}")
        
        # Start IntelligentRuntime execution if enabled
        execution_id = None
        if self.intelligent_runtime:
            test_name = f"test_suite_{len(test_paths)}_tests"
            execution_id = self.intelligent_runtime.start_execution(test_name)
            print(f"[INTELLIGENT RUNTIME] Started execution: {execution_id}")
            
            # Save execution context for subprocess to load
            self._save_execution_context(execution_id, test_name, project_name or self.project_name)

        # Build pytest command
        cmd = ["pytest", "-v", "--tb=short"]

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_report_path = self.test_output_dir / f"report_{ts}.json"
        cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])

        html_report_path = self.reports_dir / f"report_{ts}.html"
        cmd.extend(["--html", str(html_report_path), "--self-contained-html"])

        cmd.extend(["--screenshot=only-on-failure", "--output=test-results"])

        # Set working directory to the project directory containing conftest.py
        # Find the project root by looking for conftest.py or pyproject.toml
        if test_paths:
            first_test_path = Path(test_paths[0])
            if first_test_path.is_absolute():
                test_dir = first_test_path.parent
            else:
                test_dir = (Path.cwd() / first_test_path).parent
            
            # Search upward for project root (conftest.py or pyproject.toml)
            project_root = test_dir
            for parent in [test_dir] + list(test_dir.parents):
                if (parent / "conftest.py").exists() or (parent / "pyproject.toml").exists():
                    project_root = parent
                    break
            
            workdir = str(project_root)
        else:
            workdir = str(Path.cwd())
        
        # Add test paths (use relative paths from current directory)
        for test_path in test_paths:
            abs_path = Path.cwd() / test_path
            try:
                rel_path = abs_path.relative_to(workdir)
                cmd.append(str(rel_path))
            except ValueError:
                # If can't make relative, use absolute path
                cmd.append(str(abs_path))

        if kwargs.get("parallel"):
            cmd += ["-n", str(kwargs.get("workers", "auto"))]

        import os as _os
        
        # Load environment variables from .env files in the project root
        try:
            from dotenv import load_dotenv
            # Use the workdir (project root) for .env files
            env_file = Path(workdir) / ".env.local"
            if env_file.exists():
                load_dotenv(env_file, override=True)
                print(f"[PHOENIX] Loaded environment variables from {env_file}")
            env_file_default = Path(workdir) / ".env"
            if env_file_default.exists():
                load_dotenv(env_file_default, override=False)
                print(f"[PHOENIX] Loaded environment variables from {env_file_default}")
        except ImportError:
            print("[PHOENIX] python-dotenv not installed, .env files not loaded")
        except Exception as e:
            print(f"[PHOENIX] Failed to load .env files: {e}")
        
        # Create env dict after loading environment variables
        env = _os.environ.copy()
        
        if self.headed or kwargs.get("headed"):
            env["PWHEADED"] = "1"
            print("[PHOENIX] Headed Mode: ENABLED")
            print("[PHOENIX] Browser will be visible during execution")
        slow = self.slow_mo or kwargs.get("slow_mo", 0)
        if slow:
            env["PWSLOWMO"] = str(slow)
            print(f"[PHOENIX] Slow-Mo: {slow}ms per action")
        
        # Print Phoenix intelligence status
        print("[PHOENIX] ============================================")
        print("[PHOENIX] PHOENIX INTELLIGENT RUNTIME")
        print("[PHOENIX] ============================================")
        print(f"[PHOENIX] Browser Mode: {'HEADED' if (self.headed or kwargs.get('headed')) else 'HEADLESS'}")
        print(f"[PHOENIX] Intelligent Runtime: {'ENABLED' if self.intelligent_runtime else 'DISABLED'}")
        if self.intelligent_runtime:
            print("[PHOENIX] DOM Snapshot Manager: ENABLED")
            print("[PHOENIX] Locator Repository: ENABLED")
            print("[PHOENIX] Healing Engine: ENABLED" if self.enable_healing else "[PHOENIX] Healing Engine: DISABLED")
            print("[PHOENIX] Runtime Metrics: ENABLED")
            print("[PHOENIX] Runtime Timeline: ENABLED")
            print("[PHOENIX] Semantic Understanding (Priority 20): ENABLED")
            print("[PHOENIX] Flow Detection (Priority 21): ENABLED")
            print("[PHOENIX] Component Intelligence (Priority 22): ENABLED")
            print("[PHOENIX] Test Intelligence (Priority 23): ENABLED")
            print("[PHOENIX] Automation Generation (Priority 24): ENABLED")
            print("[PHOENIX] Execution Intelligence (Priority 25): ENABLED")
        print("[PHOENIX] ============================================")

        try:
            # Use python -m pytest to ensure it uses the correct Python environment
            cmd = [sys.executable, "-m"] + cmd
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir, env=env)
            
            # Check if any tests were collected
            if "collected 0 items" in result.stdout or "collected 0 item" in result.stdout:
                print(f"[WARNING] No tests were collected by pytest!")
        except Exception as exc:
            # Finalize IntelligentRuntime on error
            if self.intelligent_runtime:
                self.intelligent_runtime.end_execution(status="error")
            
            # Finish ExecutionLogger run on error
            try:
                import time as _time
                self.execution_logger.finish_run(
                    run_id=run_id,
                    passed=0,
                    failed=0,
                    total=0,
                    skipped=0,
                    duration_seconds=_time.monotonic() - start_time
                )
                print(f"[EXECUTION LOGGER] Finished run (error): {run_id}")
            except Exception:
                pass
                
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": str(exc),
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        # Surface fatal pytest errors rather than silently reporting "0 passed"
        if result.returncode in _PYTEST_FATAL_EXIT_CODES:
            meaning = _PYTEST_EXIT_CODES.get(result.returncode, "unknown error")
            msg = (
                f"pytest exited with code {result.returncode} ({meaning}). "
                "Tests did not run. Check stderr for details."
            )
            if result.returncode == 4:
                msg += (
                    " This usually means a required plugin is missing or "
                    "an unrecognised command-line argument was passed."
                )
            print(f"ERROR: {msg}")
            if result.stderr:
                print(f"pytest stderr:\n{result.stderr[:2000]}")
            
            # Finish ExecutionLogger run on fatal error
            try:
                import time as _time
                self.execution_logger.finish_run(
                    run_id=run_id,
                    passed=0,
                    failed=0,
                    total=0,
                    skipped=0,
                    duration_seconds=_time.monotonic() - start_time
                )
                print(f"[EXECUTION LOGGER] Finished run (fatal error): {run_id}")
            except Exception:
                pass
                
            return {
                "status": ExecutionStatus.ERROR.value,
                "error": msg,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
            }

        # Finalize IntelligentRuntime execution
        if self.intelligent_runtime:
            execution_status = "passed" if result.returncode == 0 else "failed"
            
            # Load runtime evidence from subprocess
            # First check the workdir's phoenix_runtime directory
            evidence_sync_file = Path(workdir) / "phoenix_runtime" / ".runtime_evidence_sync.json"
            
            # Also check the main phoenix_runtime directory if not found in workdir
            if not evidence_sync_file.exists():
                main_evidence_sync_file = Path.cwd() / "phoenix_runtime" / ".runtime_evidence_sync.json"
                if main_evidence_sync_file.exists():
                    evidence_sync_file = main_evidence_sync_file
            
            # Final fallback: check parent directory phoenix_runtime
            if not evidence_sync_file.exists():
                parent_evidence_sync_file = Path(workdir).parent / "phoenix_runtime" / ".runtime_evidence_sync.json"
                if parent_evidence_sync_file.exists():
                    evidence_sync_file = parent_evidence_sync_file
            
            # Also check the IntelligentRuntime's base directory
            if not evidence_sync_file.exists():
                runtime_evidence_sync_file = self.intelligent_runtime.base_dir / ".runtime_evidence_sync.json"
                if runtime_evidence_sync_file.exists():
                    evidence_sync_file = runtime_evidence_sync_file
            
            if evidence_sync_file.exists():
                try:
                    import json
                    with open(evidence_sync_file, 'r', encoding='utf-8') as f:
                        evidence_data = json.load(f)
                    
                    # Update the TestRunner's IntelligentRuntime with subprocess evidence
                    self.intelligent_runtime.runtime_evidence.artifacts_reused = evidence_data.get("artifacts_reused", [])
                    self.intelligent_runtime.runtime_evidence.artifacts_created = evidence_data.get("artifacts_created", [])
                    self.intelligent_runtime.runtime_evidence.cache_hits = evidence_data.get("cache_hits", 0)
                    self.intelligent_runtime.runtime_evidence.cache_misses = evidence_data.get("cache_misses", 0)
                    self.intelligent_runtime.runtime_evidence.dom_reuse_count = evidence_data.get("dom_reuse_count", 0)
                    self.intelligent_runtime.runtime_evidence.dom_generation_count = evidence_data.get("dom_generation_count", 0)
                    self.intelligent_runtime.runtime_evidence.time_saved_ms = evidence_data.get("time_saved_ms", 0.0)
                    self.intelligent_runtime.runtime_evidence.mcp_calls_saved = evidence_data.get("mcp_calls_saved", 0)
                    self.intelligent_runtime.runtime_evidence.llm_calls_saved = evidence_data.get("llm_calls_saved", 0)
                except Exception as e:
                    print(f"[INTELLIGENT RUNTIME] Failed to load subprocess evidence: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[INTELLIGENT RUNTIME] Evidence sync file not found, using default evidence values")
            
            self.intelligent_runtime.end_execution(status=execution_status)
            print(f"[INTELLIGENT RUNTIME] Completed execution with status: {execution_status}")
        
        return self._parse_results(result, json_report_path, html_report_path, run_id, start_time)

    def _parse_results(
        self,
        result: subprocess.CompletedProcess,
        json_report_path: Path,
        html_report_path: Path,
        run_id: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """Parse pytest execution results."""
        execution_result: Dict[str, Any] = {
            "status": ExecutionStatus.PASSED.value
            if result.returncode == 0
            else ExecutionStatus.FAILED.value,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "json_report_path": str(json_report_path) if json_report_path.exists() else None,
            "html_report_path": str(html_report_path) if html_report_path.exists() else None,
        }

        # Exit code 5 = no tests collected — surface it clearly
        if result.returncode == 5:
            execution_result["status"] = ExecutionStatus.SKIPPED.value
            execution_result["error"] = (
                "pytest collected no tests (exit code 5). "
                "Check that test files match the pytest naming convention."
            )
            return execution_result

        # Try JSON report first
        if json_report_path.exists():
            try:
                with open(json_report_path, "r") as f:
                    json_data = json.load(f)
                summary = json_data.get("summary", {})
                execution_result["total_tests"] = summary.get("total", 0)
                execution_result["passed_tests"] = summary.get("passed", 0)
                execution_result["failed_tests"] = summary.get("failed", 0) + summary.get(
                    "error", 0
                )
                execution_result["skipped_tests"] = summary.get("skipped", 0)
                
                # Record test attempts in ExecutionLogger
                tests = json_data.get("tests", [])
                for test in tests:
                    # Extract test name from nodeid (format: tests/path/test.py::test_name)
                    nodeid = test.get("nodeid", "")
                    if "::" in nodeid:
                        test_path, test_name = nodeid.split("::", 1)
                    else:
                        test_path = test.get("location", {}).get("file", "unknown")
                        test_name = test.get("name", "unknown")
                    
                    outcome = test.get("outcome", "unknown")
                    duration = test.get("duration", 0.0)
                    
                    status = "passed" if outcome == "passed" else "failed" if outcome in ("failed", "error") else "skipped"
                    error_type = None
                    error_message = None
                    
                    if status == "failed":
                        # Extract error information
                        if "call" in test.get("setup", {}):
                            error_info = test["setup"]["call"]
                        elif "call" in test:
                            error_info = test["call"]
                        else:
                            error_info = {}
                        
                        error_type = error_info.get("crash", {}).get("type")
                        error_message = error_info.get("crash", {}).get("message")
                        if not error_message and "longrepr" in error_info:
                            error_message = str(error_info["longrepr"])[:500]
                        
                        # Classify error type based on error message content
                        if error_message:
                            error_message_lower = error_message.lower()
                            if any(keyword in error_message_lower for keyword in ["locator", "count", "resolved to 0 elements", "to_have_count", "timeout", "not found"]):
                                error_type = "locator_not_found"
                            elif "assertion" in error_message_lower:
                                error_type = "assertion_failure"
                            elif "timeout" in error_message_lower:
                                error_type = "timeout"
                    
                    attempt_record = AttemptRecord(
                        run_id=run_id,
                        test_path=test_path,
                        test_name=test_name,
                        attempt=1,
                        status=status,
                        error_type=error_type,
                        error_message=error_message,
                        duration_seconds=duration,
                    )
                    self.execution_logger.record_attempt(attempt_record)
                    
            except Exception as e:
                print(f"[EXECUTION LOGGER] Failed to parse JSON report for execution logging: {e}")

        # Fallback: parse from stdout summary line
        if execution_result["total_tests"] == 0:
            for line in result.stdout.split("\n"):
                # e.g. "3 passed, 1 failed, 2 skipped"
                numbers = re.findall(r"(\d+)\s+(passed|failed|skipped|error)", line.lower())
                if numbers:
                    counts: Dict[str, int] = {}
                    for val, label in numbers:
                        counts[label] = counts.get(label, 0) + int(val)
                    execution_result["passed_tests"] = counts.get("passed", 0)
                    execution_result["failed_tests"] = counts.get("failed", 0) + counts.get(
                        "error", 0
                    )
                    execution_result["skipped_tests"] = counts.get("skipped", 0)
                    execution_result["total_tests"] = sum(counts.values())
                    break

        # Finish ExecutionLogger run
        try:
            import time as _time
            duration = _time.monotonic() - start_time
            self.execution_logger.finish_run(
                run_id=run_id,
                passed=execution_result["passed_tests"],
                failed=execution_result["failed_tests"],
                total=execution_result["total_tests"],
                skipped=execution_result["skipped_tests"],
                duration_seconds=duration
            )
            print(f"[EXECUTION LOGGER] Finished run: {run_id}")
        except Exception as e:
            print(f"[EXECUTION LOGGER] Failed to finish run: {e}")

        return execution_result

        return execution_result
    
    def _save_execution_context(self, execution_id: str, test_name: str, project_name: str):
        """Save execution context for subprocess to load IntelligentRuntime state."""
        import json as _json
        context_path = Path("phoenix_runtime") / ".execution_context.json"
        context_path.parent.mkdir(parents=True, exist_ok=True)
        
        context = {
            "execution_id": execution_id,
            "test_name": test_name,
            "project_name": project_name,
            "enable_intelligent_runtime": self.enable_intelligent_runtime,
            "enable_healing": self.enable_healing
        }
        
        with open(context_path, 'w', encoding='utf-8') as f:
            _json.dump(context, f, indent=2)
        
        print(f"[INTELLIGENT RUNTIME] Saved execution context to {context_path}")
