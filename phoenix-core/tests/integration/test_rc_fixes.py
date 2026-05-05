"""Integration tests verifying all 7 root-cause fixes (RC-01 through RC-07).

Each test is labelled with the RC number it verifies and is fully independent.
Run with:  pytest tests/integration/test_rc_fixes.py -v
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers — import the modules under test
# ---------------------------------------------------------------------------

# Add phoenix-intelligence to sys.path so we can import test_generator directly
_INTEL_ROOT = (
    Path(__file__).resolve().parents[3] / "phoenix-intelligence"
)
if str(_INTEL_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEL_ROOT))

from services.agents.test_generator import (
    ControlType,
    _classify_control,
    _criterion_to_playwright_lines,
    _derive_expected_result,
    _derive_overall_expected_result,
)


# ---------------------------------------------------------------------------
# RC-01: Fallback is not the default — criteria produce real Playwright code
# ---------------------------------------------------------------------------

class TestRC01FallbackCriteriaMapped:
    """RC-01: criteria-to-action mapper generates real Playwright interactions."""

    LOGIN_URL = "https://the-internet.herokuapp.com/login"
    CRITERIA = [
        "Enter username tomsmith",
        "Enter password SuperSecretPassword!",
        "Click the Login button",
        "Verify the Secure Area page is shown",
    ]

    def _build_script(self) -> str:
        from services.agents.test_generator import TestGeneratorAgent

        # Instantiate without LLM/MCP to force fallback path
        agent = TestGeneratorAgent.__new__(TestGeneratorAgent)
        agent.llm_client = None
        agent.mcp_client = None
        return agent._build_automation_fallback_script(
            user_story="User logs in with valid credentials",
            application_url=self.LOGIN_URL,
            acceptance_criteria=self.CRITERIA,
        )

    def test_script_contains_fill_not_just_comments(self):
        script = self._build_script()
        assert ".fill(" in script, "Expected .fill() call in generated script"

    def test_script_contains_click(self):
        script = self._build_script()
        assert ".click()" in script, "Expected .click() call in generated script"

    def test_script_contains_expect_assertion(self):
        script = self._build_script()
        assert "expect(" in script, "Expected expect() assertion in generated script"

    def test_script_is_valid_python(self):
        import ast
        script = self._build_script()
        ast.parse(script)  # raises SyntaxError if invalid

    def test_script_has_warning_header(self):
        script = self._build_script()
        assert "WARNING" in script, "Fallback script must include WARNING header"

    def test_script_never_uses_time_sleep(self):
        script = self._build_script()
        assert "time.sleep" not in script


# ---------------------------------------------------------------------------
# RC-02: Control-specific logic — each control type maps to the right method
# ---------------------------------------------------------------------------

class TestRC02ControlClassification:
    """RC-02: correct ControlType is inferred from criterion text and URL."""

    def test_checkbox_classified_from_url(self):
        ct = _classify_control("Check checkbox 1", "https://example.com/checkboxes")
        assert ct == ControlType.CHECKBOX

    def test_dropdown_classified_from_url(self):
        ct = _classify_control("Select Option 1", "https://example.com/dropdown")
        assert ct == ControlType.SELECT_DROPDOWN

    def test_file_upload_classified(self):
        ct = _classify_control("Upload a test file", "https://example.com/upload")
        assert ct == ControlType.FILE_INPUT

    def test_alert_classified(self):
        ct = _classify_control("Click the JS Alert button and dismiss the alert", "https://example.com/javascript_alerts")
        assert ct in (ControlType.BROWSER_ALERT, ControlType.BUTTON)

    def test_drag_drop_classified(self):
        ct = _classify_control("Drag element A and drop it on column B")
        assert ct == ControlType.DRAG_DROP

    def test_fill_generates_check_for_checkbox(self):
        lines = _criterion_to_playwright_lines("Check checkbox 1", 1, "https://example.com/checkboxes")
        code = "\n".join(lines)
        assert ".check()" in code, f"Expected .check() in: {code}"
        assert ".fill(" not in code

    def test_fill_generates_select_option_for_dropdown(self):
        lines = _criterion_to_playwright_lines("Select Option 1 from dropdown", 1, "https://example.com/dropdown")
        code = "\n".join(lines)
        assert "select_option(" in code, f"Expected select_option() in: {code}"

    def test_file_upload_generates_set_input_files(self):
        lines = _criterion_to_playwright_lines("Upload a test file", 1, "https://example.com/upload")
        code = "\n".join(lines)
        assert "set_input_files(" in code, f"Expected set_input_files() in: {code}"

    def test_drag_drop_generates_drag_to(self):
        lines = _criterion_to_playwright_lines("Drag element A to column B", 1)
        code = "\n".join(lines)
        assert "drag_to(" in code, f"Expected drag_to() in: {code}"


# ---------------------------------------------------------------------------
# RC-03: Manual test quality — no "Step completes as expected" placeholder
# ---------------------------------------------------------------------------

class TestRC03ManualTestQuality:
    """RC-03: derived expected results are specific, never the generic placeholder."""

    FORBIDDEN_PHRASE = "step completes as expected"

    def _fallback_tests(self):
        from services.agents.test_generator import TestGeneratorAgent

        agent = TestGeneratorAgent.__new__(TestGeneratorAgent)
        agent.llm_client = None
        agent.mcp_client = None
        return agent._generate_manual_tests_fallback(
            user_story="User logs in with valid credentials",
            application_url="https://the-internet.herokuapp.com/login",
            acceptance_criteria=[
                "Enter username tomsmith",
                "Enter password SuperSecretPassword!",
                "Click the Login button",
                "Verify the Secure Area page is shown",
            ],
            risk_level="regression",
        )

    def test_no_generic_placeholder_in_steps(self):
        tests = self._fallback_tests()
        for tc in tests:
            for step in tc.get("steps", []):
                er = step.get("expected_result", "").lower()
                assert self.FORBIDDEN_PHRASE not in er, (
                    f"Generic placeholder found in step: {step}"
                )

    def test_each_expected_result_is_specific(self):
        tests = self._fallback_tests()
        for tc in tests:
            for step in tc.get("steps", []):
                er = step.get("expected_result", "")
                assert len(er) >= 20, (
                    f"Expected result too short (likely a placeholder): '{er}'"
                )

    def test_overall_expected_result_is_not_generic(self):
        tests = self._fallback_tests()
        for tc in tests:
            er = tc.get("expected_result", "").lower()
            assert self.FORBIDDEN_PHRASE not in er

    def test_derive_expected_result_fill(self):
        result = _derive_expected_result("Enter username tomsmith")
        assert "tomsmith" in result.lower() or "username" in result.lower()

    def test_derive_expected_result_click(self):
        result = _derive_expected_result("Click the Login button")
        assert "login" in result.lower() or "click" in result.lower()

    def test_derive_expected_result_verify(self):
        result = _derive_expected_result("Verify the Secure Area page is shown")
        assert "secure area" in result.lower() or "shown" in result.lower()

    def test_derive_expected_result_never_returns_generic(self):
        criteria = [
            "Enter username tomsmith",
            "Click the Login button",
            "Select Option 1 from dropdown",
            "Check checkbox 1",
            "Upload a test file",
        ]
        for c in criteria:
            result = _derive_expected_result(c)
            assert "step completes as expected" not in result.lower(), (
                f"Generic placeholder returned for: {c}"
            )


# ---------------------------------------------------------------------------
# RC-04: Execute pipeline — preflight check and exit-code handling
# ---------------------------------------------------------------------------

class TestRC04ExecutePipeline:
    """RC-04: missing plugins and fatal pytest exit codes are surfaced clearly."""

    def test_preflight_check_returns_list(self):
        from phoenix.execution.runner import _preflight_check
        missing = _preflight_check()
        assert isinstance(missing, list)

    def test_preflight_result_names_missing_plugins(self):
        """If plugins are missing, names must be 'pytest-json-report' / 'pytest-html'."""
        from phoenix.execution.runner import _preflight_check
        missing = _preflight_check()
        for name in missing:
            assert name in ("pytest-json-report", "pytest-html"), (
                f"Unexpected plugin name: {name}"
            )

    def test_runner_reports_error_when_plugins_missing(self, monkeypatch):
        """If preflight fails, run_tests must return status=error, not '0 passed'."""
        from phoenix.execution.runner import TestRunner, _preflight_check

        monkeypatch.setattr(
            "phoenix.execution.runner._preflight_check",
            lambda: ["pytest-json-report"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            runner = TestRunner(test_output_dir=tmp)
            result = runner.run_tests(["nonexistent_test.py"])
        assert result["status"] == "error"
        assert result["total_tests"] == 0
        assert "pytest-json-report" in result["error"]

    def test_fatal_exit_code_is_not_reported_as_zero_passed(self, monkeypatch, tmp_path):
        """Exit code 4 must surface an error, never '0 passed'."""
        import subprocess
        from phoenix.execution.runner import TestRunner

        fake_result = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=4,
            stdout="",
            stderr="ERROR: unrecognized arguments: --json-report",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        runner = TestRunner(test_output_dir=str(tmp_path))
        result = runner.run_tests(["test_dummy.py"])
        assert result["status"] == "error", (
            "Exit code 4 must not be silently treated as '0 passed'"
        )
        assert result.get("total_tests", 0) == 0


# ---------------------------------------------------------------------------
# RC-05: SQLite healthcheck — write access is verified before use
# ---------------------------------------------------------------------------

class TestRC05SQLiteHealthcheck:
    """RC-05: DB write access is checked; failure degrades to JSON output."""

    def test_valid_temp_db_passes_healthcheck(self):
        from phoenix.storage.database import check_db_write_access
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/test.db"
            assert check_db_write_access(url) is True

    def test_nonexistent_dir_healthcheck_creates_parent_or_fails_gracefully(self):
        from phoenix.storage.database import check_db_write_access
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/subdir/test.db"
            result = check_db_write_access(url)
            # Should either succeed (created subdir) or return False — never raise
            assert isinstance(result, bool)

    def test_memory_db_always_passes(self):
        from phoenix.storage.database import check_db_write_access
        assert check_db_write_access("sqlite:///:memory:") is True

    def test_db_unavailable_flag_set_on_bad_path(self, monkeypatch):
        from phoenix.storage import database as db_module

        monkeypatch.setattr(db_module, "check_db_write_access", lambda url: False)

        from phoenix.sdk.config import PhoenixConfig
        config = PhoenixConfig.from_env()

        db = db_module.Database.__new__(db_module.Database)
        db.config = config
        db.engine = None
        db.SessionLocal = None
        db.db_available = True
        db._initialize()
        assert db.db_available is False

    def test_get_session_yields_none_when_unavailable(self):
        from phoenix.storage.database import Database
        from phoenix.sdk.config import PhoenixConfig

        config = PhoenixConfig.from_env()
        db = Database.__new__(Database)
        db.config = config
        db.engine = None
        db.SessionLocal = None
        db.db_available = False

        with db.get_session() as session:
            assert session is None


# ---------------------------------------------------------------------------
# RC-06: --clean flag — verified deletion, abort on failure
# ---------------------------------------------------------------------------

class TestRC06CleanFlag:
    """RC-06: clean deletes artifacts, re-creates empty dirs, aborts if deletion fails."""

    def test_clean_removes_files(self, tmp_path):
        from phoenix.cli.commands import _clean_project_directory

        manual_dir = tmp_path / "manual_tests"
        test_dir = tmp_path / "test_results"
        manual_dir.mkdir()
        test_dir.mkdir()
        (manual_dir / "manual_test_001_foo.md").write_text("old content")
        (test_dir / "test_001_foo.py").write_text("old content")

        result = _clean_project_directory(manual_dir, test_dir)
        assert result is True
        assert not any(manual_dir.iterdir())
        assert not any(test_dir.iterdir())

    def test_clean_recreates_empty_directories(self, tmp_path):
        from phoenix.cli.commands import _clean_project_directory

        manual_dir = tmp_path / "manual_tests"
        test_dir = tmp_path / "test_results"
        manual_dir.mkdir()
        test_dir.mkdir()
        (manual_dir / "old.md").write_text("x")

        _clean_project_directory(manual_dir, test_dir)
        assert manual_dir.exists()
        assert test_dir.exists()

    def test_clean_returns_true_on_success(self, tmp_path):
        from phoenix.cli.commands import _clean_project_directory

        manual_dir = tmp_path / "manual_tests"
        test_dir = tmp_path / "test_results"
        manual_dir.mkdir()
        test_dir.mkdir()

        result = _clean_project_directory(manual_dir, test_dir)
        assert result is True

    def test_clean_returns_false_when_deletion_fails(self, tmp_path, monkeypatch):
        from phoenix.cli import commands

        manual_dir = tmp_path / "manual_tests"
        test_dir = tmp_path / "test_results"
        manual_dir.mkdir()
        test_dir.mkdir()
        (manual_dir / "file.md").write_text("x")

        monkeypatch.setattr(shutil, "rmtree", lambda p: (_ for _ in ()).throw(OSError("locked")))

        result = commands._clean_project_directory(manual_dir, test_dir)
        assert result is False


# ---------------------------------------------------------------------------
# RC-07: API key validation — loud errors, no silent fallback
# ---------------------------------------------------------------------------

class TestRC07APIKeyValidation:
    """RC-07: missing API key produces loud errors and marks output as fallback."""

    def test_fallback_script_includes_warning_comment(self):
        from services.agents.test_generator import TestGeneratorAgent

        agent = TestGeneratorAgent.__new__(TestGeneratorAgent)
        agent.llm_client = None
        agent.mcp_client = None

        script = agent._build_automation_fallback_script(
            user_story="Test story",
            application_url="https://example.com",
            acceptance_criteria=["Click the button"],
        )
        assert "WARNING" in script.upper()

    def test_automation_generation_raises_without_llm(self):
        from services.agents.test_generator import TestGeneratorAgent

        agent = TestGeneratorAgent.__new__(TestGeneratorAgent)
        agent.llm_client = None
        agent.mcp_client = None
        agent.cache = type("C", (), {"get": lambda s, k: None, "set": lambda s, k, v, **kw: None})()
        agent.knowledge_base = None

        with pytest.raises(RuntimeError, match="LLM client is not configured"):
            agent._generate_automation_tests(
                user_story="Test",
                application_url="https://example.com",
                acceptance_criteria=["Click something"],
                knowledge_context="",
                risk_level=None,
            )

    def test_health_endpoint_reports_llm_status(self):
        """The /health endpoint must report llm.configured accurately."""
        # Import the FastAPI app and use TestClient
        try:
            from fastapi.testclient import TestClient
            from api.server import app, _llm_client
        except ImportError:
            pytest.skip("FastAPI TestClient not available")

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "configured" in data["llm"]
        # configured must match whether _llm_client was initialised
        assert data["llm"]["configured"] == (_llm_client is not None)
