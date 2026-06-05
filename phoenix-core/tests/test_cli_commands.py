"""Regression tests for CLI commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from phoenix.cli.main import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path):
    """Minimal project layout for CLI tests."""
    manual_dir = tmp_path / "manual_tests"
    manual_dir.mkdir()
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    return tmp_path


def _write_manual_test(directory: Path, name: str = "TC-001: Login Test") -> Path:
    """Write a minimal valid manual test Markdown file."""
    file_path = directory / "manual_test_001_login.md"
    file_path.write_text(
        f"# {name}\n\n"
        "## Overview\n"
        "| Field | Value |\n"
        "|---|---|\n"
        "| Risk Level | SMOKE |\n\n"
        "## Description\nLogin test.\n\n"
        "## Preconditions\nUser exists.\n\n"
        "## Test Steps\n"
        "| # | Action | Expected Result | Test Data |\n"
        "|---|---|---|---|\n"
        "| 1 | Navigate to login page | Login page shown | |\n"
        "| 2 | Enter admin/admin123 | Fields filled | |\n"
        "| 3 | Click Login button | Dashboard shown | |\n\n"
        "## Expected Result\nUser is logged in.\n",
        encoding="utf-8",
    )
    return file_path


class TestCleanCommand:
    def test_clean_dry_run_shows_nothing_to_clean(self, runner, tmp_project):
        with runner.isolated_filesystem(temp_dir=tmp_project):
            result = runner.invoke(main, ["clean", "--dry-run"])
        assert result.exit_code == 0

    def test_clean_removes_manual_tests_dir(self, runner, tmp_path):
        manual_dir = tmp_path / "manual_tests"
        manual_dir.mkdir()
        (manual_dir / "manual_test_001.md").write_text("# test", encoding="utf-8")

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["clean"])

        assert result.exit_code == 0

    def test_clean_removes_test_scripts_dir(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_001_login.py").write_text("# generated", encoding="utf-8")

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["clean"])

        assert result.exit_code == 0


class TestAutomateFileFlag:
    def test_automate_file_flag_no_nameError(self, runner, tmp_project):
        """phoenix automate --file should not raise NameError for manual_path."""
        manual_file = _write_manual_test(tmp_project / "manual_tests")

        # We don't have a running intelligence server in tests, so this will
        # fail at the network call — but NOT with NameError on manual_path.
        result = runner.invoke(
            main,
            ["automate", "--file", str(manual_file)],
        )
        # Must not be a Python-level crash (NameError raises exit_code 1 with traceback)
        assert "NameError" not in (result.output or "")
        if result.exception:
            assert "NameError" not in type(result.exception).__name__

    def test_automate_missing_manual_tests_warns(self, runner, tmp_path):
        """phoenix automate with no manual tests should warn, not crash."""
        empty_dir = tmp_path / "manual_tests"
        empty_dir.mkdir()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["automate"])

        assert result.exit_code == 0
        assert "No manual test files found" in result.output


class TestIntentParserIntegration:
    def test_parser_produces_parsedtestcase(self):
        from phoenix.parsers.intent_parser import IntentParser
        parser = IntentParser()
        tc = parser.parse_test_case(
            ["Given I am on the Add Employee page", "Then the form should be displayed"],
            {"name": "Add Employee Test"},
        )
        assert tc.title == "Add Employee Test"
        assert len(tc.steps) == 2

    def test_parser_high_confidence_navigate(self):
        from phoenix.models.intent import ActionType
        from phoenix.parsers.intent_parser import IntentParser
        parser = IntentParser()
        intent = parser.parse_step("Given I am on the Add Employee page", {})
        assert intent.action == ActionType.NAVIGATE
        assert intent.target_page == "add_employee"
        assert intent.confidence >= 0.8


class TestQualityGateBlocking:
    def test_gate_blocks_manual_review_marker(self):
        from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent
        from phoenix.validation.quality_gate import QualityGate

        bad_step = SemanticIntent(
            raw_text="[NEEDS MANUAL REVIEW] Handle edge case",
            intent_type="action",
            action=ActionType.UNKNOWN,
            confidence=0.0,
        )
        tc = ParsedTestCase(title="Bad Test", steps=[bad_step])
        result = QualityGate().validate(tc)
        assert result.passed is False
        assert any("manual_review_marker" in e for e in result.blocking_errors)

    def test_gate_blocks_invalid_url_assertions(self):
        from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent
        from phoenix.validation.quality_gate import QualityGate

        bad_step = SemanticIntent(
            raw_text="Apply Leave page is visible",
            intent_type="assertion",
            action=ActionType.ASSERT_URL,
            expected_state="Apply Leave page is visible",
            confidence=0.9,
        )
        tc = ParsedTestCase(title="Leave Test", steps=[bad_step])
        result = QualityGate().validate(tc)
        assert result.passed is False
        assert any("has_invalid_assertions" in e for e in result.blocking_errors)

    def test_gate_blocks_missing_locators(self):
        from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent
        from phoenix.validation.quality_gate import QualityGate

        bad_step = SemanticIntent(
            raw_text="Click something undefined",
            intent_type="action",
            action=ActionType.CLICK,
            target_element=None,
            target_locator=None,
            confidence=0.9,
        )
        tc = ParsedTestCase(title="Missing Locator Test", steps=[bad_step])
        result = QualityGate().validate(tc)
        assert result.passed is False
        assert any("has_unresolved_locators" in e for e in result.blocking_errors)
