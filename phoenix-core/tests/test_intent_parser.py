"""Regression tests for the IntentParser."""

import pytest

from phoenix.models.intent import ActionType
from phoenix.parsers.intent_parser import IntentParser


@pytest.fixture
def parser():
    return IntentParser()


class TestIntentParser:
    def test_parses_gherkin_given_navigate(self, parser):
        intent = parser.parse_step("Given I am on the Add Employee page", {})
        assert intent.action == ActionType.NAVIGATE
        assert intent.intent_type == "precondition"
        assert intent.target_page == "add_employee"
        assert intent.confidence >= 0.8

    def test_parses_gherkin_when_click(self, parser):
        intent = parser.parse_step("When I click the Submit button", {})
        assert intent.action == ActionType.CLICK
        assert intent.target_element is not None

    def test_parses_gherkin_then_assert_visible(self, parser):
        intent = parser.parse_step("Then the dashboard should be displayed", {})
        assert intent.action == ActionType.ASSERT_VISIBLE
        assert intent.intent_type == "assertion"

    def test_parses_plain_english_navigate(self, parser):
        intent = parser.parse_step("Navigate to the Login page", {})
        assert intent.action == ActionType.NAVIGATE
        assert "login" in intent.target_page

    def test_parses_fill_step(self, parser):
        intent = parser.parse_step("Enter 'admin' in the Username field", {})
        assert intent.action == ActionType.FILL

    def test_parses_select_step(self, parser):
        intent = parser.parse_step("Select 'Annual Leave' from the Leave Type dropdown", {})
        assert intent.action == ActionType.SELECT

    def test_parses_login_shorthand(self, parser):
        intent = parser.parse_step("Log in with valid credentials", {})
        assert intent.action == ActionType.FILL
        assert intent.target_element == "login_form"
        assert intent.confidence >= 0.9

    def test_detects_manual_review_marker(self, parser):
        intent = parser.parse_step("[NEEDS MANUAL REVIEW] Some step", {})
        assert intent.action == ActionType.UNKNOWN
        assert intent.requires_review is True
        assert any("MANUAL REVIEW" in e for e in intent.validation_errors)

    def test_detects_unknown_actions(self, parser):
        intent = parser.parse_step("xyzzy frobnicate the quux", {})
        assert intent.action == ActionType.UNKNOWN
        assert intent.confidence < 0.5

    def test_parse_test_case_gherkin_format(self, parser):
        steps = [
            "Given I am on the Login page",
            "When I enter 'admin' in the Username field",
            "Then the dashboard should be displayed",
        ]
        tc = parser.parse_test_case(steps, {"name": "Login Test"})
        assert tc.title == "Login Test"
        assert tc.source_format == "gherkin"
        assert len(tc.steps) == 3

    def test_parse_test_case_computes_confidence(self, parser):
        steps = ["Navigate to the login page", "Click the Login button"]
        tc = parser.parse_test_case(steps, {"name": "Simple Test"})
        assert 0.0 < tc.overall_confidence <= 1.0

    def test_parse_test_case_unknown_action_not_automatable(self, parser):
        steps = ["[NEEDS MANUAL REVIEW] Do something unclear"]
        tc = parser.parse_test_case(steps, {"name": "Bad Test"})
        assert tc.is_automatable is False
        assert len(tc.blocking_issues) > 0
